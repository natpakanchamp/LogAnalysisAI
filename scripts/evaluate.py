"""Evaluate the trained bundle on the held-out test split against PRD §04 thresholds."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loganalysis.config import settings  # noqa: E402
from loganalysis.datasplit import split_sessions  # noqa: E402
from loganalysis.ingestion.loader import load_dataset  # noqa: E402
from loganalysis.metrics.evaluation import evaluate, format_report  # noqa: E402
from loganalysis.persistence import BUNDLE_NAME  # noqa: E402
from loganalysis.pipeline import Pipeline  # noqa: E402
from loganalysis.summarize.llm_summarizer import Summarizer  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args_p = argparse.ArgumentParser(description="Evaluate Log Analysis AI")
    args_p.add_argument("--dataset", default="sample", choices=["sample", "hdfs"])
    args_p.add_argument("--limit", type=int, default=None)
    args = args_p.parse_args(argv)

    bundle = settings.artifact_path(BUNDLE_NAME)
    if not bundle.exists():
        print(f"No trained bundle at {bundle}. Run: python scripts/train.py --dataset {args.dataset}")
        return 1

    sessions = load_dataset(args.dataset, settings.dataset_dir(args.dataset), limit=args.limit)
    _train, test = split_sessions(sessions)

    # Force the template summarizer during evaluation (no LLM calls over the whole test set).
    pipeline = Pipeline.from_bundle(bundle, summarizer=Summarizer(api_key=""))

    ai_preds: list[bool] = []
    rule_preds: list[bool] = []
    labels: list[int] = []
    high_severity: list[bool] = []
    detect_latencies: list[int] = []

    for session in test:
        result = pipeline.process_session(session)
        ai_preds.append(result.ai_anomaly)
        rule_preds.append(result.rule_anomaly)
        labels.append(session.label)
        high_severity.append(result.high_severity)
        if session.label == 1 and result.ai_anomaly and result.detect_latency is not None:
            detect_latencies.append(result.detect_latency)

    report = evaluate(
        ai_preds=ai_preds, rule_preds=rule_preds, labels=labels,
        high_severity=high_severity, detect_latencies=detect_latencies,
    )
    print(format_report(report))
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
