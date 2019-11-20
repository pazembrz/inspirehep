# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

"""INSPIRE module that adds more fun to the platform."""
import datetime
import os
import random
from functools import partial

import elasticsearch
import pytest
from click.testing import CliRunner
from flask import current_app
from flask.cli import ScriptInfo
from helpers.factories.models.base import BaseFactory
from helpers.factories.models.migrator import LegacyRecordsMirrorFactory
from helpers.factories.models.pidstore import PersistentIdentifierFactory
from helpers.factories.models.records import RecordMetadataFactory
from helpers.factories.models.user_access_token import AccessTokenFactory, UserFactory
from helpers.providers.faker import faker
from pytest_invenio.fixtures import _es_create_indexes, _es_delete_indexes
from redis import StrictRedis

from inspirehep.factory import create_app as inspire_create_app
from inspirehep.records.api import InspireRecord
from inspirehep.records.fixtures import (
    init_default_storage_path,
    init_records_files_storage_path,
)


@pytest.fixture(scope="module")
def app_config(app_config):
    # add extra global config if you would like to customize the config
    # for a specific test you can chagne create fixture per-directory
    # using ``conftest.py`` or per-file.
    app_config["DEBUG"] = False
    app_config["JSONSCHEMAS_HOST"] = "localhost:5000"
    app_config["SERVER_NAME"] = "localhost:5000"
    return app_config


@pytest.fixture(scope="module")
def db_uri(instance_path):
    """Database URI (defaults to an SQLite datbase in the instance path).
    Scope: module
    The database can be overwritten by setting the ``SQLALCHEMY_DATABASE_URI``
    environment variable to a SQLAlchemy database URI.
    """
    if "SQLALCHEMY_DATABASE_URI" in os.environ:
        yield os.environ["SQLALCHEMY_DATABASE_URI"]
    else:
        yield "postgresql+psycopg2://inspirehep:inspirehep@localhost/inspirehep"


@pytest.fixture(scope="function")
def enable_files(base_app):
    original_value = base_app.config.get("FEATURE_FLAG_ENABLE_FILES")
    base_app.config["FEATURE_FLAG_ENABLE_FILES"] = True
    yield base_app
    base_app.config["FEATURE_FLAG_ENABLE_FILES"] = original_value


@pytest.fixture(scope="function")
def disable_files(base_app):
    original_value = base_app.config.get("FEATURE_FLAG_ENABLE_FILES")
    base_app.config["FEATURE_FLAG_ENABLE_FILES"] = False
    yield base_app
    base_app.config["FEATURE_FLAG_ENABLE_FILES"] = original_value


@pytest.fixture(scope="module")
def create_app():
    return inspire_create_app


@pytest.fixture(scope="module")
def inspire_database(appctx):
    """Setup database.

    Scope: module

    Normally, tests should use the function-scoped :py:data:`db` fixture
    instead. This fixture takes care of creating the database/tables and
    removing the tables once tests are done.
    """
    _start = datetime.datetime.now()
    from invenio_db import db as db_
    from sqlalchemy_utils.functions import create_database, database_exists

    if not database_exists(str(db_.engine.url)):
        create_database(str(db_.engine.url))
    db_.create_all()
    db_.session.rollback()
    db_.session.remove()
    all_tables = db_.metadata.tables
    for table_name, table_object in all_tables.items():
        db_.session.execute(f"ALTER TABLE {table_name} DISABLE TRIGGER ALL;")
        db_.session.execute(table_object.delete())
        db_.session.execute(f"ALTER TABLE {table_name} ENABLE TRIGGER ALL;")
    db_.session.commit()
    yield db_
    _start = datetime.datetime.now()
    db_.session.remove()


@pytest.fixture(scope="function")
def db_alembic(database):
    yield database


@pytest.fixture(scope="function")
def db_(inspire_database):
    """Creates a new database session for a test.
    Scope: function
    You must use this fixture if your test connects to the database. The
    fixture will set a save point and rollback all changes performed during
    the test (this is much faster than recreating the entire database).
    """
    _start = datetime.datetime.now()
    import sqlalchemy as sa

    connection = inspire_database.engine.connect()
    transaction = connection.begin()

    options = dict(bind=connection, binds={})
    session = inspire_database.create_scoped_session(options=options)

    session.begin_nested()

    # FIXME: attach session to all factories
    # https://github.com/pytest-dev/pytest-factoryboy/issues/11#issuecomment-130521820
    BaseFactory._meta.sqlalchemy_session = session
    RecordMetadataFactory._meta.sqlalchemy_session = session
    PersistentIdentifierFactory._meta.sqlalchemy_session = session
    LegacyRecordsMirrorFactory._meta.sqlalchemy_session = session
    # `session` is actually a scoped_session. For the `after_transaction_end`
    # event, we need a session instance to listen for, hence the `session()`
    # call.
    @sa.event.listens_for(session(), "after_transaction_end")
    def restart_savepoint(sess, trans):
        if trans.nested and not trans._parent.nested:
            session.expire_all()
            session.begin_nested()

    old_session = inspire_database.session
    inspire_database.session = session

    yield inspire_database
    _start = datetime.datetime.now()
    session.remove()
    transaction.rollback()
    connection.close()
    inspire_database.session = old_session


