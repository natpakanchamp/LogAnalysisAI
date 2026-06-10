"""Load datasets into in-memory sessions.

Supports the synthetic ``sample`` dataset (``logs.jsonl`` + ``labels.csv``) and the real
LogHub HDFS format (``HDFS.log`` + ``anomaly_label.csv``).
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from loganalysis.records import LogRecord

_BLOCK_RE = re.compile(r"blk_-?\d+")
_HDFS_LINE_RE = re.compile(
    r"^(?P<date>\d{6})\s+(?P<time>\d{6})\s+\d+\s+(?P<level>\w+)\s+(?P<comp>\S+):\s+(?P<msg>.*)$"
)


@dataclass(frozen=True)
class LabeledSession:
    session_id: str
    records: tuple[LogRecord, ...]
    label: int            # 1 anomalous, 0 normal, -1 unknown
    anomaly_type: str = ""
    category: str = "normal"

    @property
    def messages(self) -> list[str]:
        return [r.message for r in self.records]


def load_sample(dataset_dir: Path) -> list[LabeledSession]:
    """Load the synthetic sample produced by ``scripts/download_data.py --sample``."""
    logs_path = dataset_dir / "logs.jsonl"
    labels_path = dataset_dir / "labels.csv"
    if not logs_path.exists() or not labels_path.exists():
        raise FileNotFoundError(
            f"Sample dataset missing in {dataset_dir}. "
            f"Run: python scripts/download_data.py --sample"
        )

    labels: dict[str, tuple[int, str, str]] = {}
    with labels_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            labels[row["session_id"]] = (
                int(row["label"]), row.get("anomaly_type", ""), row.get("category", "normal"),
            )

    grouped: dict[str, list[LogRecord]] = {}
    order: list[str] = []
    with logs_path.open(encoding="utf-8") as fh:
        for line in fh:
            obj = json.loads(line)
            sid = obj["session_id"]
            if sid not in grouped:
                grouped[sid] = []
                order.append(sid)
            grouped[sid].append(LogRecord(
                timestamp=float(obj["timestamp"]), service=obj["service"],
                session_id=sid, message=obj["message"], raw=obj.get("raw", obj["message"]),
            ))

    sessions: list[LabeledSession] = []
    for sid in order:
        label, atype, category = labels.get(sid, (-1, "", "normal"))
        sessions.append(LabeledSession(
            session_id=sid, records=tuple(grouped[sid]),
            label=label, anomaly_type=atype, category=category,
        ))
    return sessions


def load_hdfs(dataset_dir: Path, limit: int | None = None) -> list[LabeledSession]:
    """Load the real LogHub HDFS_v1 dataset (block-level labels)."""
    log_path = dataset_dir / "HDFS.log"
    label_path = dataset_dir / "anomaly_label.csv"
    if not log_path.exists() or not label_path.exists():
        raise FileNotFoundError(
            f"HDFS dataset missing in {dataset_dir} (need HDFS.log + anomaly_label.csv). "
            f"See data/README.md."
        )

    labels: dict[str, int] = {}
    with label_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            labels[row["BlockId"]] = 1 if row["Label"].strip().lower() == "anomaly" else 0

    grouped: dict[str, list[LogRecord]] = {}
    order: list[str] = []
    with log_path.open(encoding="utf-8", errors="ignore") as fh:
        for i, line in enumerate(fh):
            if limit is not None and i >= limit:
                break
            m = _HDFS_LINE_RE.match(line.strip())
            msg = m.group("msg") if m else line.strip()
            comp = m.group("comp") if m else "hdfs"
            blocks = _BLOCK_RE.findall(line)
            if not blocks:
                continue
            sid = blocks[0]
            if sid not in grouped:
                grouped[sid] = []
                order.append(sid)
            grouped[sid].append(LogRecord(
                timestamp=float(i), service=comp, session_id=sid, message=msg, raw=line.strip(),
            ))

    sessions: list[LabeledSession] = []
    for sid in order:
        sessions.append(LabeledSession(
            session_id=sid, records=tuple(grouped[sid]),
            label=labels.get(sid, -1),
            anomaly_type="" if labels.get(sid, 0) == 0 else "hdfs_anomaly",
            category="normal" if labels.get(sid, 0) == 0 else "abnormal_sequence",
        ))
    return sessions


def load_dataset(name: str, dataset_dir: Path, limit: int | None = None) -> list[LabeledSession]:
    if name == "sample":
        return load_sample(dataset_dir)
    if name == "hdfs":
        return load_hdfs(dataset_dir, limit=limit)
    raise ValueError(f"Unknown dataset '{name}' (expected 'sample' or 'hdfs').")
