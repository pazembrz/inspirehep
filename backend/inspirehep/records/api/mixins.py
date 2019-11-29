import hashlib
import uuid
from io import BytesIO

import magic
import requests
import structlog
from botocore.exceptions import ClientError
from flask import current_app
from inspire_schemas.builders import LiteratureBuilder
from invenio_db import db
from invenio_files_rest.models import ObjectVersion, Timestamp, timestamp_before_update
from redis import StrictRedis
from sqlalchemy import func, or_

from inspirehep.records.errors import (
    ContentTypeMismatchError,
    DataSizeMismatchError,
    DownloadFileError,
    HashMismatchError,
    MissingDataError,
    MissingPermissions,
)
from inspirehep.records.models import (
    ConferenceLiterature,
    ConferenceToLiteratureRelationshipType,
    RecordCitations,
)

LOGGER = structlog.getLogger()

# We need to turn this odd as updating many files at the same time by many workers
# is causing deadlocks due to updating "update" column in invenio files_files
db.event.remove(Timestamp, "before_update", timestamp_before_update)


def requests_retry_session(retries=3):
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class CitationMixin:
    def _citation_query(self):
        """Prepares query with all records which cited this one
        Returns:
            query: Query containing all citations for this record
        """
        return RecordCitations.query.filter_by(cited_id=self.id)

    @property
    def citation_count(self):
        """Gives citation count number
        Returns:
            int: Citation count number for this record if it is literature or data
            record.
        """
        return self._citation_query().count()

    @property
    def citations_by_year(self):
        """Return the number of citations received per year for the current record.
        Returns:
            dict: citation summary for this record.
        """
        db_query = self._citation_query()
        db_query = db_query.with_entities(
            func.count(RecordCitations.citation_date).label("sum"),
            func.date_trunc("year", RecordCitations.citation_date).label("year"),
        )
        db_query = db_query.group_by("year").order_by("year")
        return [{"year": r.year.year, "count": r.sum} for r in db_query.all() if r.year]

    def hard_delete(self):
        with db.session.begin_nested():
            LOGGER.warning("Hard Deleting citations")
            # Removing citations from RecordCitations table and
            # Removing references to this record from RecordCitations table
            RecordCitations.query.filter(
                or_(
                    RecordCitations.citer_id == self.id,
                    RecordCitations.cited_id == self.id,
                )
            ).delete()
        super().hard_delete()

    def is_superseded(self):
        """Checks if record is superseded
        Returns:
            bool: True if is superseded, False otherwise
        """
        return "successor" in self.get_value("related_records.relation", "")

    def update_refs_in_citation_table(self, save_every=100):
        """Updates all references in citation table.
        First removes all references (where citer is this record),
        then adds all from the record again.
        Args:
            save_every (int): How often data should be saved into session.
            One by one is very inefficient, but so is 10000 at once.
        """
        RecordCitations.query.filter_by(citer_id=self.id).delete()
        if (
            self.is_superseded()
            or self.get("deleted")
            or self.pid_type not in ["lit"]
            or "Literature" not in self["_collections"]
        ):
            # Record is not eligible to cite
            LOGGER.info(
                "Record's is not eligible to cite.",
                recid=self.get("control_number"),
                uuid=str(self.id),
            )
            return
        records_pids = self.get_linked_pids_from_field("references.record")
        # Limit records to literature and data as only this types can be cited
        proper_records_pids = [
            rec_pid for rec_pid in records_pids if rec_pid[0] in ["lit", "dat"]
        ]
        LOGGER.info(
            f"Record has {len(proper_records_pids)} linked references",
            recid=self.get("control_number"),
            uuid=str(self.id),
        )
        records_uuids = self.get_records_ids_by_pids(proper_records_pids)
        referenced_records = set()
        references_waiting_for_commit = []
        citation_date = self.earliest_date
        for reference in records_uuids:
            if reference not in referenced_records:
                referenced_records.add(reference)
                references_waiting_for_commit.append(
                    RecordCitations(
                        citer_id=self.model.id,
                        cited_id=reference,
                        citation_date=citation_date,
                    )
                )
            if len(references_waiting_for_commit) >= save_every:
                db.session.bulk_save_objects(references_waiting_for_commit)
                references_waiting_for_commit = []
        if references_waiting_for_commit:
            db.session.bulk_save_objects(references_waiting_for_commit)
        LOGGER.info(
            "Record citations updated",
            recid=self.get("control_number"),
            uuid=str(self.id),
        )

    def update(self, data, disable_relations_update=False, *args, **kwargs):
        super().update(data, disable_relations_update, *args, **kwargs)

        if disable_relations_update:
            LOGGER.info(
                "Record citation update disabled",
                recid=self.get("control_number"),
                uuid=str(self.id),
            )
        else:
            self.update_refs_in_citation_table()


