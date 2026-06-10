"""Synthetic, labeled, HDFS-style log generator.

Produces realistic block-lifecycle sessions so the full pipeline, the test suite, and the
evaluation can run with zero downloads. Two anomaly families are injected:

* ``ordering``  — valid event keys in an abnormal order, with **no** error keyword. The
  DeepLog detector catches these; the rule-based baseline misses them. This is what proves
  the PRD business metric *"incidents rule-based can't detect but AI does > 0"*.
* ``error``     — a session containing an explicit error/exception/fatal event.

The generator is deterministic given a seed.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path

from loganalysis.records import LogRecord

# --- Event templates (key id → message template) ------------------------------------
TEMPLATES: dict[int, str] = {
    1: "Receiving block {blk} src: /{ip}:{port} dest: /{ip2}:{port2}",
    2: "Received block {blk} of size {n} from /{ip}",
    3: "PacketResponder {k} for block {blk} terminating",
    4: "BLOCK* NameSystem.addStoredBlock: blockMap updated for {blk}",
    5: "Verification succeeded for {blk}",
    6: "Served block {blk} to /{ip}",
    7: "Deleting block {blk} file /data/{blk}",
    8: "BLOCK* ask /{ip} to replicate {blk}",
    9: "Starting thread to transfer block {blk} to /{ip}",
    10: "Reopen Block {blk}",
    11: "Receiving empty packet for block {blk}",
    12: "Took {n} ms to process request on {svc} (latency spike)",
    13: "writeBlock {blk} received exception java.io.IOException",  # error keyword
    14: "ERROR DataNode exception on {blk}: connection reset",      # error keyword
    15: "FATAL deadlock detected waiting for lock on {svc}",        # error keyword
}

# Templates whose text carries an explicit error keyword (rule-based baseline keys off these).
ERROR_KEYS: frozenset[int] = frozenset({13, 14, 15})

# A few valid "normal" block-lifecycle paths. Variation is added at render time.
NORMAL_PATHS: tuple[tuple[int, ...], ...] = (
    (1, 1, 1, 2, 4, 3, 3, 3, 4, 5),
    (1, 1, 2, 4, 3, 3, 4, 5, 6),
    (1, 1, 1, 2, 4, 3, 3, 3, 4, 8, 9, 11),
    (1, 2, 4, 3, 5, 6, 10),
    (1, 1, 2, 4, 3, 3, 4, 5, 7),
)

SERVICES = ("gateway", "auth-svc", "payment-svc", "db-proxy", "cache", "worker")

# Map an anomaly to (root-cause category, biased service) so the supervised classifier has
# a learnable signal in the event-key histogram.
ANOMALY_PROFILE: dict[str, tuple[str, str]] = {
    "ordering": ("abnormal_sequence", "gateway"),
    "error_io": ("io_error", "db-proxy"),
    "error_deadlock": ("deadlock", "worker"),
    "latency": ("latency", "cache"),
}

NORMAL_CATEGORY = "normal"

# Secrets occasionally planted into a line to exercise the redaction layer.
_SECRET_SNIPPETS = (
    " token=ghp_AbC123dEf456GhI789jkl password=hunter2",
    " authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
    " api_key=sk-live-9f8e7d6c5b4a3 user=ops@corp.com",
)


@dataclass(frozen=True)
class SyntheticSession:
    session_id: str
    records: tuple[LogRecord, ...]
    label: int          # 1 = anomalous, 0 = normal
    anomaly_type: str   # "" for normal, else one of ANOMALY_PROFILE keys
    category: str       # root-cause category ground truth


def _ip(rng: random.Random) -> str:
    return f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"


def _render(key: int, blk: str, service: str, rng: random.Random) -> str:
    msg = TEMPLATES[key].format(
        blk=blk, ip=_ip(rng), ip2=_ip(rng),
        port=rng.randint(1024, 65535), port2=rng.randint(1024, 65535),
        n=rng.randint(1, 4000), k=rng.randint(0, 3), svc=service,
    )
    if rng.random() < 0.04:  # plant a secret in ~4% of lines
        msg += rng.choice(_SECRET_SNIPPETS)
    return msg


def _make_keys(rng: random.Random) -> tuple[list[int], int, str, str]:
    """Return (event keys, label, anomaly_type, category) for one session."""
    base = list(rng.choice(NORMAL_PATHS))
    roll = rng.random()
    if roll < 0.80:  # normal
        return base, 0, "", NORMAL_CATEGORY

    if roll < 0.88:  # ordering anomaly: shuffle a middle slice, insert a rare valid key
        i, j = sorted(rng.sample(range(1, len(base)), 2))
        slice_ = base[i:j]
        rng.shuffle(slice_)
        base[i:j] = slice_
        base.insert(rng.randint(1, len(base) - 1), rng.choice([10, 11, 8]))
        cat, _svc = ANOMALY_PROFILE["ordering"]
        return base, 1, "ordering", cat

    if roll < 0.93:  # IO error
        base.insert(rng.randint(1, len(base)), 13)
        if rng.random() < 0.5:
            base.append(14)
        cat, _svc = ANOMALY_PROFILE["error_io"]
        return base, 1, "error_io", cat

    if roll < 0.97:  # deadlock
        base.append(15)
        cat, _svc = ANOMALY_PROFILE["error_deadlock"]
        return base, 1, "error_deadlock", cat

    # latency spike
    for _ in range(rng.randint(2, 4)):
        base.insert(rng.randint(1, len(base)), 12)
    cat, _svc = ANOMALY_PROFILE["latency"]
    return base, 1, "latency", cat


def _service_for(anomaly_type: str, rng: random.Random) -> str:
    if anomaly_type in ANOMALY_PROFILE:
        return ANOMALY_PROFILE[anomaly_type][1]
    return rng.choice(SERVICES)


def generate(
    n_sessions: int = 1800, seed: int = 7, start_ts: float = 1_700_000_000.0
) -> list[SyntheticSession]:
    """Generate ``n_sessions`` labeled sessions deterministically."""
    rng = random.Random(seed)
    sessions: list[SyntheticSession] = []
    ts = start_ts
    for idx in range(n_sessions):
        keys, label, atype, category = _make_keys(rng)
        blk = f"blk_{rng.randint(-9_000_000_000, 9_000_000_000)}"
        service = _service_for(atype, rng)
        records: list[LogRecord] = []
        for key in keys:
            ts += rng.uniform(0.01, 0.4)
            message = _render(key, blk, service, rng)
            records.append(
                LogRecord(timestamp=ts, service=service, session_id=blk,
                          message=message, raw=message)
            )
        sessions.append(
            SyntheticSession(session_id=blk, records=tuple(records),
                             label=label, anomaly_type=atype, category=category)
        )
    return sessions


def write_dataset(target_dir: Path, sessions: list[SyntheticSession]) -> None:
    """Persist sessions to ``logs.jsonl`` and ``labels.csv``."""
    target_dir.mkdir(parents=True, exist_ok=True)
    logs_path = target_dir / "logs.jsonl"
    labels_path = target_dir / "labels.csv"

    with logs_path.open("w", encoding="utf-8") as fh:
        for session in sessions:
            for rec in session.records:
                fh.write(json.dumps({
                    "timestamp": rec.timestamp,
                    "service": rec.service,
                    "session_id": rec.session_id,
                    "message": rec.message,
                }) + "\n")

    with labels_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["session_id", "label", "anomaly_type", "category"])
        for session in sessions:
            writer.writerow([session.session_id, session.label,
                             session.anomaly_type, session.category])
