"""Evaluation math (PRD §04)."""

from loganalysis.metrics.evaluation import confusion, evaluate


def test_confusion_counts():
    preds = [True, True, False, False]
    labels = [1, 0, 1, 0]
    c = confusion(preds, labels)
    assert (c.tp, c.fp, c.fn, c.tn) == (1, 1, 1, 1)


def test_precision_recall_f1():
    # 2 TP, 1 FP, 1 FN
    preds = [True, True, True, False]
    labels = [1, 1, 0, 1]
    c = confusion(preds, labels)
    assert c.precision == 2 / 3
    assert c.recall == 2 / 3
    assert abs(c.f1 - 2 / 3) < 1e-9


def test_perfect_predictions():
    c = confusion([True, False, True], [1, 0, 1])
    assert c.precision == 1.0 and c.recall == 1.0 and c.f1 == 1.0


def test_mismatched_lengths_raise():
    import pytest

    with pytest.raises(ValueError):
        confusion([True], [1, 0])


def test_evaluate_counts_ai_beats_rules_and_high_severity_recall():
    # 3 anomalies (all high-severity). AI catches all; rule catches only #2.
    ai_preds = [True, True, True, False]
    rule_preds = [False, True, False, False]
    labels = [1, 1, 1, 0]
    high_severity = [True, True, True, False]
    report = evaluate(
        ai_preds=ai_preds, rule_preds=rule_preds, labels=labels,
        high_severity=high_severity, detect_latencies=[0, 1, 2],
    )
    assert report.recall_high_severity == 1.0
    assert report.ai_beats_rules == 2  # #1 and #3 caught by AI, missed by rule
    assert report.overall.recall == 1.0
    assert report.mttd_windows == 1.0
