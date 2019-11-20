# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

from flask_alembic import Alembic
from sqlalchemy import text


def test_downgrade(base_app, db_alembic, es):
    alembic = Alembic(base_app)
    alembic.downgrade("e5e43ad8f861")
    assert "enum_conference_to_literature_relationship_type" not in _get_custom_enums(
        db_alembic
    )
    assert "conference_literature" not in _get_table_names(db_alembic)
    assert "ix_conference_literature_literature_uuid" not in _get_indexes(
        "conference_literature", db_alembic
    )
    assert "ix_conference_literature_conference_uuid" not in _get_indexes(
        "conference_literature", db_alembic
    )

    alembic.downgrade(target="788a3a61a635")
    assert "ix_files_object_key_head" not in _get_indexes("files_object", db_alembic)

    assert "idx_pid_provider" not in _get_indexes("pidstore_pid", db_alembic)

    alembic.downgrade(target="dc1ae5abe9d6")

    assert "idx_pid_provider" in _get_indexes("pidstore_pid", db_alembic)

    alembic.downgrade(target="c6570e49b7b2")

    assert "records_citations" in _get_table_names(db_alembic)
    assert "ix_records_citations_cited_id" in _get_indexes(
        "records_citations", db_alembic
    )

    alembic.downgrade(target="5ce9ef759ace")

    assert "record_citations" in _get_table_names(db_alembic)
    assert "records_citations" not in _get_table_names(db_alembic)
    assert "ix_records_citations_cited_id" not in _get_indexes(
        "record_citations", db_alembic
    )
    assert "idx_citations_cited" in _get_indexes("record_citations", db_alembic)

    alembic.downgrade(target="b646d3592dd5")
    assert "ix_legacy_records_mirror_last_updated" not in _get_indexes(
        "legacy_records_mirror", db_alembic
    )
    assert "ix_legacy_records_mirror_valid_collection" not in _get_indexes(
        "legacy_records_mirror", db_alembic
    )
    assert "legacy_records_mirror" not in _get_table_names(db_alembic)

    alembic.downgrade(target="7be4c8b5c5e8")
    assert "idx_citations_cited" not in _get_indexes("record_citations", db_alembic)

    assert "record_citations" not in _get_table_names(db_alembic)

    # test 7be4c8b5c5e8
    alembic.downgrade(target="b5be5fda2ee7")
    alembic.downgrade(1)

    assert "ix_records_metadata_json_referenced_records_2_0" not in _get_indexes(
        "records_metadata", db_alembic
    )

    assert "workflows_record_sources" not in _get_table_names(db_alembic)
    assert "workflows_pending_record" not in _get_table_names(db_alembic)
    assert "crawler_workflows_object" not in _get_table_names(db_alembic)
    assert "crawler_job" not in _get_table_names(db_alembic)
    assert "workflows_audit_logging" not in _get_table_names(db_alembic)
    assert "workflows_buckets" not in _get_table_names(db_alembic)
    assert "workflows_object" not in _get_table_names(db_alembic)
    assert "workflows_workflow" not in _get_table_names(db_alembic)

    assert "ix_crawler_job_job_id" not in _get_indexes("crawler_job", db_alembic)
    assert "ix_crawler_job_scheduled" not in _get_indexes("crawler_job", db_alembic)
    assert "ix_crawler_job_spider" not in _get_indexes("crawler_job", db_alembic)
    assert "ix_crawler_job_workflow" not in _get_indexes("crawler_job", db_alembic)
    assert "ix_workflows_audit_logging_object_id" not in _get_indexes(
        "workflows_audit_logging", db_alembic
    )
    assert "ix_workflows_audit_logging_user_id" not in _get_indexes(
        "workflows_audit_logging", db_alembic
    )
    assert "ix_workflows_object_data_type" not in _get_indexes(
        "workflows_object", db_alembic
    )
    assert "ix_workflows_object_id_parent" not in _get_indexes(
        "workflows_object", db_alembic
    )
    assert "ix_workflows_object_id_workflow" not in _get_indexes(
        "workflows_object", db_alembic
    )
    assert "ix_workflows_object_status" not in _get_indexes(
        "workflows_object", db_alembic
    )


