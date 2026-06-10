"""Rule-based baseline detector (the incumbent the PRD wants AI to beat).

Flags a session when any line contains an explicit error keyword. By design it cannot see
*sequence-ordering* or *latency* anomalies that carry no error keyword — exactly the gap
the DeepLog detector fills, which is how we count the PRD business metric
"incidents rule-based can't detect but AI does > 0".
"""

from __future__ import annotations

import re

from loganalysis.detection.base import DetectionResult

_ERROR_PATTERN = re.compile(
    r"(?i)\b(error|exception|fatal|panic|failed|failure|fail|timeout|refused|corrupt)\b"
)


class RuleBasedDetector:
    name = "rule_based"

    def predict_messages(self, messages: list[str]) -> DetectionResult:
        hits = [i for i, m in enumerate(messages) if _ERROR_PATTERN.search(m)]
        is_anomaly = bool(hits)
        return DetectionResult(
            is_anomaly=is_anomaly,
            anomaly_score=1.0 if is_anomaly else 0.0,
            # The rule is crude but deterministic: high "confidence" either way. This makes
            # AI↔rule disagreements (a HITL trigger) meaningful rather than noisy.
            confidence=0.95 if is_anomaly else 0.9,
            detector=self.name,
            anomalous_positions=tuple(hits),
            detail=f"{len(hits)} line(s) matched error keywords" if hits else "no error keywords",
        )
