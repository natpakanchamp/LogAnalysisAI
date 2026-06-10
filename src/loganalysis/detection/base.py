"""Detector interface and result type (repository-style abstraction)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DetectionResult:
    """Outcome of scoring one session."""

    is_anomaly: bool
    anomaly_score: float                       # 0..1, higher = more anomalous
    confidence: float                          # 0..1, model's certainty in this decision
    detector: str                              # detector name
    anomalous_positions: tuple[int, ...] = field(default_factory=tuple)
    detail: str = ""

    def __post_init__(self) -> None:
        # Clamp to [0, 1] defensively — scores feed severity/HITL logic downstream.
        object.__setattr__(self, "anomaly_score", _clamp(self.anomaly_score))
        object.__setattr__(self, "confidence", _clamp(self.confidence))


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


class SequenceDetector(ABC):
    """Detects anomalies from a sequence of integer event keys."""

    name: str = "detector"

    @abstractmethod
    def fit(self, normal_sequences: list[list[int]]) -> None:
        """Train on normal sessions only (semi-supervised, DeepLog-style)."""

    @abstractmethod
    def predict(self, sequence: list[int]) -> DetectionResult:
        """Score a single session's event-key sequence."""
