# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2014-2018 CERN.
#
# INSPIRE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# INSPIRE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with INSPIRE. If not, see <http://www.gnu.org/licenses/>.
#
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization
# or submit itself to any jurisdiction.

"""INSPIRE module that adds more fun to the platform."""

from __future__ import absolute_import, division, print_function

from io import BytesIO
from pathlib import Path

import uuid
import hashlib

from flask import current_app
from fs.errors import ResourceNotFoundError
from fs.opener import fsopen
from inspire_dojson.utils import strip_empty_values
from inspire_schemas.api import validate as schema_validate
from inspire_schemas.builders import LiteratureBuilder
from invenio_db import db
from invenio_files_rest.models import Bucket
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.models import PersistentIdentifier, RecordIdentifier
from invenio_records.models import RecordMetadata
from invenio_records_files.api import Record
from invenio_records_files.models import RecordsBuckets
from sqlalchemy import Text, cast, not_, or_, type_coerce
from sqlalchemy.dialects.postgresql import JSONB


class InspireQueryBuilder(object):
    def __init__(self):
        self._query = RecordMetadata.query

    def not_deleted(self):
        expression = or_(
            not_(type_coerce(RecordMetadata.json, JSONB).has_key("deleted")),
            not_(RecordMetadata.json["deleted"] == cast(True, JSONB)),
        )
        return self.filter(expression)

    def by_collections(self, collections):
        expression = type_coerce(RecordMetadata.json, JSONB)["_collections"].contains(
            collections
        )
        return self.filter(expression)

    def filter(self, expression):
        self._query = self._query.filter(expression)
        return self

    def no_duplicates(self):
        self._query = self._query.distinct(RecordMetadata.json["control_number"])
        return self

    def query(self):
        return self._query


