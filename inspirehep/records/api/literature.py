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

import hashlib
from io import BytesIO

from flask import current_app
from fs.errors import ResourceNotFoundError
from fs.opener import fsopen
from inspire_schemas.builders import LiteratureBuilder
from invenio_files_rest.models import Location, Bucket, ObjectVersion
from invenio_records_files.models import RecordsBuckets

from ...pidstore.api import PidStoreLiterature
from .base import InspireRecord


class LiteratureRecord(InspireRecord):
    """Literature Record."""

    pid_type = "lit"

    @classmethod
    def create(cls, data, **kwargs):
        documents = data.pop("documents", None)
        figures = data.pop("documents", None)
        record = super().create(data, **kwargs)
        if documents or figures:
            record.set_files(documents=documents, figures=figures)
        return record

    def update(self, data):
        documents = data.pop("documents", None)
        figures = data.pop("documents", None)
        record = super().update(data)
        if documents or figures:
            record.set_files(documents=documents, figures=figures)
        return record

    @staticmethod
    def mint(record_uuid, data):
        PidStoreLiterature.mint(record_uuid, data)

    def delete(self):
        for file in list(self.files.keys):
            del self.files[file]
        super().delete()

    def set_files(self, documents=None, figures=None):
        """Sets new documents and figures for record.
        Every figure or document not listed in arguments will be removed from record.
        If you want to only add new documents, use `add_files`
        Args:
            documents (list): List of documents which should be set to this record
            figures (list): List of figures which should be set to this record

            Documents and figures are lists of dicts.
            Most obscure dict which whould be provided for each file is:
            {
                'url': 'http:// or /api/file/bucket_id/file_key'
                'is_document': True or False(default)
            }

        Returns: list of keys of all documents and figures in this record

        """
        self.pop("figures", [])
        self.pop("documents", [])
        files = self.add_files(documents=documents, figures=figures)
        keys = [file_metadata["key"] for file_metadata in files]
        for key in list(self.files.keys):
            if key not in keys:
                del self.files[key]
        return keys

    def add_files(self, documents=None, figures=None):
        """Public method for adding documents and figures

        Args:
            documents (list): List of documents which should be added to this record
            figures (list): List of figures which should be added to this record

            Documents and figures are lists of dicts.
            Most obscure dict which whould be provided for each file is:
            {
                'url': 'http:// or /api/file/bucket_id/file_key'
                'is_document': True or False(default)
            }


        Returns: List of added keys

        """
        if not documents and not figures:
            raise TypeError("No files passed, at least one is needed")
        files = []
        builder = LiteratureBuilder(record=self)
        if documents:
            doc_keys = [
                doc_metadata["key"] for doc_metadata in self.get("documents", [])
            ]
            for doc in documents:
                metadata = self._add_file(document=True, **doc)
                if metadata["key"] not in doc_keys:
                    builder.add_document(**metadata)
                files.append(metadata)
        if figures:
            fig_keys = [fig_metadata["key"] for fig_metadata in self.get("figures", [])]
            for fig in figures:
                metadata = self._add_file(**fig)
                if metadata not in fig_keys:
                    builder.add_figure(**metadata)
                files.append(metadata)
        super().update(builder.record)
        return files

    def _download_file_from_url(self, url):
        """Downloads file and calculates hash for it
        if everythong is ok then adds it to files in current record

        Args:
            url (str): Local or remote url/filepath

        Returns: key(sha-1) of downloaded file

        Example:
            >>> self._download_file_from_url('http://example.com/url_to_file.pdf')
            '207611e7bf8a83f0739bb2e16a1a7cf0d585fb5f'
        """
        stream = fsopen(url, mode="rb")
        # TODO: change to stream.read() when fs will be updated to > 2.0
        # As HTTPOpener is not working with size = -1
        # (and read() method sets this size as default)
        # This is workaround until we will update to fs >2.0
        data = stream._f.wrapped_file.read()
        key = hashlib.sha1(data).hexdigest()
        if key not in self.files.keys:
            self.files[key] = BytesIO(data)
        return key

    def _download_file_flom_lcoal_storage(self, url, **kwargs):
        """Opens local file with ObjectVersion API, callculates it's hash and returns
        hash of the file
        Args:
            url (str): Local url which starts with /api/files/

        Returns: key(sha-1) of downloaded file
        Example:
            >>> url = '/api/files/261926f6-4923-458e-adb0/207611e7bf8a83f0739bb2e'
            >>> self._download_file_flom_lcoal_storage(url)
                '207611e7bf8a83f0739bb2e'
        """
        url_splited = url.split("/")
        file = ObjectVersion.get(bucket=url_splited[-2], key=url_splited[-1])
        if not file:
            raise FileNotFoundError(
                "{url} is not a valid file in local storage!".format(url=url)
            )
        data = file.file.storage().open().read()
        file.file.storage().close()
        key = hashlib.sha1(data)
        if key not in self.files.keys:
            file.copy(bucket=self.files.bucket.id, key=key)
        return key

    def _find_and_add_file(self, url, original_url):
        """Finds proper url (url or original_url) and method to download file.
        Args:
            url (str): Local or remote path to a file
            original_url (str): Local or remote path to a file

        Returns: Key of downloaded file, or None if file was not found

        """
        urls = [_url for _url in [url, original_url] if _url]
        key = None
        for _url in urls:
            try:
                if _url.startswith("/api/files/"):
                    key = self._download_file_flom_lcoal_storage(_url)
            except FileNotFoundError:
                pass
        if not key:
            for _url in urls:
                try:
                    if _url.startswith("http"):
                        key = self._download_file_from_url(_url)
                except ResourceNotFoundError:
                    pass
        return key

    def _add_file(self, url, original_url=None, filename=None, **kwargs):
        """Downloads file from url and saves it with `filename` as a proper name
        Args:
            url: Url to a file, or to local api
            filename: Proper name of the file.
                If not provided, last part of URL will be used as a filename
            original_url: URL from which this document was downloaded
            **kwargs: Additional metadata for the file:
                'description': works for documents and figures
                'fulltext': works for documents only
                'hidden': works for documents only
                'material': works for documents and figures
                'caption': works for facets only
        Returns: Metadata for file

        """
        key = self._find_and_add_file(url, original_url)
        if not key:
            raise FileNotFoundError(
                "File `{url}|{original_url}` not found".format(
                    url=url, original_url=original_url
                )
            )
        if not filename and original_url:
            filename = original_url.split("/")[-1]
        elif not filename:
            filename = url.split("/")[-1]

        metadata = kwargs
        metadata["key"] = key

        if not original_url:
            metadata["original_url"] = url
        else:
            metadata["original_url"] = original_url

        metadata["filename"] = filename
        if "fulltext" not in metadata:
            metadata["fulltext"] = True
        if "hidden" not in metadata:
            metadata["hidden"] = False

        file_path = "/api/files/{bucket}/{key}".format(
            bucket=self.files[key].bucket_id, key=key
        )

        metadata["url"] = file_path
        return metadata
