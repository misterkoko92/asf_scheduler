# -*- coding: utf-8 -*-
from __future__ import annotations

from utils.applescript_utils import applescript_escape


def test_applescript_escape_quotes_and_backslashes():
    assert applescript_escape('a"b') == 'a\\"b'
    assert applescript_escape("a\\b") == "a\\\\b"


def test_applescript_escape_newlines():
    assert applescript_escape("a\nb") == "a b"
    assert applescript_escape("a\rb") == "a b"