def test_upgrade(base_app, db_alembic, es):
    alembic = Alembic(base_app)
    # go down to first migration
    alembic.downgrade(target="b5be5fda2ee7")

    alembic.upgrade(target="7be4c8b5c5e8")

    assert "workflows_record_sources" in _get_table_names(db_alembic)
    assert "workflows_pending_record" in _get_table_names(db_alembic)
    assert "crawler_workflows_object" in _get_table_names(db_alembic)
    assert "crawler_job" in _get_table_names(db_alembic)
    assert "workflows_audit_logging" in _get_table_names(db_alembic)
    assert "workflows_buckets" in _get_table_names(db_alembic)
    assert "workflows_object" in _get_table_names(db_alembic)
    assert "workflows_workflow" in _get_table_names(db_alembic)

    assert "ix_crawler_job_job_id" in _get_indexes("crawler_job", db_alembic)
    assert "ix_crawler_job_scheduled" in _get_indexes("crawler_job", db_alembic)
    assert "ix_crawler_job_spider" in _get_indexes("crawler_job", db_alembic)
    assert "ix_crawler_job_workflow" in _get_indexes("crawler_job", db_alembic)
    assert "ix_workflows_audit_logging_object_id" in _get_indexes(
        "workflows_audit_logging", db_alembic
    )
    assert "ix_workflows_audit_logging_user_id" in _get_indexes(
        "workflows_audit_logging", db_alembic
    )
    assert "ix_workflows_object_data_type" in _get_indexes(
        "workflows_object", db_alembic
    )
    assert "ix_workflows_object_id_parent" in _get_indexes(
        "workflows_object", db_alembic
    )
    assert "ix_workflows_object_id_workflow" in _get_indexes(
        "workflows_object", db_alembic
    )
    assert "ix_workflows_object_status" in _get_indexes("workflows_object", db_alembic)

    assert "ix_records_metadata_json_referenced_records_2_0" in _get_indexes(
        "records_metadata", db_alembic
    )

    alembic.upgrade(target="b646d3592dd5")

    assert "idx_citations_cited" in _get_indexes("record_citations", db_alembic)

    assert "record_citations" in _get_table_names(db_alembic)

    alembic.upgrade(target="5ce9ef759ace")

    assert "ix_legacy_records_mirror_last_updated" in _get_indexes(
        "legacy_records_mirror", db_alembic
    )
    assert "ix_legacy_records_mirror_valid_collection" in _get_indexes(
        "legacy_records_mirror", db_alembic
    )
    assert "legacy_records_mirror" in _get_table_names(db_alembic)

    alembic.upgrade(target="c6570e49b7b2")

    assert "records_citations" in _get_table_names(db_alembic)
    assert "record_citations" not in _get_table_names(db_alembic)

    assert "ix_records_citations_cited_id" in _get_indexes(
        "records_citations", db_alembic
    )
    assert "idx_citations_cited" not in _get_indexes("records_citations", db_alembic)

    alembic.upgrade(target="dc1ae5abe9d6")

    assert "idx_pid_provider" in _get_indexes("pidstore_pid", db_alembic)

    alembic.upgrade(target="788a3a61a635")

    assert "idx_pid_provider" not in _get_indexes("pidstore_pid", db_alembic)

    alembic.upgrade(target="e5e43ad8f861")
    assert "ix_files_object_key_head" in _get_indexes("files_object", db_alembic)

    alembic.upgrade(target="f563233434cd")

    assert "conference_literature" in _get_table_names(db_alembic)
    assert "ix_conference_literature_literature_uuid" in _get_indexes(
        "conference_literature", db_alembic
    )
    assert "ix_conference_literature_conference_uuid" in _get_indexes(
        "conference_literature", db_alembic
    )
    assert "enum_conference_to_literature_relationship_type" in _get_custom_enums(
        db_alembic
    )


def _get_indexes(tablename, db_alembic):
    query = text(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE tablename=:tablename
    """
    ).bindparams(tablename=tablename)

    return [el.indexname for el in db_alembic.session.execute(query)]


def _get_sequences(db_alembic):
    query = text(
        """
        SELECT relname
        FROM pg_class
        WHERE relkind='S'
    """
    )

    return [el.relname for el in db_alembic.session.execute(query)]


def _get_table_names(db_alembic):
    return db_alembic.engine.table_names()


def _get_custom_enums(db_alembic):
    query = """ SELECT pg_type.typname AS enumtype,  
        pg_enum.enumlabel AS enumlabel 
        FROM pg_type  
        JOIN pg_enum  
            ON pg_enum.enumtypid = pg_type.oid;"""
    return set([a[0] for a in db_alembic.session.execute(query)])
