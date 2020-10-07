# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

import structlog
from inspire_utils.helpers import force_list
from inspire_utils.record import get_value
from invenio_pidstore.errors import PIDAlreadyExists, PIDDoesNotExistError
from invenio_pidstore.models import PersistentIdentifier, PIDStatus

from inspirehep.pidstore.api.utils import get_pid_from_record_uri
from inspirehep.pidstore.errors import MissingSchema
from inspirehep.pidstore.providers.external import InspireExternalIdProvider
from inspirehep.pidstore.providers.recid import InspireRecordIdProvider
from inspirehep.utils import flatten_list

from ..errors import PIDAlreadyExistsError

LOGGER = structlog.getLogger()


class Minter:

    provider = InspireExternalIdProvider
    object_type = "rec"
    pid_type = None
    pid_value_path = None

    def __init__(self, object_uuid, data):
        self.data = data
        self.object_uuid = object_uuid

    def validate(self):
        if "$schema" not in self.data:
            raise MissingSchema

    def get_pid_values(self):
        pid_values = get_value(self.data, self.pid_value_path, default=[])
        if not isinstance(pid_values, (tuple, list)):
            pid_values = [str(pid_value) for pid_value in force_list(pid_values)]
        return set(pid_values)

    def get_all_pids_from_record_represented_by_pid(self, pid_value):
        result = PersistentIdentifier.query.filter(
            PersistentIdentifier.pid_type == self.pid_type,
            PersistentIdentifier.pid_value == pid_value,
        ).one_or_none()
        if result and result.object_uuid != self.object_uuid:
            all_pids = flatten_list(
                PersistentIdentifier.query.with_entities("pid_value")
                .filter(
                    PersistentIdentifier.pid_type == self.pid_type,
                    PersistentIdentifier.object_uuid == result.object_uuid,
                )
                .all()
            )
            return all_pids
        return None

    def get_pids_to_retake(self):
        pid_values = []
        if "deleted_records" in self.data:
            ref_path = "deleted_records.$ref"
            for rec in flatten_list(get_value(self.data, ref_path, [])):
                pid_type, pid_value = get_pid_from_record_uri(rec)
                if pid_type == self.pid_type:
                    pids = self.get_all_pids_from_record_represented_by_pid(pid_value)
                    if pids:
                        pid_values.extend(pids)
        return set(pid_values)

    @property
    def pid_value(self):
        """Returns pid_value or list of pid values

        Required by InvenioRecordsREST POST view.
        """
        return self.get_pid_values()

    def create(self, pid_value, **kwargs):
        LOGGER.info(
            "Minting",
            pid_type=self.pid_type,
            recid=pid_value,
            object_type=self.object_type,
            object_uuid=str(self.object_uuid),
            pid_provider=self.provider.pid_provider,
        )
        try:
            return self.provider.create(
                pid_type=self.pid_type,
                pid_value=pid_value,
                object_type=self.object_type,
                object_uuid=self.object_uuid,
                **kwargs
            )
        except PIDAlreadyExists as e:
            raise PIDAlreadyExistsError(e.pid_type, e.pid_value) from e

    @classmethod
    def mint(cls, object_uuid, data):
        minter = cls(object_uuid, data)
        minter.validate()
        for pid_value in minter.get_pid_values():
            minter.create(pid_value)
        for pid_value in minter.get_pids_to_retake():
            minter.create(pid_value, force=True)
        return minter

    @classmethod
    def update(cls, object_uuid, data, delete_missing=True):
        minter = cls(object_uuid, data)
        minter.validate()
        pids_in_db = minter.get_all_pidstore_pids()
        pids_requested = minter.get_pid_values()
        pids_to_retake = minter.get_pids_to_retake()
        for pid_value in pids_to_retake - pids_in_db:
            minter.create(pid_value, force=True)

        if delete_missing:
            pids_to_delete = pids_in_db - pids_requested - pids_to_retake
            if pids_to_delete:
                minter.delete(object_uuid, None, pids_to_delete)

        pids_to_create = pids_requested - pids_in_db
        for pid_value in pids_to_create:
            minter.create(pid_value)

        return minter

    @classmethod
    def delete(cls, object_uuid, data, pids_to_delete=None):
        LOGGER.info(
            "Some pids for record are going to be removed",
            pids_to_delete=pids_to_delete or "all",
            object_uuid=object_uuid,
            pid_type=cls.pid_type,
        )
        minter = cls(object_uuid, data)
        if pids_to_delete is None:
            pids_to_delete = minter.get_all_pidstore_pids()
        for pid_value in pids_to_delete:
            minter.provider.get(pid_value, minter.pid_type).delete()
        return minter

    def get_all_pidstore_pids(self):
        return {
            result[0]
            for result in PersistentIdentifier.query.with_entities(
                PersistentIdentifier.pid_value
            )
            .filter_by(pid_type=self.pid_type or self.provider.pid_type)
            .filter_by(object_uuid=self.object_uuid)
            .filter_by(pid_provider=self.provider.pid_provider)
            .filter(PersistentIdentifier.status != PIDStatus.DELETED)
        }


class ControlNumberMinter(Minter):

    pid_value_path = "control_number"
    provider = InspireRecordIdProvider

    @classmethod
    def mint(cls, object_uuid, data):
        minter = cls(object_uuid, data)
        minter.validate()

        pid_value = None
        if "control_number" in data:
            pid_value = data["control_number"]

        record_id_provider = minter.create(str(pid_value) if pid_value else None)
        data["control_number"] = int(record_id_provider.pid.pid_value)

        return minter