class InspireRecord(Record):
    """Inspire Record."""

    pid_type = None

    @staticmethod
    def strip_empty_values(data):
        return strip_empty_values(data)

    @staticmethod
    def mint(record_uuid, data):
        pass

    def validate(self):
        schema_validate(self)

    @staticmethod
    def query_builder():
        return InspireQueryBuilder()

    @classmethod
    def get_uuid_from_pid_value(cls, pid_value, pid_type=None):
        if not pid_type:
            pid_type = cls.pid_type
        pid = PersistentIdentifier.get(pid_type, pid_value)
        return pid.object_uuid

    @classmethod
    def get_record_by_pid_value(cls, pid_value, pid_type=None):
        if not pid_type:
            pid_type = cls.pid_type
        record_uuid = cls.get_uuid_from_pid_value(pid_value)
        record = cls.get_record(record_uuid)
        return record

    @classmethod
    def create(cls, data, **kwargs):
        id_ = uuid.uuid4()
        data = cls.strip_empty_values(data)
        with db.session.begin_nested():
            cls.mint(id_, data)
            record = super().create(data, id_=id_, **kwargs)
        return record

    def update(self, data):
        with db.session.begin_nested():
            super().update(data)
            self.model.json = self
            db.session.add(self.model)

    def redirect(self, other):
        """Redirect pidstore of current record to the other one.

        Args:
            other (InspireRecord): The record that self is going to be redirected.
        """
        self_pids = PersistentIdentifier.query.filter(
            PersistentIdentifier.object_uuid == self.id
        ).all()
        other_pid = PersistentIdentifier.query.filter(
            PersistentIdentifier.object_uuid == other.id
        ).one()
        with db.session.begin_nested():
            for pid in self_pids:
                pid.redirect(other_pid)
                db.session.add(pid)
            self._mark_deleted()

    @classmethod
    def create_or_update(cls, data, **kwargs):
        control_number = data.get("control_number")
        try:
            record = cls.get_record_by_pid_value(control_number)
            record.update(data)
        except PIDDoesNotExistError:
            record = cls.create(data, **kwargs)
        return record

    def delete(self):
        with db.session.begin_nested():
            pids = PersistentIdentifier.query.filter(
                PersistentIdentifier.object_uuid == self.id
            ).all()
            for pid in pids:
                pid.delete()
                db.session.delete(pid)
        self._mark_deleted()

    def _mark_deleted(self):
        self["deleted"] = True

    def hard_delete(self):
        with db.session.begin_nested():
            pids = PersistentIdentifier.query.filter(
                PersistentIdentifier.object_uuid == self.id
            ).all()
            for pid in pids:
                RecordIdentifier.query.filter_by(recid=pid.pid_value).delete()
                db.session.delete(pid)
            db.session.delete(self.model)

    def add_files(self, documents, figures, src_records=(), only_new=False):
        if not documents or figures:
            raise TypeError("No files passed, at least one is needed")
        files = []
        for doc in documents:
            files.append(self._add_file(document=True, **doc))
        for fig in figures:
            files.sappend(self._add_file(**fig))

    def _get_bucket(self, location=None, storage_class=None):
        pass

    def _create_bucket(self, location=None, storage_class=None):
        """Create bucket (only one for one storage_class) and return it
        Overwrites base clase as it is not implemented """

        bucket = RecordsBuckets.query.filter(
            RecordsBuckets.record_id == self.id, Bucket.storage_class == storage_class
        ).one_or_none()

        if not bucket:
            if location is None:
                location = current_app.config["RECORDS_DEFAULT_FILE_LOCATION_NAME"]
            if storage_class is None:
                storage_class = current_app.config["RECORDS_DEFAULT_STORAGE_CLASS"]

            bucket = Bucket.create(location=location, storage_class=storage_class)
        return bucket

    def _download_file_from_url(self, url):
        """Downloads file and callculates hash for it
        Args:
            url: Local or remote url/filepath

        Returns: Data stream, and key (which is a hash)

        """
        stream = fsopen(url, mode="rb")
        # TODO: change to stream.read() when fs will be updated to > 2.0
        # As HTTPOpener is not working with size = -1
        # (and read() method sets this size as default)
        # This is workaround until we will update to fs >2.0
        data = stream._f.wrapped_file.read()
        stream.close()
        key = hashlib.sha1(data).hexdigest()
        return {"data": BytesIO(data), "key": key}

    def _download_file(self, url, original_url=None, **kwargs):
        if original_url:
            try:
                file = self._download_file_from_url(original_url)
                return file
            except ResourceNotFoundError:
                pass
        if not url.startswith("http"):
            root_path = current_app.config["BASE_FILES_LOCATION"]
            records_directory = current_app.config["RECORDS_DEFAULT_FILE_LOCATION_NAME"]
            url = Path(root_path + records_directory + url).as_uri()

        file = self._download_file_from_url(url)
        return file

    def _add_file(self, url, filename=None, is_document=False, **kwargs):
        """Downloads file from url and saves it with `filename` as a proper name
        Args:
            url: Url to a file, it can be also path on disk
            filename: Filename which should be wisible to the user.
                If not provided, last part of URL will be used as a filename
            is_document: Flag to inform if it's a document or a figure
            **kwargs: Additional metadata for the file:
                'description': works for documents and figures
                'fulltext': works for documents only
                'hidden': works for documents only
                'material': works for documents and figures
                'caption': works for facets only
        Returns: Metadata for file

        """

        metadata = kwargs
        metadata["key"] = key
        metadata["original_url"] = url
        metadata["filename"] = filename
        if "fulltext" not in metadata:
            metadata["fulltext"] = True
        if "hidden" not in metadata:
            metadata["hidden"] = False

        if key in self.files:
            # If key is already in files
            # it means this file is already downloaded
            return self.files[key].data

        self.files[key] = BytesIO(data)
        file_path = "/api/files/{bucket}/{key}".format(
            bucket=self.files[key].bucket_id, key=key
        )
        metadata["url"] = file_path
        builder = LiteratureBuilder(record=self)
        if is_document:
            builder.add_document(**metadata)
        else:
            builder.add_figure(**metadata)
        return metadata
