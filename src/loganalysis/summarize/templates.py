"""Deterministic, offline root-cause summary (fallback when no LLM is configured)."""

from __future__ import annotations

_CATEGORY_DESC = {
    "abnormal_sequence": "an abnormal sequence of operations (events out of expected order)",
    "io_error": "an I/O / connection error",
    "deadlock": "a probable deadlock (system hang with no error log)",
    "latency": "a latency spike under load",
    "normal": "no clear root cause",
}


def template_summary(
    *,
    category: str,
    severity: str,
    suspect_service: str,
    suspect_commit: str,
    sample_messages: list[str],
    detectors: list[str],
) -> str:
    cause = _CATEGORY_DESC.get(category, "an anomalous log pattern")
    detected_by = " + ".join(detectors) if detectors else "the model"
    evidence = "; ".join(m[:90] for m in sample_messages[:2]) or "n/a"
    commit = f" Recent suspect commit: {suspect_commit}." if suspect_commit else ""
    return (
        f"[{severity.upper()}] Detected {cause} in service '{suspect_service}' "
        f"(flagged by {detected_by}).{commit} "
        f"Evidence: {evidence}. "
        f"Recommended: inspect '{suspect_service}' around the affected window and confirm "
        f"before remediation."
    )
