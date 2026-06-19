"""Train the DeepLog detector and root-cause classifier, then save the artifact bundle."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from loganalysis.classification.root_cause import RootCauseClassifier  # noqa: E402
from loganalysis.config import settings  # noqa: E402
from loganalysis.datasplit import split_sessions  # noqa: E402
from loganalysis.detection.deeplog import DeepLogDetector  # noqa: E402
from loganalysis.ingestion.loader import load_dataset  # noqa: E402
from loganalysis.parsing.drain_parser import DrainParser  # noqa: E402
from loganalysis.persistence import BUNDLE_NAME, save_bundle  # noqa: E402
from loganalysis.redaction.redactor import Redactor  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser_args = argparse.ArgumentParser(description="Train Log Analysis AI models")
    parser_args.add_argument("--dataset", default="sample", choices=["sample", "hdfs"])
    parser_args.add_argument("--epochs", type=int, default=settings.epochs)
    parser_args.add_argument("--limit", type=int, default=None, help="cap raw HDFS lines")
    args = parser_args.parse_args(argv)

    print(f"Loading dataset '{args.dataset}' ...")
    sessions = load_dataset(args.dataset, settings.dataset_dir(args.dataset), limit=args.limit)
    train, _test = split_sessions(sessions)
    n_anom = sum(s.label == 1 for s in train)
    print(f"  {len(sessions)} sessions → {len(train)} train ({n_anom} anomalous)")

    redactor = Redactor()
    drain = DrainParser()

    # Fit Drain templates on redacted training lines; collect per-session key sequences.
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
    print(f"  Drain mined {drain.num_keys} distinct event templates")

    # 'g' is dataset-dependent (see scripts/sweep_candidates.py): HDFS needs a wider top-g.
    num_candidates = (
        settings.num_candidates_hdfs if args.dataset == "hdfs" else settings.num_candidates
    )
    t0 = time.time()
    detector = DeepLogDetector(
        num_keys=drain.num_keys, window_size=settings.window_size,
        num_candidates=num_candidates, embedding_dim=settings.embedding_dim,
        hidden_size=settings.hidden_size, num_layers=settings.num_layers,
        epochs=args.epochs, batch_size=settings.batch_size, learning_rate=settings.learning_rate,
    )
    print(f"  Training DeepLog on {len(normal_sequences)} normal sessions, {args.epochs} epochs ...")
    detector.fit(normal_sequences)
    print(f"  DeepLog trained in {time.time() - t0:.1f}s")

    classifier = RootCauseClassifier(num_keys=drain.num_keys)
    classifier.fit(train_sequences, categories)
    print("  Root-cause classifier trained")

    out = settings.artifact_path(BUNDLE_NAME)
    save_bundle(out, drain, detector, classifier)
    print(f"Saved bundle → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
