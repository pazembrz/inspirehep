# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

import mock
import pytest

from inspirehep.records.api.mixins import FilesMixin


def test_hash_check():
    correct_hashes = [
        "5b9cc946ba36be6a60d25708a81bb2c105f04c1f",
        "a1301e1ae9c4b2ca1b6cbc30ca7cc0dd2cb072b6",
        "37aa63c77398d954473262e1a0057c1e632eda77",
    ]

    wrong_hashes = ["file_name", "some_file.txt", "other_strange_file_name.pdf"]

    for hash in correct_hashes:
        assert FilesMixin.is_hash(hash) is True
    for wrong_hash in wrong_hashes:
        assert FilesMixin.is_hash(wrong_hash) is False


def test_filename_from_external():
    url = "http://marvel.com/jessicajones.txt"
    expected = "jessicajones.txt"

    assert expected == FilesMixin.find_filename_from_url(url)


def test_filename_from_external_with_invalid_url():
    url = ""
    expected = ""

    assert expected == FilesMixin.find_filename_from_url(url)