@pytest.fixture(scope="function")
def db(db_):
    _start = datetime.datetime.now()
    init_default_storage_path()
    init_records_files_storage_path()
    yield db_


@pytest.fixture(scope="function")
def es_clear(es):
    """Clear Elasticsearch indices after test finishes (function scope).

    Scope: function

    This fixture rollback any changes performed to the indexes during a test,
    in order to leave Elasticsearch in a clean state for the next test.
    """
    from invenio_search import current_search, current_search_client

    es.indices.refresh()
    for indice in es.indices.stats()["indices"].keys():
        try:
            es.delete_by_query(indice, "{}")
        except elasticsearch.exceptions.RequestError:
            # There is ES error on version 5, when you try to remove records
            # using delete_by_query and record have internal visioning and
            # it's current version is 0 it's failing. So in this case only way is to
            # remove index but invenio 1.1.1 allows to remove all indexes only
            # After upgrading to invenio 1.2 we will be able
            # to remove only specified index
            _es_delete_indexes(current_search)
            _es_create_indexes(current_search, current_search_client)
            print("==============================================================")
            break
    es.indices.refresh()

    yield es


@pytest.fixture(scope="function")
def create_record(base_app, db, es_clear):
    """Fixture to create record from the application level.

    Examples:

        def test_with_record(base_app, create_record)
            data = {'control_number': 123}
            record = create_record(
                'lit',
                data=data,
            )
    """

    def _create_record(record_type, data=None):
        accepted_record_types = base_app.config["PID_TYPE_TO_INDEX"].keys()

        if record_type not in accepted_record_types:
            raise ValueError(f"{record_type} is not supported")
        index = base_app.config["PID_TYPE_TO_INDEX"][record_type]
        record_data = faker.record(record_type, data=data)
        record = InspireRecord.create(record_data)
        record._indexing = record.index(delay=False)
        es_clear.indices.refresh(index)
        return record

    return _create_record


@pytest.fixture(scope="function")
def create_record_factory(base_app, db, es_clear):
    """Fixtures to create factory record.

    Examples:

        def test_with_record(base_app, create_record_factory)
            record = create_record_factory(
                'lit',
                with_pid=True,
                with_index=False,
            )
    """

    def _create_record_factory(
        record_type,
        data=None,
        with_pid=True,
        with_indexing=False,
        with_validation=False,
    ):
        control_number = random.randint(1, 2_147_483_647)
        if with_validation:
            data = faker.record(record_type, data)
        record = RecordMetadataFactory(
            record_type=record_type, data=data, control_number=control_number
        )

        if with_pid:
            record._persistent_identifier = PersistentIdentifierFactory(
                object_uuid=record.id,
                pid_type=record_type,
                pid_value=record.json["control_number"],
            )

        if with_indexing:
            index = base_app.config["PID_TYPE_TO_INDEX"][record_type]
            record._index = es_clear.index(
                index=index,
                id=str(record.id),
                doc_type=index.split("-")[-1],
                body=record.json,
                params={},
            )
            es_clear.indices.refresh(index)
        return record

    return _create_record_factory


@pytest.fixture(scope="function")
def create_pidstore(db):
    def _create_pidstore(object_uuid, pid_type, pid_value):
        return PersistentIdentifierFactory(
            object_uuid=object_uuid, pid_type=pid_type, pid_value=pid_value
        )

    return _create_pidstore


@pytest.fixture(scope="function")
def api_client(base_app):
    """Test client for the base application fixture.
    Scope: function
    If you need the database and search indexes initialized, simply use the
    Pytest-Flask fixture ``client`` instead. This fixture is mainly useful if
    you need a test client without needing to initialize both the database and
    search indexes.
    """
    with base_app.test_client() as client:
        yield client


@pytest.fixture(scope="function")
def create_user_and_token(base_app, db, es):
    """Fixtures to create user and authentication token for given user.

    Examples:

        def test_needs_authentication(base_app, create_user_and_token)
            user = create_user_and_token()
    """

    def _create_user_and_token():
        return AccessTokenFactory()

    return _create_user_and_token


@pytest.fixture(scope="function")
def create_user(base_app, db, es):
    """Fixture to create user.

    Examples:

        def test_needs_user(base_app, create_user)
            user = create_user()
    """

    def _create_user(role="user", orcid=None, email=None):
        return UserFactory(role=role, orcid=orcid, email=email)

    return _create_user


@pytest.fixture
def logout():
    """
    Fixture to logout the current user.

    Example:
        user = create_user('cataloger')
        login_user_via_session(api_client, email=cataloger@cat.com)
        . . .
        logout(api_client)
    """

    def _logout(client):
        with client.session_transaction() as sess:
            if sess["user_id"]:
                del sess["user_id"]

    return _logout


@pytest.fixture(scope="function")
def app_cli_runner(appctx):
    """Click CLI runner inside the Flask application."""
    runner = CliRunner()
    obj = ScriptInfo(create_app=lambda info: current_app)
    runner._invoke = runner.invoke
    runner.invoke = partial(runner.invoke, obj=obj)
    return runner


@pytest.fixture(scope="function")
def redis(base_app):
    redis_url = current_app.config.get("CACHE_REDIS_URL")
    r = StrictRedis.from_url(redis_url, decode_responses=True)
    r.flushall()

    yield r
