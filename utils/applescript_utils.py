# utils/applescript_utils.py
# -*- coding: utf-8 -*-

from __future__ import annotations


def applescript_escape(value: str | None) -> str:
    """
    Escape a Python string for safe inclusion inside AppleScript double quotes.
    Replaces newlines with spaces and escapes backslashes and quotes.
    """
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\r", " ").replace("\n", " ")
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    return text
