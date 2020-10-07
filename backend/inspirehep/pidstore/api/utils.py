# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.


def get_pid_from_record_uri(uri):
    parts = [part for part in uri.split("/") if part]
    try:
        pid_type = parts[-2][:3]
        pid_value = parts[-1]
    except IndexError:
        return None
    return pid_type, pid_value
