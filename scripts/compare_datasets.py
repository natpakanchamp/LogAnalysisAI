"""Train + evaluate on both the synthetic ``sample`` and the real ``hdfs`` datasets,
then print a side-by-side metrics comparison and write ``docs/dataset_comparison.md``.

Why a dedicated runner instead of ``train.py``/``evaluate.py`` twice:
  * It keeps each dataset's bundle in memory (no clobbering ``models/model_bundle.pt``).
  * For HDFS it pre-selects a stratified subset of *complete* blocks and streams the
    11M-line log once — avoiding both session truncation (the ``--limit`` line cap) and
    loading every record into memory.

Run: ``python scripts/compare_datasets.py --hdfs-cap 12000``
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loganalysis.classification.root_cause import RootCauseClassifier  # noqa: E402
from loganalysis.config import settings  # noqa: E402
from loganalysis.datasplit import split_sessions  # noqa: E402
from loganalysis.detection.deeplog import DeepLogDetector  # noqa: E402
from loganalysis.ingestion.loader import LabeledSession, load_dataset  # noqa: E402
from loganalysis.metrics.evaluation import EvalReport, evaluate, format_report  # noqa: E402
from loganalysis.parsing.drain_parser import DrainParser  # noqa: E402
from loganalysis.pipeline import Pipeline  # noqa: E402
from loganalysis.records import LogRecord  # noqa: E402
from loganalysis.redaction.redactor import Redactor  # noqa: E402
from loganalysis.summarize.llm_summarizer import Summarizer  # noqa: E402

_BLOCK_RE = re.compile(r"blk_-?\d+")
_HDFS_LINE_RE = re.compile(
    r"^(?P<date>\d{6})\s+(?P<time>\d{6})\s+\d+\s+(?P<level>\w+)\s+(?P<comp>\S+):\s+(?P<msg>.*)$"
)


def load_hdfs_subset(dataset_dir: Path, cap: int, seed: int) -> list[LabeledSession]:
    """Load a stratified subset of *complete* HDFS blocks (preserves the anomaly ratio).

    Selects block IDs up front from ``anomaly_label.csv``, then streams ``HDFS.log`` once,
    keeping only lines belonging to the chosen blocks — so sessions are never truncated
    and we never hold all 11M records in memory.
    """
    log_path = dataset_dir / "HDFS.log"
    label_path = dataset_dir / "anomaly_label.csv"
    if not log_path.exists() or not label_path.exists():
        raise FileNotFoundError(f"HDFS dataset missing in {dataset_dir}")

    import csv

    normals: list[str] = []
    anomalies: list[str] = []
    with label_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["Label"].strip().lower() == "anomaly":
                anomalies.append(row["BlockId"])
            else:
                normals.append(row["BlockId"])

    rng = random.Random(seed)
    total = len(normals) + len(anomalies)
    anomaly_ratio = len(anomalies) / total
    n_anom = min(len(anomalies), max(1, round(cap * anomaly_ratio)))
    n_norm = min(len(normals), cap - n_anom)
    chosen_anom = set(rng.sample(anomalies, n_anom))
    chosen_norm = set(rng.sample(normals, n_norm))
    chosen = chosen_anom | chosen_norm
    label_of = {b: 1 for b in chosen_anom}
    label_of.update({b: 0 for b in chosen_norm})

    grouped: dict[str, list[LogRecord]] = {}
    order: list[str] = []
    with log_path.open(encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            blocks = _BLOCK_RE.findall(line)
            if not blocks:
                continue
            sid = blocks[0]
            if sid not in chosen:
                continue
            m = _HDFS_LINE_RE.match(line.strip())
            msg = m.group("msg") if m else line.strip()
            comp = m.group("comp") if m else "hdfs"
            if sid not in grouped:
                grouped[sid] = []
                order.append(sid)
            grouped[sid].append(LogRecord(
                timestamp=float(i), service=comp, session_id=sid, message=msg, raw=line.strip(),
            ))

    sessions: list[LabeledSession] = []
    for sid in order:
        lbl = label_of[sid]
        sessions.append(LabeledSession(
            session_id=sid, records=tuple(grouped[sid]), label=lbl,
            anomaly_type="" if lbl == 0 else "hdfs_anomaly",
            category="normal" if lbl == 0 else "abnormal_sequence",
        ))
    return sessions


def train_pipeline(train: list[LabeledSession], epochs: int) -> Pipeline:
    redactor = Redactor()
    drain = DrainParser()
    train_sequences: list[list[int]] = []
    categories: list[str] = []
    normal_sequences: list[list[int]] = []
    for session in train:
        keys = [drain.fit_line(redactor.scrub(rec.message)) for rec in session.records]
        train_sequences.append(keys)
        categories.append(session.category)
        if session.label == 0:
            normal_sequences.append(keys)
    drain.freeze()

    detector = DeepLogDetector(
        num_keys=drain.num_keys, window_size=settings.window_size,
        num_candidates=settings.num_candidates, embedding_dim=settings.embedding_dim,
        hidden_size=settings.hidden_size, num_layers=settings.num_layers,
        epochs=epochs, batch_size=settings.batch_size, learning_rate=settings.learning_rate,
    )
    detector.fit(normal_sequences)
    classifier = RootCauseClassifier(num_keys=drain.num_keys)
    classifier.fit(train_sequences, categories)
    return Pipeline(drain, detector, classifier, summarizer=Summarizer(api_key="")), drain.num_keys


def run_eval(pipeline: Pipeline, test: list[LabeledSession]) -> EvalReport:
    ai_preds, rule_preds, labels, high_sev, latencies = [], [], [], [], []
    for session in test:
        r = pipeline.process_session(session)
        ai_preds.append(r.ai_anomaly)
        rule_preds.append(r.rule_anomaly)
        labels.append(session.label)
        high_sev.append(r.high_severity)
        if session.label == 1 and r.ai_anomaly and r.detect_latency is not None:
            latencies.append(r.detect_latency)
    return evaluate(
        ai_preds=ai_preds, rule_preds=rule_preds, labels=labels,
        high_severity=high_sev, detect_latencies=latencies,
    )


def run_dataset(name: str, sessions: list[LabeledSession], epochs: int) -> tuple[EvalReport, dict]:
    train, test = split_sessions(sessions)
    n_anom_tr = sum(s.label == 1 for s in train)
    n_anom_te = sum(s.label == 1 for s in test)
    print(f"\n[{name}] {len(sessions)} sessions → train {len(train)} "
          f"({n_anom_tr} anom) / test {len(test)} ({n_anom_te} anom)")
    t0 = time.time()
    pipeline, num_keys = train_pipeline(train, epochs)
    print(f"[{name}] trained in {time.time() - t0:.1f}s — {num_keys} event templates")
    report = run_eval(pipeline, test)
    meta = {
        "sessions": len(sessions), "train": len(train), "test": len(test),
        "test_anomalies": n_anom_te, "num_templates": num_keys, "epochs": epochs,
    }
    return report, meta


def report_row(report: EvalReport) -> dict:
    o, r = report.overall, report.rule_overall
    return {
        "ai_precision": round(o.precision, 4), "ai_recall": round(o.recall, 4),
        "ai_f1": round(o.f1, 4), "ai_accuracy": round(o.accuracy, 4),
        "recall_high_severity": round(report.recall_high_severity, 4),
        "tp": o.tp, "fp": o.fp, "fn": o.fn, "tn": o.tn,
        "rule_precision": round(r.precision, 4), "rule_recall": round(r.recall, 4),
        "ai_beats_rules": report.ai_beats_rules, "mttd_windows": round(report.mttd_windows, 3),
        "passed": report.passed,
    }


def write_markdown(out: Path, results: dict) -> None:
    s, h = results["sample"]["metrics"], results["hdfs"]["metrics"]
    sm, hm = results["sample"]["meta"], results["hdfs"]["meta"]

    def row(label: str, key: str, fmt: str = "{:.3f}") -> str:
        return f"| {label} | {fmt.format(s[key])} | {fmt.format(h[key])} |"

    lines = [
        "# Dataset Comparison — Synthetic vs. Real HDFS",
        "",
        "Same model + hyperparameters (PRD §04/§05), trained and evaluated independently on "
        "each dataset. The template summarizer is used during evaluation (no LLM calls).",
        "",
        "## Dataset shape",
        "",
        "| | Synthetic (sample) | Real HDFS_v1 |",
        "|---|---|---|",
        f"| Total sessions | {sm['sessions']} | {hm['sessions']} |",
        f"| Train / Test | {sm['train']} / {sm['test']} | {hm['train']} / {hm['test']} |",
        f"| Test anomalies | {sm['test_anomalies']} | {hm['test_anomalies']} |",
        f"| Event templates (Drain) | {sm['num_templates']} | {hm['num_templates']} |",
        f"| Epochs | {sm['epochs']} | {hm['epochs']} |",
        "",
        "## DeepLog detector metrics",
        "",
        "| Metric | Synthetic | Real HDFS |",
        "|---|---|---|",
        row("Precision", "ai_precision"),
        row("Recall", "ai_recall"),
        row("F1", "ai_f1"),
        row("Recall (high-severity)", "recall_high_severity"),
        row("Accuracy", "ai_accuracy"),
        f"| TP / FP / FN / TN | {s['tp']}/{s['fp']}/{s['fn']}/{s['tn']} | "
        f"{h['tp']}/{h['fp']}/{h['fn']}/{h['tn']} |",
        "",
        "## Rule-based baseline",
        "",
        "| Metric | Synthetic | Real HDFS |",
        "|---|---|---|",
        row("Precision", "rule_precision"),
        row("Recall", "rule_recall"),
        f"| AI-only catches (rules missed) | {s['ai_beats_rules']} | {h['ai_beats_rules']} |",
        "",
        "## PRD threshold result",
        "",
        f"- Synthetic: **{'ALL PASS' if s['passed'] else 'SOME NOT MET'}**",
        f"- Real HDFS: **{'ALL PASS' if h['passed'] else 'SOME NOT MET'}**",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compare synthetic vs HDFS metrics")
    ap.add_argument("--hdfs-cap", type=int, default=12000, help="max HDFS blocks to sample")
    ap.add_argument("--epochs", type=int, default=settings.epochs)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    print("Loading synthetic sample ...")
    sample_sessions = load_dataset("sample", settings.dataset_dir("sample"))
    print(f"Loading HDFS subset (cap {args.hdfs_cap}) ...")
    hdfs_sessions = load_hdfs_subset(settings.dataset_dir("hdfs"), args.hdfs_cap, args.seed)

    results = {}
    for name, sessions in (("sample", sample_sessions), ("hdfs", hdfs_sessions)):
        report, meta = run_dataset(name, sessions, args.epochs)
        print(format_report(report))
        results[name] = {"metrics": report_row(report), "meta": meta}

    docs = settings.data_dir.parent / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "dataset_comparison.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    write_markdown(docs / "dataset_comparison.md", results)
    print(f"\nWrote docs/dataset_comparison.md and docs/dataset_comparison.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
