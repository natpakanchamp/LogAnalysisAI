"""Drain3 wrapper: stable contiguous keys, unknown handling, template recovery."""

from loganalysis.parsing.drain_parser import UNKNOWN_KEY, DrainParser


def test_same_template_gets_same_key():
    parser = DrainParser()
    k1 = parser.fit_line("Received block blk_111 of size 100 from /10.0.0.1")
    k2 = parser.fit_line("Received block blk_222 of size 999 from /10.0.0.9")
    assert k1 == k2


def test_different_templates_get_different_keys():
    parser = DrainParser()
    k1 = parser.fit_line("Received block blk_111 of size 100 from /10.0.0.1")
    k2 = parser.fit_line("FATAL deadlock detected waiting for lock on worker")
    assert k1 != k2
    assert parser.num_keys == 2


def test_keys_are_contiguous_from_zero():
    parser = DrainParser()
    keys = parser.fit([
        "Receiving block blk_1 src /10.0.0.1 dest /10.0.0.2",
        "Received block blk_1 of size 10 from /10.0.0.1",
        "Verification succeeded for blk_1",
    ])
    assert sorted(set(keys)) == [0, 1, 2]


def test_unknown_template_at_inference_returns_unknown_key():
    parser = DrainParser()
    parser.fit(["Received block blk_1 of size 10 from /10.0.0.1"])
    parser.freeze()
    # A line with a completely different structure should not match.
    assert parser.transform_line("quantum flux capacitor overload on reactor core 7") == UNKNOWN_KEY


def test_transform_matches_learned_template():
    parser = DrainParser()
    parser.fit(["Received block blk_1 of size 10 from /10.0.0.1"])
    key = parser.transform_line("Received block blk_999 of size 4096 from /10.0.0.5")
    assert key == 0
