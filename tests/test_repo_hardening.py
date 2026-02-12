# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def test_gitignore_protects_env_files():
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert ".env" in text
    assert ".env.*" in text


def test_env_example_contains_required_airfrance_keys():
    env_example = Path(".env.example")
    assert env_example.exists()
    content = env_example.read_text(encoding="utf-8")
    required = [
        "AF_API_KEY=",
        "AF_MAX_CALLS_PER_DAY=",
        "AF_MIN_DELAY_SECONDS=",
        "AF_TIME_ORIGIN_TYPE=",
    ]
    for key in required:
        assert key in content
