# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.
import json

from inspirehep.search.api import LiteratureSearch


def test_literature_get_records_by_pids_returns_correct_record(
    base_app, db, es_clear, create_record
):
    record1 = create_record("lit")
    record1_control_number = record1["control_number"]
    record2 = create_record("lit")
    record2_control_number = record2["control_number"]
    expected_control_numbers = [record1_control_number, record2_control_number]
    result = LiteratureSearch().get_records_by_pids([("lit", record1_control_number)])
    assert len(result) == 1
    assert (
        json.loads(result[0]._ui_display)["control_number"] == record1["control_number"]
    )

    result = LiteratureSearch().get_records_by_pids(
        [("lit", record1_control_number), ("lit", record2_control_number)]
    )

    assert len(result) == len(expected_control_numbers)
    for rec in result:
        assert rec.to_dict()["control_number"] in expected_control_numbers


def test_empty_literature_search(api_client, db, es_clear, create_record):
    create_record("lit")
    create_record("lit")
    response = api_client.get("api/literature")

    expected_results_count = 2
    assert expected_results_count == len(response.json["hits"]["hits"])


def test_literature_search_with_parameter(api_client, db, es_clear, create_record):
    record1 = create_record("lit")
    create_record("lit")
    record1_control_number = record1["control_number"]
    response = api_client.get(f"api/literature?q={record1_control_number}")

    expected_results_count = 1
    assert expected_results_count == len(response.json["hits"]["hits"])
    assert (
        record1_control_number
        == response.json["hits"]["hits"][0]["metadata"]["control_number"]
    )


def test_empty_authors_search(api_client, db, es_clear, create_record):
    create_record("aut")
    create_record("aut")
    response = api_client.get("api/authors")

    expected_results_count = 2
    assert expected_results_count == len(response.json["hits"]["hits"])


def test_authors_search_with_parameter(api_client, db, es_clear, create_record):
    record1 = create_record("aut")
    create_record("aut")
    record1_control_number = record1["control_number"]
    response = api_client.get(f"api/authors?q={record1_control_number}")

    expected_results_count = 1
    assert expected_results_count == len(response.json["hits"]["hits"])
    assert (
        record1_control_number
        == response.json["hits"]["hits"][0]["metadata"]["control_number"]
    )


def test_empty_jobs_search(api_client, db, es_clear, create_record):
    create_record("job", data={"status": "open"})
    create_record("job", data={"status": "open"})
    create_record("job", data={"status": "closed"})
    response = api_client.get("api/jobs")

    expected_results_count = 2
    assert expected_results_count == len(response.json["hits"]["hits"])


def test_jobs_search_with_parameter(api_client, db, es_clear, create_record):
    record1 = create_record("job", data={"status": "open"})
    create_record("job", data={"status": "open"})
    create_record("job", data={"status": "closed"})
    record1_control_number = record1["control_number"]
    response = api_client.get(f"api/jobs?q={record1_control_number}")

    expected_results_count = 1
    assert expected_results_count == len(response.json["hits"]["hits"])
    assert (
        record1_control_number
        == response.json["hits"]["hits"][0]["metadata"]["control_number"]
    )


def test_empty_conferences_search(api_client, db, es_clear, create_record):
    create_record("con")
    create_record("con")
    response = api_client.get("api/conferences")

    expected_results_count = 2
    assert expected_results_count == len(response.json["hits"]["hits"])


def test_conferences_search_with_parameter(api_client, db, es_clear, create_record):
    record1 = create_record("con")
    create_record("con")
    record1_control_number = record1["control_number"]
    response = api_client.get(f"api/conferences?q={record1_control_number}")

    expected_results_count = 1
    assert expected_results_count == len(response.json["hits"]["hits"])
    assert (
        record1_control_number
        == response.json["hits"]["hits"][0]["metadata"]["control_number"]
    )
