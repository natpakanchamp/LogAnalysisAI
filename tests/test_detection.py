"""DeepLog and rule-based detector behavior on controlled sequences."""

from loganalysis.detection.base import DetectionResult
from loganalysis.detection.deeplog import DeepLogDetector
from loganalysis.detection.rule_based import RuleBasedDetector


def _train_deeplog() -> DeepLogDetector:
    # A strict normal grammar: keys always cycle 1 -> 2 -> 3 -> 4 -> 5 -> 1 ...
    normal = [[1, 2, 3, 4, 5, 1, 2, 3, 4, 5, 1, 2, 3, 4, 5] for _ in range(40)]
    det = DeepLogDetector(num_keys=6, window_size=4, num_candidates=1, epochs=40)
    det.fit(normal)
    return det


def test_deeplog_accepts_normal_sequence():
    det = _train_deeplog()
    result = det.predict([1, 2, 3, 4, 5, 1, 2, 3, 4, 5])
    assert isinstance(result, DetectionResult)
    assert result.is_anomaly is False
    assert result.detector == "deeplog"


def test_deeplog_flags_ordering_anomaly():
    det = _train_deeplog()
    # Valid keys, abnormal order (5 then 5 then 4 ...) — no error keyword involved.
    result = det.predict([1, 2, 3, 4, 5, 5, 5, 5, 5, 5])
    assert result.is_anomaly is True
    assert result.anomaly_score > 0.0
    assert len(result.anomalous_positions) >= 1


def test_deeplog_flags_unseen_template():
    det = _train_deeplog()
    # Key 99 was never seen (out of range). Placed at the end it becomes a prediction
    # target -> unknown -> anomalous by construction, deterministically.
    result = det.predict([1, 2, 3, 4, 5, 1, 2, 3, 4, 99])
    assert result.is_anomaly is True


def test_scores_are_clamped_to_unit_interval():
    result = DetectionResult(
        is_anomaly=True, anomaly_score=2.5, confidence=-1.0, detector="x"
    )
    assert result.anomaly_score == 1.0
    assert result.confidence == 0.0


def test_rule_based_catches_error_keyword():
    det = RuleBasedDetector()
    result = det.predict_messages([
        "Received block blk_1 of size 10",
        "ERROR DataNode exception on blk_1: connection reset",
    ])
    assert result.is_anomaly is True
    assert result.anomalous_positions == (1,)


def test_rule_based_misses_ordering_anomaly_without_error_keyword():
    det = RuleBasedDetector()
    result = det.predict_messages([
        "Receiving block blk_1",
        "Reopen Block blk_1",
        "PacketResponder 0 for block blk_1 terminating",
    ])
    # No error keyword present -> the rule baseline cannot flag this. This is the gap
    # DeepLog is meant to close.
    assert result.is_anomaly is False
