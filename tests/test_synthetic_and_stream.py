"""Synthetic generator, dataset round-trip, and stream replay."""

from loganalysis.ingestion.loader import load_sample
from loganalysis.ingestion.stream import replay_sessions
from loganalysis.ingestion.synthetic import generate, write_dataset


def test_generate_is_deterministic_and_labeled():
    a = generate(n_sessions=200, seed=1)
    b = generate(n_sessions=200, seed=1)
    assert len(a) == 200
    assert [s.session_id for s in a] == [s.session_id for s in b]
    # Has both normal and anomalous sessions.
    labels = {s.label for s in a}
    assert labels == {0, 1}
    # Anomalous sessions carry a non-normal category.
    anomalous = [s for s in a if s.label == 1]
    assert anomalous and all(s.category != "normal" for s in anomalous)


def test_write_and_load_roundtrip(tmp_path):
    sessions = generate(n_sessions=120, seed=3)
    write_dataset(tmp_path, sessions)
    assert (tmp_path / "logs.jsonl").exists()
    assert (tmp_path / "labels.csv").exists()

    loaded = load_sample(tmp_path)
    assert len(loaded) == len(sessions)
    by_id = {s.session_id: s for s in sessions}
    for ls in loaded:
        assert ls.label == by_id[ls.session_id].label
        assert ls.category == by_id[ls.session_id].category
        assert len(ls.records) == len(by_id[ls.session_id].records)


def test_planted_secrets_exist_for_redaction_to_catch():
    sessions = generate(n_sessions=400, seed=5)
    all_text = "\n".join(r.message for s in sessions for r in s.records)
    # At least one of the planted secret markers should appear in raw generated logs.
    assert any(tok in all_text for tok in ("password=", "Bearer ", "api_key="))


def test_replay_orders_by_timestamp():
    sessions = generate(n_sessions=30, seed=9)
    replayed = list(replay_sessions(sessions, speed=0.0))
    assert len(replayed) == len(sessions)
    firsts = [s.records[0].timestamp for s in replayed if s.records]
    assert firsts == sorted(firsts)
