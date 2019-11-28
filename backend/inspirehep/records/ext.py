# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

"""Flask extension for inspirehep."""

import boto3
from botocore.exceptions import UnknownServiceError
from flask import _app_ctx_stack as stack
from flask import current_app


class InspireRecords(object):
    """inspirehep extension."""

    def __init__(self, app=None):
        """Extension initialization."""
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Flask application initialization."""
        app.extensions["inspirehep-records"] = self
        from inspirehep.records import receivers  # noqa: F401


class Boto3(object):
    """Stores boto3 conectors inside Flask's application context
    for easier handling.

    """

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        app.extensions["inspire-s3"] = self
        app.teardown_appcontext(self.teardown)

    def connect(self):
        """Initiate s3 connection"""
        hostname = current_app.config.get("S3_HOSTNAME")
        session_params = {
            "aws_access_key_id": current_app.config.get("S3_ACCESS_KEY"),
            "aws_secret_access_key": current_app.config.get("S3_SECRET_KEY"),
        }
        session = boto3.session.Session(**session_params)
        service = "s3"
        try:
            connections = {}

            # Get session params and override them with kwargs
            # `profile_name` cannot be passed to clients and resources
            kwargs = session_params.copy()
            kwargs["endpoint_url"] = hostname
            # Create resource or client
            if service in session.get_available_resources():
                connections.update({service: session.resource(service, **kwargs)})
            else:
                connections.update({service: session.client(service, **kwargs)})
        except UnknownServiceError:
            raise
        return connections

    def teardown(self, exception):
        ctx = stack.top
        if hasattr(ctx, "boto3_cns"):
            for c in ctx.boto3_cns:
                con = ctx.boto3_cns[c]
                if hasattr(con, "close") and callable(con.close):
                    ctx.boto3_cns[c].close()

    @property
    def resources(self):
        c = self.connections
        return {k: v for k, v in c.items() if hasattr(c[k].meta, "client")}

    @property
    def clients(self):
        """
        Get all clients (with and without associated resources)
        """
        clients = {}
        for k, v in self.connections.items():
            if hasattr(v.meta, "client"):  # has boto3 resource
                clients[k] = v.meta.client
            else:  # no boto3 resource
                clients[k] = v
        return clients

    @property
    def s3_client(self):
        return self.clients["s3"]

    @property
    def connections(self):
        ctx = stack.top
        if ctx is not None:
            if not hasattr(ctx, "boto3_cns"):
                ctx.boto3_cns = self.connect()
            return ctx.boto3_cns
