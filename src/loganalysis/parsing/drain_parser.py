"""Streaming log → template parsing via Drain3 (logpai/Drain3, MIT).

Drain3 mines a stable template for each log line. We wrap it to expose a *contiguous*
event-key index (0..N-1) suitable for the DeepLog embedding, plus an explicit
``UNKNOWN_KEY`` for lines that match no learned template at inference time (an unseen
template is, by construction, anomalous to a next-event model).
"""

from __future__ import annotations

from drain3 import TemplateMiner
from drain3.masking import MaskingInstruction
from drain3.template_miner_config import TemplateMinerConfig

UNKNOWN_KEY = -1

# Mask volatile tokens (block ids, IPs, numbers, hex) so a template generalizes from the
# first example and matching is robust to changing parameter values. Order matters: the
# more specific block-id rule must run before the generic number rule.
_MASKING = [
    MaskingInstruction(r"blk_-?\d+", "BLK"),
    MaskingInstruction(r"(\d{1,3}\.){3}\d{1,3}(:\d+)?", "IP"),
    MaskingInstruction(r"0x[0-9a-fA-F]+", "HEX"),
    MaskingInstruction(r"\b\d+\b", "NUM"),
]


def _build_config() -> TemplateMinerConfig:
    cfg = TemplateMinerConfig()
    cfg.profiling_enabled = False
    cfg.drain_sim_th = 0.4          # similarity threshold for the same template
    cfg.drain_depth = 4
    cfg.masking_instructions = _MASKING
    return cfg


class DrainParser:
    """Learns templates during :meth:`fit` and freezes them for :meth:`transform`."""

    def __init__(self) -> None:
        self._miner = TemplateMiner(config=_build_config())
        self._cluster_to_index: dict[int, int] = {}
        self._frozen = False

    @property
    def num_keys(self) -> int:
        return len(self._cluster_to_index)

    def _index_for_cluster(self, cluster_id: int) -> int:
        idx = self._cluster_to_index.get(cluster_id)
        if idx is None:
            idx = len(self._cluster_to_index)
            self._cluster_to_index[cluster_id] = idx
        return idx

    def fit_line(self, message: str) -> int:
        """Learn from a line and return its (possibly new) event-key index."""
        result = self._miner.add_log_message(message)
        return self._index_for_cluster(result["cluster_id"])

    def fit(self, messages: list[str]) -> list[int]:
        return [self.fit_line(m) for m in messages]

    def transform_line(self, message: str) -> int:
        """Match a line against frozen templates. Returns ``UNKNOWN_KEY`` if none match."""
        cluster = self._miner.match(message)
        if cluster is None:
            return UNKNOWN_KEY
        return self._cluster_to_index.get(cluster.cluster_id, UNKNOWN_KEY)

    def transform(self, messages: list[str]) -> list[int]:
        return [self.transform_line(m) for m in messages]

    def template_of(self, message: str) -> str:
        cluster = self._miner.match(message)
        return cluster.get_template() if cluster is not None else message

    def freeze(self) -> "DrainParser":
        """Mark the parser as trained. The instance is picklable for persistence."""
        self._frozen = True
        return self
