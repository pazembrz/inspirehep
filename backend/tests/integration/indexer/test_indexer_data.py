# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.
from copy import deepcopy

from helpers.utils import create_record, es_search
from invenio_search import current_search
from marshmallow import utils

from inspirehep.search.api import DataSearch


def test_index_data_record(inspire_app):
    record = create_record("dat")

    expected_count = 1
    expected_metadata = deepcopy(record)
    expected_metadata["_created"] = utils.isoformat(record.created)
    expected_metadata["_updated"] = utils.isoformat(record.updated)

    response = es_search("records-data")

    assert response["hits"]["total"]["value"] == expected_count
    assert response["hits"]["hits"][0]["_source"] == expected_metadata


def test_indexer_deletes_record_from_es(inspire_app):
    record = create_record("dat")

    record["deleted"] = True
    record.index(delay=False)
    current_search.flush_and_refresh("records-data")

    expected_records_count = 0

    record_lit_es = DataSearch().get_record(str(record.id)).execute().hits
    assert expected_records_count == len(record_lit_es)
