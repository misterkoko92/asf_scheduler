# -*- coding: utf-8 -*-
from __future__ import annotations

from utils.security_redaction import is_placeholder_secret, redact_sensitive_text


def test_is_placeholder_secret_detects_common_template_values():
    assert is_placeholder_secret("replace_with_real_key")
    assert is_placeholder_secret("your_token_here")
    assert is_placeholder_secret("dummy_secret_value")
    assert is_placeholder_secret("")
    assert is_placeholder_secret(None)
    assert is_placeholder_secret("   ")
    assert is_placeholder_secret("abc123")


def test_is_placeholder_secret_accepts_non_placeholder_values():
    assert is_placeholder_secret("af_live_7krxvvkty8jn3dcgzuar7wck") is False


def test_redact_sensitive_text_masks_tokens_email_and_phone():
    raw = (
        "API_KEY=supersecretvalue123456\n"
        "Authorization: Bearer ABCDEFGHIJKLMNOPQRSTUV123456\n"
        "contact: test.user@example.org, tel=+33 6 12 34 56 78"
    )
    redacted = redact_sensitive_text(raw)
    assert "supersecretvalue123456" not in redacted
    assert "ABCDEFGHIJKLMNOPQRSTUV123456" not in redacted
    assert "test.user@example.org" not in redacted
    assert "+33 6 12 34 56 78" not in redacted
    assert "***REDACTED***" in redacted
    assert "***REDACTED_EMAIL***" in redacted
    assert "***REDACTED_PHONE***" in redacted
