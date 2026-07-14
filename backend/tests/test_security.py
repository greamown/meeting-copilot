from pathlib import Path

import pytest

from app.core.security import allowlisted_path, redact, scrub_mapping


def test_redaction():
    assert "supersecret" not in redact("Authorization: Bearer supersecret")
    assert "abc1234567890" not in redact("api_key=abc1234567890")
    assert scrub_mapping({"access_token": "raw", "safe": "value"}) == {"access_token": "[REDACTED]", "safe": "value"}


def test_repository_path_allowlist(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    assert allowlisted_path(str(allowed), [tmp_path]) == allowed.resolve()
    with pytest.raises(ValueError):
        allowlisted_path("/etc", [tmp_path])