class FilesMixin:
    @property
    def s3_client(self):
        return current_app.extensions.get("inspire-s3").s3_client

    def update(self, data, force=False, *args, **kwargs):
        data = self.add_files(data, force=force)
        super().update(data, *args, **kwargs)

    def get_download_url(self, url, original_url=None):
        download_url = original_url or url
        if download_url.startswith("http"):
            return download_url
        elif url.startswith("http"):
            return url
        return f"{current_app.config['PREFERRED_URL_SCHEME']}://{current_app.config['SERVER_NAME']}{download_url}"

    def check_key_and_filename(self, key, filename, url):
        if not filename:
            if not self.is_hash(key):
                filename = key
                key = None
            else:
                filename = self.get_filiname_from_url_or_key(url, key)
                LOGGER.info(
                    "Filename not provided",
                    uuid=self.id,
                    key=key,
                    new_filename=filename,
                )
        return key, filename

    def check_file_metadata(self, key, url, force):
        mimetype = None
        size = None
        content_disposition = None
        if not key:
            key = self.check_url_on_cache(url)
        if key:
            metadata = self.s3_get_file_metadata(key)
            if metadata:
                mimetype = metadata.get("ContentType")
                content_disposition = metadata.get("ContentDisposition")
                size = metadata.get("ContentLength")
                LOGGER.info(
                    "File already on s3", uuid=self.id, key=key, ContentType=mimetype
                )
                if size == 0:
                    LOGGER.warning(
                        "File size is wrong. Forcing to redownload",
                        key=key,
                        recid=self["control_number"],
                        mimetype=mimetype,
                        size=size,
                        content_disposition=content_disposition,
                    )
                    force = True
            else:
                LOGGER.info("Metadata on s3 is missing.", key=key, uuid=self.id)
                force = True
        return key, url, mimetype, size, content_disposition, force

    def add_file(
        self,
        url,
        original_url=None,
        key=None,
        filename=None,
        force=False,
        *args,
        **kwargs,
    ):
        download_url = self.get_download_url(url=url, original_url=original_url)
        key, filename = self.check_key_and_filename(key, filename, download_url)
        key, url, mimetype, size, content_disposition, force = self.check_file_metadata(
            key, url, force
        )
        if not key or force:
            LOGGER.info(
                "Downloading url", uuid=self.id, url=download_url, force=force, key=key
            )
            key, mimetype, size = self.add_file_from_url(
                download_url, filename=filename, force=force
            )
        elif (
            not mimetype or mimetype == "binary/octet-stream" or not content_disposition
        ):
            LOGGER.info("Updating file metadata", recid=self["control_number"], key=key)
            data_stream = self.get_file_object(key)
            mimetype, size = self.update_metadata_for_file(
                key, data_stream.read(), filename
            )
            if not key:
                raise DownloadFileError(f"Cannot download file", url=url)
        data = {
            "key": key,
            "original_url": original_url or url,
            "filename": filename,
            "url": self.build_s3_url(key),
            "mimetype": mimetype,
            "size": size,
        }
        return data

    def extract_key_from_afs_path(self, afs_path):
        key = afs_path.split(b"/")[-1]
        if self.is_hash(key):
            LOGGER.info(
                "Found cached file on AFS",
                afs_path=afs_path,
                key=key,
                recid=self["control_number"],
            )
            return key.decode("utf-8")
        return None

    def check_url_on_cache(self, url):
        redis = StrictRedis.from_url(current_app.config["CACHE_REDIS_URL"])
        afs_path = redis.hget("afs_file_locations", url)
        if afs_path:
            return self.extract_key_from_afs_path(afs_path)
        return None

    def verify_metadata(
        self,
        metadata,
        expected_mimetype,
        expected_size,
        expected_read_for_group="http://acs.amazonaws.com/groups/global/AllUsers",
    ):
        if expected_mimetype and metadata["ContentType"] != expected_mimetype:
            raise ContentTypeMismatchError
        if expected_size and metadata["ContentLength"] != expected_size:
            raise DataSizeMismatchError
        if expected_read_for_group:
            for grantee in metadata.get("Grants", []):
                if (
                    grantee["Grantee"].get("URI") == expected_read_for_group
                    and grantee.get("Permission") == "READ"
                ):
                    return
            raise MissingPermissions

    def get_all_files_local_metadata(self):
        if "_files" in self:
            all_files = self["_files"]
        else:
            all_files = []
            all_files.extend(self.get("figures", []))
            all_files.extend(self.get("documents", []))
        return all_files

    def get_local_metadata(self, key):
        all_files = self.get_all_files_local_metadata()
        for file in all_files:
            if file["key"] == key:
                return file
        return None

    def check_file(self, key):
        response = self.s3_get_file_metadata(key)
        if not response:
            raise MissingDataError

        local_metadata = self.get_local_metadata(key)
        # Compare s3 metadata with local metadata

        if local_metadata:
            self.verify_metadata(
                response, local_metadata.get("mimetype"), local_metadata.get("size")
            )
        data_stream = self.get_file_object(key)
        data = data_stream.read()
        data_size = len(data)
        if data_size == 0:
            raise DataSizeMismatchError
        key_hashed = self.hash_data(data=data)
        mimetype = magic.from_buffer(data, mime=True)
        if key != key_hashed:
            raise HashMismatchError
        # Compare s3 metadata with s3 data
        self.verify_metadata(response, mimetype, data_size)

    def verify_file(
        self, key, url, original_url=None, filename=None, fix=False, **kwargs
    ):
        try:
            self.check_file(key)
        except (HashMismatchError, DataSizeMismatchError, MissingDataError) as e:
            LOGGER.exception(
                "File is corrupted. Re-download from original url!",
                recid=self["control_number"],
                key=key,
                exc=e,
            )
            if fix:
                self.add_file_from_url(original_url, filename, force=True)
        except (ContentTypeMismatchError, MissingPermissions) as e:
            LOGGER.error(
                "File metadata on s3 are corupted.",
                recid=self["control_number"],
                key=key,
                exc=e,
            )
            if fix:
                self.add_file_from_url(original_url or url, filename)

    def verify_record_files(self, fix=False):
        all_files = self.get_all_files_local_metadata()
        for file in all_files:
            if self.is_hash(file["key"]):
                self.verify_file(fix=fix, **file)

    def build_s3_url(self, key):
        return f"{current_app.config.get('S3_HOSTNAME')}/{self.get_bucket(key)}/{key}"

    def add_file_from_url(self, url, filename, force=False):
        max_retries = current_app.config.get("FILES_DOWNLOAD_MAX_RETRIES", 3)
        data = requests_retry_session(retries=max_retries).get(url, stream=True).content
        return self.add_file_from_memory(data, filename, force)

    def add_file_from_memory(self, data, filename, force=False):
        key_hashed = self.hash_data(data=data)
        mimetype = magic.from_buffer(data, mime=True)
        size = len(data)
        s3_file_metadata = self.s3_get_file_metadata(key_hashed)
        try:
            self.verify_metadata(s3_file_metadata, mimetype, size)
        except (ContentTypeMismatchError, MissingPermissions):
            self.update_metadata_for_file(key_hashed, data, filename)
        except DataSizeMismatchError:
            force = True
        if not s3_file_metadata or force:
            if force:
                LOGGER.warning(
                    "Forcing to push file to s3. Deleting old data if exists",
                    recid=self["control_number"],
                    key=key_hashed,
                )
                self.s3_client.delete_object(
                    Bucket=self.get_bucket(key_hashed), Key=key_hashed
                )
            LOGGER.info(
                "Pushing file to S3", key=key_hashed, recid=self["control_number"]
            )
            self.send_file_to_s3(key_hashed, filename, file=data, mimetype=mimetype)
        return key_hashed, mimetype, size

    def update_metadata_for_file(self, key, data, filename):
        mimetype = magic.from_buffer(data, mime=True)
        size = len(data)
        self.replace_file_metadata_on_s3(key, filename, mimetype=mimetype)
        return mimetype, size

    def s3_get_file_metadata(self, key):
        try:
            object_head = self.s3_client.head_object(
                Bucket=self.get_bucket(key), Key=key
            )
            acls = self.s3_client.get_object_acl(Bucket=self.get_bucket(key), Key=key)
        except ClientError as e:
            LOGGER.warning(exc=e, key=key, recid=self["control_number"])
            return None
        object_head["Grants"] = acls["Grants"]
        return object_head

    def send_file_to_s3(self, key, filename, file, mimetype=None):
        try:
            LOGGER.info(
                "Pushing file to s3",
                recid=self["control_number"],
                key=key,
                filename=filename,
            )
            size = len(file)
            if not mimetype:
                mimetype = magic.from_buffer(file, mime=True)
            self.s3_client.put_object(
                ACL="public-read",
                Body=file,
                Bucket=self.get_bucket(key),
                Key=key,
                ContentDisposition=f'attachment; filename="{filename}"',
                ContentLength=size,
                ContentType=mimetype,
            )
        except ClientError as e:
            LOGGER.warning(exc=e, key=key, recid=self["control_number"])
            raise

    def replace_file_metadata_on_s3(self, key, filename, mimetype):
        try:
            LOGGER.info(
                "Updating file metadata on s3",
                recid=self["control_number"],
                key=key,
                filename=filename,
            )
            self.s3_client.copy_object(
                ACL="public-read",
                Bucket=self.get_bucket(key),
                Key=key,
                CopySource={"Bucket": self.get_bucket(key), "Key": key},
                ContentDisposition=f'attachment; filename="{filename}"',
                ContentType=mimetype,
                MetadataDirective="REPLACE",
            )
        except ClientError as e:
            LOGGER.warning(exc=e, key=key, recid=self["control_number"])
            raise

    def get_view_url(self, key):
        """this is url for local view which serves files"""
        api_prefix = current_app.config["FILES_API_PREFIX"]
        return f"{api_prefix}/FILES/{key}"

    def get_object(self, key):
        try:
            return self.s3_client.get_object(Bucket=self.get_bucket(key), Key=key)
        except ClientError as e:
            LOGGER.warning(exc=e, key=key, recid=self["control_number"])
        return None

    def get_file_object(self, key):
        response = self.get_object(key)
        if response:
            return response["Body"]
        return None

    def get_filiname_from_url_or_key(self, url, key):
        filename = None
        if url:
            filename = self.find_filename_from_url(url)
        return filename or key

    @staticmethod
    def get_bucket(key):
        bucket = f"{current_app.config.get('S3_BUCKET_PREFIX')}{key[0]}"
        return bucket

    def verify_hash_of_files(self, file_object, file_hash):
        calculated_hash = self.hash_data(file_instance=file_object)
        return calculated_hash == file_hash

    @staticmethod
    def find_filename_from_url(url):
        try:
            return url.split("/")[-1]
        except AttributeError:
            return None

    @staticmethod
    def hash_data(data=None, file_instance=None):
        """Hashes data/file with selected algorithm.

        Note:
            `file_instance` takes precedence before `data` (if it's provided)

        Args:
            data (bytes): data bytes
            file_instance (ObjectVersion): file instance

        Returns:
            str: Hash of the file_instance/data

        Raises:
            ValueError: when `data` AND `file_instance` are empty
        """
        if file_instance:
            file_stream = file_instance.file.storage().open()
            data = file_stream.read()

        if data:
            return hashlib.sha1(data).hexdigest()

        raise ValueError("Data for hashing cannot be empty")

    @staticmethod
    def is_hash(test_str):
        return test_str and len(test_str) == 40

    def add_files(self, data, force=False):
        if not current_app.config.get("FEATURE_FLAG_ENABLE_FILES", False):
            LOGGER.info("Feature flag ``FEATURE_FLAG_ENABLE_FILES`` is disabled")
            return data

        if "deleted" in data and data["deleted"]:
            LOGGER.info("Record is deleted", uuid=self.id)
            return data

        documents = data.pop("documents", [])
        figures = data.pop("figures", [])

        self.pop("documents", None)
        self.pop("figures", None)

        added_documents = self.add_documents(documents, force=force)
        if added_documents:
            data["documents"] = added_documents

        added_figures = self.add_figures(figures, force=force)
        if added_figures:
            data["figures"] = added_figures

        return data

    def add_documents(self, documents, force=False):
        builder = LiteratureBuilder()
        for document in documents:
            if document.get("hidden", False):
                builder.add_document(**document)
                continue
            file_data = self.add_file(document=True, **document, force=force)
            document.update(file_data)
            if "fulltext" not in document:
                document["fulltext"] = True
            try:
                builder.add_document(**document)
            except ValueError as e:
                LOGGER.exception(
                    recid=self["control_number"], document=document.get("key")
                )
        return builder.record.get("documents")

    def add_figures(self, figures, force=False):
        builder = LiteratureBuilder()
        for figure in figures:
            file_data = self.add_file(**figure, force=force)
            figure.update(file_data)
            try:
                builder.add_figure(**figure)
            except ValueError as e:
                LOGGER.exception(recid=self["control_number"], figure=figure.get("key"))
        return builder.record.get("figures")


