"""Sliding-window construction for DeepLog."""

from loganalysis.features.sequencer import build_training_pairs, sliding_windows


def test_sliding_windows_basic():
    pairs = list(sliding_windows([1, 2, 3, 4, 5], window_size=2))
    assert pairs == [
        ((1, 2), 3),
        ((2, 3), 4),
        ((3, 4), 5),
    ]


def test_short_sequence_is_left_padded():
    pairs = list(sliding_windows([7, 8], window_size=5))
    # padded to [0,0,0,0,7,8] -> one window predicting the last key
    assert len(pairs) == 1
    history, nxt = pairs[0]
    assert len(history) == 5
    assert nxt == 8


def test_empty_sequence_yields_nothing():
    assert list(sliding_windows([], window_size=3)) == []


def test_build_training_pairs_flattens_sessions():
    histories, targets = build_training_pairs([[1, 2, 3], [4, 5, 6]], window_size=2)
    assert len(histories) == len(targets) == 2
    assert targets == [3, 6]
