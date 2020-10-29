# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.
import datetime

import structlog
from invenio_db import db
from invenio_pidstore.errors import PIDInvalidAction
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy_utils.models import Timestamp

from inspirehep.pidstore.errors import (
    PidRedirectionMissing,
    WrongPidTypeRedirection,
    WrongRedirectionPidStatus,
)

LOGGER = structlog.getLogger()


class InspireRedirect(db.Model, Timestamp):
    __tablename__ = "inspire_pidstore_redirect"
    __table_args__ = (
        db.Index(
            "ix_inspire_pidstore_redirect_new_record", "new_pid_type", "new_pid_value"
        ),
    )

    original_pid_type = db.Column(db.String(6), nullable=False, primary_key=True)
    original_pid_value = db.Column(db.String(255), nullable=False, primary_key=True)

    new_pid_type = db.Column(db.String(6), nullable=False)
    new_pid_value = db.Column(db.String(255), nullable=False)

    @property
    def new_pid(self):
        return PersistentIdentifier.get(self.new_pid_type, self.new_pid_value)

    @classmethod
    def redirect(cls, old_pid, new_pid):
        """Redirects pid from old_pid to new_pid"""
        if old_pid.pid_type != new_pid.pid_type:
            raise WrongPidTypeRedirection(old_pid, new_pid)

        if (
            not old_pid.is_registered()
            and not old_pid.is_deleted()
            and not old_pid.is_redirected()
        ) or not new_pid.is_registered():
            raise WrongRedirectionPidStatus(old_pid, new_pid)

        current_redirection = cls.query.filter_by(
            original_pid_type=old_pid.pid_type, original_pid_value=old_pid.pid_value
        ).one_or_none()

        if current_redirection:
            if old_pid.status != PIDStatus.REDIRECTED:
                LOGGER.warning(
                    "There is redirection for PID while status is not correct. Trying to fix.",
                    pid_type=old_pid.pid_type,
                    pid_value=old_pid.pid_value,
                    status=old_pid.status,
                )
                old_pid.status = PIDStatus.REDIRECTED
                db.session.add(old_pid)

            if (
                current_redirection.new_pid_type == new_pid.pid_type
                and current_redirection.new_pid_value == new_pid.pid_value
            ):
                LOGGER.info(
                    "Pid already redirected correctly.",
                    old_pid=old_pid,
                    new_pid=new_pid,
                )
            else:
                current_redirection.new_pid_type = new_pid.pid_type
                current_redirection.new_pid_value = new_pid.pid_value
                db.session.add(current_redirection)
        else:
            try:
                with db.session.begin_nested():
                    redirect = cls(
                        original_pid_type=old_pid.pid_type,
                        original_pid_value=old_pid.pid_value,
                        new_pid_type=new_pid.pid_type,
                        new_pid_value=new_pid.pid_value,
                    )
                    db.session.add(redirect)
                    old_pid.status = PIDStatus.REDIRECTED
                    db.session.add(old_pid)
            except IntegrityError as e:
                raise PIDInvalidAction(e)
            except SQLAlchemyError as e:
                LOGGER.exception(
                    "Failed to redirect record", old_pid=old_pid, new_pid=new_pid
                )
                return False
        LOGGER.info("PID redirected successfully", old_pid=old_pid, new_pid=new_pid)
        return True

    @classmethod
    def get_redirect(cls, pid):
        while pid.status == PIDStatus.REDIRECTED:
            pid = cls.get(
                original_pid_type=pid.pid_type, original_pid_value=pid.pid_value
            ).new_pid
        return pid

    def delete(self):
        pid = PersistentIdentifier.get(self.original_pid_type, self.original_pid_value)
        pid.delete()
        db.session.delete(self)

        return True

    @classmethod
    def get(cls, original_pid_type, original_pid_value):
        try:
            return cls.query.filter_by(
                original_pid_type=original_pid_type,
                original_pid_value=original_pid_value,
            ).one()
        except NoResultFound:
            raise PidRedirectionMissing(original_pid_type, original_pid_value)
