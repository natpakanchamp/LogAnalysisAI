"""Turn parsed event-key sequences into the windows DeepLog consumes.

A *session* is the ordered list of event keys for one correlation id (e.g. an HDFS block).
Training uses sliding windows ``(history → next_key)`` over **normal** sessions only.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator


def sliding_windows(
    sequence: list[int], window_size: int
) -> Iterator[tuple[tuple[int, ...], int]]:
    """Yield ``(history, next_key)`` pairs.

    Short sequences are left-padded with ``0`` so every session yields at least one window.
    """
    if not sequence:
        return
    if len(sequence) <= window_size:
        padded = [0] * (window_size - len(sequence) + 1) + sequence
    else:
        padded = sequence
    for i in range(len(padded) - window_size):
        history = tuple(padded[i : i + window_size])
        nxt = padded[i + window_size]
        yield history, nxt


def build_training_pairs(
    sequences: Iterable[list[int]], window_size: int
) -> tuple[list[tuple[int, ...]], list[int]]:
    """Flatten many normal sessions into (histories, next_keys) for supervised training."""
    histories: list[tuple[int, ...]] = []
    targets: list[int] = []
    for seq in sequences:
        for history, nxt in sliding_windows(seq, window_size):
            histories.append(history)
            targets.append(nxt)
    return histories, targets
