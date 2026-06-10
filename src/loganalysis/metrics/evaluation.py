"""Evaluation against the PRD §04 success metrics.

Computes Precision/Recall/F1 (overall and high-severity recall), a Mean-Time-To-Detect
proxy, and the "AI beats rules" count — then checks them against the PRD thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loganalysis.config import settings


@dataclass(frozen=True)
class Confusion:
    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def accuracy(self) -> float:
        total = self.tp + self.fp + self.fn + self.tn
        return (self.tp + self.tn) / total if total else 0.0


def confusion(preds: list[bool], labels: list[int]) -> Confusion:
    if len(preds) != len(labels):
        raise ValueError("preds and labels must be the same length")
    tp = fp = fn = tn = 0
    for pred, label in zip(preds, labels):
        truth = label == 1
        if pred and truth:
            tp += 1
        elif pred and not truth:
            fp += 1
        elif not pred and truth:
            fn += 1
        else:
            tn += 1
    return Confusion(tp=tp, fp=fp, fn=fn, tn=tn)


@dataclass(frozen=True)
class EvalReport:
    n: int
    overall: Confusion
    rule_overall: Confusion
    recall_high_severity: float
    mttd_windows: float
    ai_beats_rules: int
    thresholds: dict[str, bool] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(self.thresholds.values())


def _recall_high_severity(
    ai_preds: list[bool], labels: list[int], high_severity: list[bool]
) -> float:
    tp = fn = 0
    for pred, label, hs in zip(ai_preds, labels, high_severity):
        if label == 1 and hs:
            if pred:
                tp += 1
            else:
                fn += 1
    denom = tp + fn
    return tp / denom if denom else 0.0


def evaluate(
    *,
    ai_preds: list[bool],
    rule_preds: list[bool],
    labels: list[int],
    high_severity: list[bool],
    detect_latencies: list[int],
) -> EvalReport:
    """Build the full evaluation report.

    ``detect_latencies`` is the windows-to-first-flag for each *correctly detected* anomaly
    (used for the MTTD proxy); pass an empty list if none.
    """
    overall = confusion(ai_preds, labels)
    rule_overall = confusion(rule_preds, labels)
    rec_hs = _recall_high_severity(ai_preds, labels, high_severity)
    mttd = sum(detect_latencies) / len(detect_latencies) if detect_latencies else 0.0
    ai_beats_rules = sum(
        1 for a, r, lbl in zip(ai_preds, rule_preds, labels) if lbl == 1 and a and not r
    )

    thresholds = {
        f"recall_high_severity>={settings.recall_target_high_severity}":
            rec_hs >= settings.recall_target_high_severity,
        f"precision_overall>={settings.precision_target_overall}":
            overall.precision >= settings.precision_target_overall,
        f"f1_overall>={settings.f1_target}":
            overall.f1 >= settings.f1_target,
        "ai_beats_rules>0": ai_beats_rules > 0,
    }

    return EvalReport(
        n=len(labels), overall=overall, rule_overall=rule_overall,
        recall_high_severity=rec_hs, mttd_windows=mttd,
        ai_beats_rules=ai_beats_rules, thresholds=thresholds,
    )


def format_report(report: EvalReport) -> str:
    o = report.overall
    r = report.rule_overall
    lines = [
        "=" * 60,
        "  Log Analysis AI — Evaluation (PRD §04)",
        "=" * 60,
        f"  Sessions evaluated      : {report.n}",
        "",
        "  AI (DeepLog) detector:",
        f"    Precision (overall)   : {o.precision:.3f}",
        f"    Recall (overall)      : {o.recall:.3f}",
        f"    F1 (overall)          : {o.f1:.3f}",
        f"    Recall (high-severity): {report.recall_high_severity:.3f}",
        f"    Accuracy              : {o.accuracy:.3f}",
        f"    TP/FP/FN/TN           : {o.tp}/{o.fp}/{o.fn}/{o.tn}",
        "",
        "  Rule-based baseline:",
        f"    Precision / Recall    : {r.precision:.3f} / {r.recall:.3f}",
        "",
        f"  MTTD (windows-to-detect): {report.mttd_windows:.2f}",
        f"  AI-only catches (rules missed): {report.ai_beats_rules}",
        "",
        "  Threshold checks:",
    ]
    for name, ok in report.thresholds.items():
        lines.append(f"    [{'PASS' if ok else 'FAIL'}] {name}")
    lines.append("=" * 60)
    lines.append(f"  RESULT: {'ALL PASS' if report.passed else 'SOME THRESHOLDS NOT MET'}")
    lines.append("=" * 60)
    return "\n".join(lines)
