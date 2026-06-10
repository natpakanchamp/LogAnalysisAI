"""Prepare datasets for Log Analysis AI.

``--sample``  generates a self-contained labeled synthetic dataset (no network).
``--hdfs``    prints instructions for fetching the real LogHub HDFS_v1 dataset.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a script without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loganalysis.config import settings  # noqa: E402
from loganalysis.ingestion.synthetic import generate, write_dataset  # noqa: E402


def make_sample(n_sessions: int, seed: int) -> Path:
    target = settings.dataset_dir("sample")
    sessions = generate(n_sessions=n_sessions, seed=seed)
    write_dataset(target, sessions)
    n_anom = sum(s.label for s in sessions)
    print(f"Wrote {len(sessions)} sessions ({n_anom} anomalous, "
          f"{n_anom / len(sessions):.1%}) to {target}")
    print(f"  - {target / 'logs.jsonl'}")
    print(f"  - {target / 'labels.csv'}")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare datasets for Log Analysis AI")
    parser.add_argument("--sample", action="store_true", help="generate synthetic sample dataset")
    parser.add_argument("--hdfs", action="store_true", help="show HDFS download instructions")
    parser.add_argument("--n", type=int, default=1800, help="number of synthetic sessions")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    if args.hdfs:
        print("Fetch HDFS_v1 from https://github.com/logpai/loghub (→ Zenodo) or a Kaggle "
              "mirror, then place HDFS.log + anomaly_label.csv under data/hdfs/.")
        return 0
    if args.sample or not (args.sample or args.hdfs):
        make_sample(args.n, args.seed)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
