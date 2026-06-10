"""Severity scoring (drives alert priority, HITL routing, and high-severity recall).

Severity combines the root-cause category, the detector's anomaly score, and whether the
rule baseline also fired. The PRD's Recall ≥ 0.90 target applies specifically to
*high-severity* incidents, so :func:`is_high_severity` is the gate used in evaluation.
"""

from __future__ import annotations

LOW, MEDIUM, HIGH, CRITICAL = "low", "medium", "high", "critical"
_ORDER = {LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3}

# Baseline severity floor per root-cause category.
_CATEGORY_FLOOR = {
    "normal": LOW,
    "latency": MEDIUM,
    "abnormal_sequence": MEDIUM,
    "io_error": HIGH,
    "deadlock": HIGH,
}


def assess_severity(category: str, anomaly_score: float, rule_flagged: bool) -> str:
    """Return one of low/medium/high/critical."""
    severity = _CATEGORY_FLOOR.get(category, MEDIUM)

    # A strong anomaly signal escalates one step.
    if anomaly_score >= 0.9 and _ORDER[severity] < _ORDER[CRITICAL]:
        severity = _next(severity)

    # Corroboration by the rule baseline on an already-high incident → critical.
    if rule_flagged and _ORDER[severity] >= _ORDER[HIGH]:
        severity = CRITICAL

    return severity


def _next(level: str) -> str:
    nxt = min(_ORDER[level] + 1, _ORDER[CRITICAL])
    return next(k for k, v in _ORDER.items() if v == nxt)


def is_high_severity(severity: str) -> bool:
    return _ORDER.get(severity, 0) >= _ORDER[HIGH]


def severity_rank(severity: str) -> int:
    return _ORDER.get(severity, 0)
