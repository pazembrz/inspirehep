# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.
import structlog
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_pidstore.models import PersistentIdentifier
from invenio_pidstore.providers.base import BaseProvider
from sqlalchemy.orm.exc import NoResultFound

LOGGER = structlog.getLogger()


class InspireBaseProvider(BaseProvider):
    def __init__(self, pid, *args, **kwargs):
        return super().__init__(pid)

    @classmethod
    def get(cls, pid_value, pid_type=None, object_uuid=None, **kwargs):
        """Get a persistent identifier for this provider.
        Use object_uuid if it's provided to limit PIDs to specified record

        Args:
            pid_value(str): Persistent identifier value.
            pid_type(str): Persistent identifier type.
            object_uuid(str): Get pid only if it's assigned to this object.
        """
        query = PersistentIdentifier.query.filter_by(
            pid_value=pid_value,
            pid_type=pid_type or cls.pid_type,
            pid_provider=cls.pid_provider,
        )
        if object_uuid:
            query = query.filter_by(object_uuid=object_uuid)
        try:
            return cls(query.one(), **kwargs)
        except NoResultFound:
            raise PIDDoesNotExistError(pid_type, pid_value)
