"""Redaction must remove secrets before logs reach the model (PRD §03)."""

from loganalysis.redaction.redactor import Redactor


def test_redacts_password_key_value():
    # Arrange
    redactor = Redactor()
    line = "user login password=hunter2 ok"

    # Act
    result = redactor.redact(line)

    # Assert
    assert "hunter2" not in result.text
    assert "password=<REDACTED>" in result.text
    assert "credential_kv" in result.categories
    assert result.had_secret is True


def test_redacts_api_token_and_email():
    redactor = Redactor()
    line = "calling api_key=sk-live-9f8e7d6c notify ops@corp.com"

    result = redactor.redact(line)

    assert "sk-live-9f8e7d6c" not in result.text
    assert "ops@corp.com" not in result.text
    assert "<REDACTED:EMAIL>" in result.text


def test_redacts_jwt_and_bearer():
    redactor = Redactor()
    line = "authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc123"

    result = redactor.redact(line)

    assert "eyJzdWIiOiIxIn0" not in result.text
    assert "<REDACTED" in result.text


def test_redacts_aws_access_key():
    redactor = Redactor()
    result = redactor.redact("key AKIAIOSFODNN7EXAMPLE in config")
    assert "AKIAIOSFODNN7EXAMPLE" not in result.text
    assert "aws_key" in result.categories


def test_preserves_clean_line_and_reports_no_secret():
    redactor = Redactor()
    clean = "Received block blk_123 of size 4096 from /10.0.0.1"

    result = redactor.redact(clean)

    assert result.text == clean
    assert result.categories == ()
    assert result.had_secret is False


def test_empty_input_is_safe():
    redactor = Redactor()
    result = redactor.redact("")
    assert result.text == ""
    assert result.had_secret is False