class ConferencePaperAndProceedingsMixin:
    def clean_conference_literature_relation(self):
        ConferenceLiterature.query.filter_by(literature_uuid=self.id).delete()

    def create_conferences_relations(self, document_type):
        conferences_pids = self.get_linked_pids_from_field(
            "publication_info.conference_record"
        )
        conferences = self.get_records_by_pids(conferences_pids)
        conference_literature_relations_waiting_for_commit = []
        for conference in conferences:
            if conference.get("deleted") is not True:
                conference_literature_relations_waiting_for_commit.append(
                    ConferenceLiterature(
                        conference_uuid=conference.id,
                        literature_uuid=self.id,
                        relationship_type=ConferenceToLiteratureRelationshipType(
                            document_type
                        ),
                    )
                )
        if len(conference_literature_relations_waiting_for_commit) > 0:
            db.session.bulk_save_objects(
                conference_literature_relations_waiting_for_commit
            )
            LOGGER.info(
                "Conferecnce-literature relation set",
                recid=self.get("control_number"),
                uuid=str(self.id),
                records_attached=len(
                    conference_literature_relations_waiting_for_commit
                ),
            )

    def update_conference_paper_and_proccedings(self):
        self.clean_conference_literature_relation()
        document_types = set(self.get("document_type"))
        allowed_types = set(
            [option.value for option in list(ConferenceToLiteratureRelationshipType)]
        )
        relationship_types = allowed_types.intersection(document_types)
        if relationship_types and self.get("deleted") is not True:
            self.create_conferences_relations(relationship_types.pop())

    def hard_delete(self):
        self.clean_conference_literature_relation()
        super().hard_delete()

    def update(self, data, disable_relations_update=False, *args, **kwargs):
        super().update(data, disable_relations_update, *args, **kwargs)
        if not disable_relations_update:
            self.update_conference_paper_and_proccedings()
        else:
            LOGGER.info(
                "Record conference papers and proceedings update disabled",
                recid=self.get("control_number"),
                uuid=str(self.id),
            )

    def get_newest_linked_conferences_uuid(self):
        """Returns referenced conferences for which perspective this record has changed
        """
        try:
            prev_version = self._previous_version
        except AttributeError:
            prev_version = {}

        changed_deleted_status = self.get("deleted", False) ^ prev_version.get(
            "deleted", False
        )
        pids_latest = self.get_linked_pids_from_field(
            "publication_info.conference_record"
        )

        if changed_deleted_status:
            return list(self.get_records_ids_by_pids(pids_latest))

        doc_type_previous = set(prev_version.get("document_type", []))
        doc_type_latest = set(self.get("document_type", []))
        doc_type_diff = doc_type_previous.symmetric_difference(doc_type_latest)
        allowed_types = set(
            [option.value for option in list(ConferenceToLiteratureRelationshipType)]
        )
        type_changed = True if doc_type_diff.intersection(allowed_types) else False

        try:
            pids_previous = set(
                self._previous_version.get_linked_pids_from_field(
                    "publication_info.conference_record"
                )
            )
        except AttributeError:
            pids_previous = []
        if type_changed:
            pids_changed = set(pids_latest)
            pids_changed.update(pids_previous)
        else:
            pids_changed = set.symmetric_difference(set(pids_latest), pids_previous)

        return list(self.get_records_ids_by_pids(list(pids_changed)))
