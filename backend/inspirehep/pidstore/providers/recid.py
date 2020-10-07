# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.


import requests
import structlog
from flask import current_app
from invenio_pidstore.errors import PIDAlreadyExists
from invenio_pidstore.models import PersistentIdentifier, PIDStatus, RecordIdentifier
from sqlalchemy.exc import IntegrityError

from inspirehep.pidstore.errors import PIDAlreadyExistsError
from inspirehep.pidstore.providers.base import InspireBaseProvider

LOGGER = structlog.getLogger()


def get_next_pid_from_legacy():
    """Reserve the next pid on legacy.
    Sends a request to a legacy instance to reserve the next available
    identifier, and returns it to the caller.
    """
    headers = {"User-Agent": "invenio_webupload"}

    url = current_app.config.get("LEGACY_PID_PROVIDER")
    next_pid = requests.get(url, headers=headers).json()
    return next_pid


class InspireRecordIdProvider(InspireBaseProvider):
    """Record identifier provider."""

    pid_type = None

    pid_provider = "recid"

    default_status = PIDStatus.RESERVED

    @classmethod
    def create(
        cls,
        object_type=None,
        object_uuid=None,
        pid_type=None,
        force=False,
        pid_value=None,
        status=None,
        **kwargs
    ):
        """Create a new record identifier."""
        pid_value = str(pid_value) if pid_value else None
        if pid_value is None:
            if current_app.config.get("LEGACY_PID_PROVIDER"):
                pid_value = str(get_next_pid_from_legacy())
                LOGGER.info("Control number from legacy", recid=pid_value)
                RecordIdentifier.insert(pid_value)
            else:
                pid_value = str(RecordIdentifier.next())
                LOGGER.info("Control number from RecordIdentifier", recid=pid_value)
        else:
            LOGGER.info("Control number provided", recid=pid_value, force=force)

            if not RecordIdentifier.query.filter_by(recid=pid_value).one_or_none():
                RecordIdentifier.insert(pid_value)

        status = cls.default_status
        if object_type and object_uuid:
            status = PIDStatus.REGISTERED
        pid_from_db = PersistentIdentifier.query.filter_by(
            pid_value=pid_value, pid_provider=cls.pid_provider, pid_type=pid_type
        ).one_or_none()
        if pid_from_db and force:
            pid_from_db.object_uuid = object_uuid
            pid_from_db.status = status
        elif pid_from_db:
            if pid_from_db.object_uuid != object_uuid:
                raise PIDAlreadyExists(cls.pid_type, pid_value)
            else:
                pid_from_db.status = status

        else:
            return super().create(
                object_type=object_type,
                object_uuid=object_uuid,
                pid_type=pid_type,
                pid_value=pid_value,
                status=status,
                **kwargs
            )
        return cls(pid_from_db)
