# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

"""INSPIRE module that adds more fun to the platform."""


from helpers.factories.models.records import RecordMetadataFactory
from invenio_pidstore.models import PIDStatus

from inspirehep.pidstore.providers.recid import InspireRecordIdProvider


def test_provider_without_pid_value(inspire_app):
    record = RecordMetadataFactory()

    provide = {"object_type": "rec", "object_uuid": record.id, "pid_type": "pid"}
    provider = InspireRecordIdProvider.create(**provide)

    assert provider.pid.pid_value
    assert "pid" == provider.pid.pid_type
    assert PIDStatus.REGISTERED == provider.pid.status


def test_provider_with_pid_value(inspire_app):
    record = RecordMetadataFactory()

    provide = {
        "object_type": "rec",
        "object_uuid": record.id,
        "pid_type": "pid",
        "pid_value": 1,
    }
    provider = InspireRecordIdProvider.create(**provide)

    assert provider.pid.pid_value == "1"
    assert "pid" == provider.pid.pid_type
    assert PIDStatus.REGISTERED == provider.pid.status


def test_provider_reclaims_other_record_pid(inspire_app):
    record = RecordMetadataFactory()
    provide = {"object_type": "rec", "object_uuid": record.id, "pid_type": "pid"}
    provider = InspireRecordIdProvider.create(**provide)

    record2 = RecordMetadataFactory()
    provide["object_uuid"] = record2.id
    provide["pid_value"] = provider.pid.pid_value
    provide["force"] = True

    provider2 = InspireRecordIdProvider.create(**provide)

    assert provider2.pid.id == provider.pid.id
    assert provider2.pid.object_uuid == record2.id
    assert provider2.pid.status == PIDStatus.REGISTERED
