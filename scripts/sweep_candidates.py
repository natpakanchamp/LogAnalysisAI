"""Sweep DeepLog's ``num_candidates`` (top-g) on a dataset to find the best precision/recall
trade-off — the main knob for the over-flagging seen on real HDFS.

``num_candidates`` only affects *inference*, so the LSTM is trained once and re-evaluated
for every g. Writes ``docs/sweep_<dataset>.json`` and prints a table + the best-F1 pick.

Run: ``python scripts/sweep_candidates.py --dataset hdfs --hdfs-cap 12000``
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from loganalysis.config import settings  # noqa: E402
from loganalysis.datasplit import split_sessions  # noqa: E402
from loganalysis.ingestion.loader import load_dataset  # noqa: E402
from scripts.compare_datasets import (  # noqa: E402
    load_hdfs_subset, report_row, run_eval, train_pipeline,
)

DEFAULT_GRID = [1, 2, 3, 4, 5, 7, 9, 11, 13]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sweep DeepLog num_candidates")
    ap.add_argument("--dataset", default="hdfs", choices=["sample", "hdfs"])
    ap.add_argument("--hdfs-cap", type=int, default=12000)
    ap.add_argument("--epochs", type=int, default=settings.epochs)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--grid", type=int, nargs="+", default=DEFAULT_GRID)
    args = ap.parse_args(argv)

    if args.dataset == "hdfs":
        sessions = load_hdfs_subset(settings.dataset_dir("hdfs"), args.hdfs_cap, args.seed)
    else:
        sessions = load_dataset("sample", settings.dataset_dir("sample"))

    train, test = split_sessions(sessions)
    n_anom = sum(s.label == 1 for s in test)
    print(f"[{args.dataset}] train {len(train)} / test {len(test)} ({n_anom} anom)")

    t0 = time.time()
    pipeline, num_keys = train_pipeline(train, args.epochs)
    print(f"Trained once in {time.time() - t0:.1f}s — {num_keys} templates\n")

    grid = [g for g in args.grid if g <= num_keys]
    print(f"{'g':>3} | {'precision':>9} | {'recall':>7} | {'F1':>6} | "
          f"{'recall_hs':>9} | {'FP':>5} | {'FN':>4} | PRD")
    print("-" * 64)

    rows = []
    default_g = settings.num_candidates
    for g in grid:
        pipeline.detector.num_candidates = g
        rep = run_eval(pipeline, test)
        row = report_row(rep)
        row["g"] = g
        rows.append(row)
        mark = " ←current" if g == default_g else ""
        print(f"{g:>3} | {row['ai_precision']:>9.3f} | {row['ai_recall']:>7.3f} | "
              f"{row['ai_f1']:>6.3f} | {row['recall_high_severity']:>9.3f} | "
              f"{row['fp']:>5} | {row['fn']:>4} | {'PASS' if row['passed'] else 'no'}{mark}")

    best = max(rows, key=lambda r: r["ai_f1"])
    print("-" * 64)
    print(f"Best F1: g={best['g']} → F1={best['ai_f1']:.3f} "
          f"(precision {best['ai_precision']:.3f}, recall {best['ai_recall']:.3f}, "
          f"high-sev recall {best['recall_high_severity']:.3f})")

    out = ROOT / "docs" / f"sweep_{args.dataset}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(
        {"dataset": args.dataset, "num_templates": num_keys, "test": len(test),
         "test_anomalies": n_anom, "rows": rows, "best_g": best["g"]},
        indent=2,
    ), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
