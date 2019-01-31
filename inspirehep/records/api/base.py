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

import uuid
import hashlib

from flask import current_app
from fs.errors import ResourceNotFoundError
from fs.opener import fsopen
from inspire_dojson.utils import strip_empty_values
from inspire_schemas.api import validate as schema_validate
from inspire_schemas.builders import LiteratureBuilder
from invenio_db import db
from invenio_files_rest.models import Bucket, Location, ObjectVersion
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.models import PersistentIdentifier, RecordIdentifier
from invenio_records.models import RecordMetadata
from invenio_records_files.api import Record
from invenio_records_files.models import RecordsBuckets
from sqlalchemy import cast, not_, or_, type_coerce
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

    def _get_bucket(self, location=None, storage_class=None, record_id=None):
        """Allows to retreive bucket for any record(default: self)
        Args:
            location (str): Bucket location
                (default: 'RECORDS_DEFAULT_FILE_LOCATION_NAME') from config
            storage_class (str): Bucket storage class
                (default: 'RECORDS_DEFAULT_STORAGE_CLASS') from config
            record_id (int): record to which bucket is asigned
                (default: self)

        Returns: Bucket found in db for selected location, storage_class and record_id
            If there is no bucket for selected parameters, returns None

        """
        if not storage_class:
            storage_class = current_app.config["RECORDS_DEFAULT_STORAGE_CLASS"]
        if not location:
            location = current_app.config["RECORDS_DEFAULT_FILE_LOCATION_NAME"]
        if not record_id:
            record_id = self.id

        location = Location.get_by_name(location)

        bucket = RecordsBuckets.query.filter(
            RecordsBuckets.record_id == record_id,
            Bucket.default_storage_class == storage_class,
            Bucket.default_location == location.id,
        ).one_or_none()
        return bucket

    def _create_bucket(self, location=None, storage_class=None):
        """Create bucket and return it, if bucket already exists just returns it.
        Overwrites base_class._create_bucket method as it is not implemented

        Args:
            location (str): Bucket location
                (default: 'RECORDS_DEFAULT_FILE_LOCATION_NAME') from config
            storage_class (str): Bucket storage class
                (default: 'RECORDS_DEFAULT_STORAGE_CLASS') from config

        Returns: Bucket for current record, selected location and storage_class
        """
        bucket = self._get_bucket(location, storage_class)
        if not bucket:
            if location is None:
                location = current_app.config["RECORDS_DEFAULT_FILE_LOCATION_NAME"]
            if storage_class is None:
                storage_class = current_app.config["RECORDS_DEFAULT_STORAGE_CLASS"]

            bucket = Bucket.create(location=location, storage_class=storage_class)
        return bucket
