"""Secret/PII redaction applied to every log line *before* it reaches the model.

PRD §03 (Data Gaps): "Log อาจมี Access token, password → ต้องมี redaction, filtering layer
ก่อนส่งเข้า model ไม่งั้นจะกลายเป็นช่องโหว่ความปลอดภัยทันที."

The redactor is intentionally conservative: it strips obvious credentials, keys, JWTs,
private keys, and emails, and reports which categories were found (useful for the audit
trail required by PRD §06). It never raises on input; redaction must not break ingestion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Ordered (specific → general). Each entry: (category, compiled pattern, replacement).
_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "private_key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                   re.DOTALL),
        "<REDACTED:PRIVATE_KEY>",
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
        "<REDACTED:JWT>",
    ),
    (
        "bearer",
        re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
        "Bearer <REDACTED>",
    ),
    (
        "aws_key",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "<REDACTED:AWS_KEY>",
    ),
    (
        "credential_kv",
        re.compile(
            r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|token|apikey)"
            r"\s*[=:]\s*[\"']?[^\s\"']+[\"']?"
        ),
        r"\1=<REDACTED>",
    ),
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "<REDACTED:EMAIL>",
    ),
)


@dataclass(frozen=True)
class RedactionResult:
    text: str
    categories: tuple[str, ...]  # categories of secret found, for the audit trail

    @property
    def had_secret(self) -> bool:
        return bool(self.categories)


class Redactor:
    """Stateless secret scrubber. Safe to share across threads."""

    def redact(self, text: str) -> RedactionResult:
        if not text:
            return RedactionResult(text=text, categories=())
        found: list[str] = []
        result = text
        for category, pattern, replacement in _RULES:
            new_result, n = pattern.subn(replacement, result)
            if n:
                found.append(category)
                result = new_result
        return RedactionResult(text=result, categories=tuple(found))

    def scrub(self, text: str) -> str:
        """Convenience: return only the redacted text."""
        return self.redact(text).text
