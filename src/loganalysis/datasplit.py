"""Deterministic train/test split shared by training and evaluation."""

from __future__ import annotations

import random

from loganalysis.ingestion.loader import LabeledSession


def split_sessions(
    sessions: list[LabeledSession], test_ratio: float = 0.3, seed: int = 13
) -> tuple[list[LabeledSession], list[LabeledSession]]:
    """Shuffle by a fixed seed and split. Same seed → identical split across runs."""
    indices = list(range(len(sessions)))
    random.Random(seed).shuffle(indices)
    n_test = int(len(sessions) * test_ratio)
    test_idx = set(indices[:n_test])
    train = [s for i, s in enumerate(sessions) if i not in test_idx]
    test = [s for i, s in enumerate(sessions) if i in test_idx]
    return train, test
