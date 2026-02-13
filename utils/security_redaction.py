# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Pattern

# Placeholder markers accepted in templates/examples but invalid for runtime secrets.
_PLACEHOLDER_RE: Pattern[str] = re.compile(
    r"(replace_with|your[_-]?(key|token|secret)|dummy|example|changeme|xxx|abc123)",
    re.IGNORECASE,
)

# Broad redaction patterns for logs/diagnostic exports.
_REDACTION_PATTERNS: list[Pattern[str]] = [
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\b(\s*[:=]\s*)([^\s,;\"']+)"),
    re.compile(r"(?i)\b(authorization\s*:\s*bearer\s+)([A-Za-z0-9\-_\.=+/]{8,})"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:\+?\d[\d\s().-]{7,}\d)\b"),
]


def is_placeholder_secret(value: str | None) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return True
    return bool(_PLACEHOLDER_RE.search(raw))


def redact_sensitive_text(text: str | None) -> str:
    out = str(text or "")
    if not out:
        return ""

    # Assignment-like secrets: preserve key label, redact value.
    out = _REDACTION_PATTERNS[0].sub(r"\1\2***REDACTED***", out)
    # Authorization bearer token: preserve prefix.
    out = _REDACTION_PATTERNS[1].sub(r"\1***REDACTED***", out)
    # Emails and phones.
    out = _REDACTION_PATTERNS[2].sub("***REDACTED_EMAIL***", out)
    out = _REDACTION_PATTERNS[3].sub("***REDACTED_PHONE***", out)
    return out
