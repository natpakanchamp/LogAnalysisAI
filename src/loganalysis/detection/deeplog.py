"""DeepLog: LSTM next-event anomaly detection.

Ported and condensed from `d0ng1ee/logdeep` (MIT) and the original DeepLog paper
(Du et al., CCS'17). The model learns, from **normal** sessions, to predict the next event
key given a window of preceding keys. At inference a window is anomalous when the actual
next key falls outside the model's top-``g`` predictions; a session is anomalous if any of
its windows is. An *unseen* template (UNKNOWN_KEY) is anomalous by construction.
"""

from __future__ import annotations

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from loganalysis.detection.base import DetectionResult, SequenceDetector
from loganalysis.features.sequencer import build_training_pairs, sliding_windows


class _DeepLogLSTM(nn.Module):
    def __init__(self, num_keys: int, embedding_dim: int, hidden_size: int, num_layers: int):
        super().__init__()
        # +1 row reserved for the UNKNOWN key in the input embedding.
        self.embedding = nn.Embedding(num_keys + 1, embedding_dim)
        self.lstm = nn.LSTM(embedding_dim, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, num_keys)  # predict over known keys only

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        emb = self.embedding(x)
        out, _ = self.lstm(emb)
        return self.fc(out[:, -1, :])


class DeepLogDetector(SequenceDetector):
    name = "deeplog"

    def __init__(
        self,
        num_keys: int,
        window_size: int = 10,
        num_candidates: int = 9,
        embedding_dim: int = 32,
        hidden_size: int = 64,
        num_layers: int = 2,
        epochs: int = 30,
        batch_size: int = 64,
        learning_rate: float = 1e-3,
        device: str | None = None,
        seed: int = 42,
    ) -> None:
        self.seed = seed
        self.num_keys = num_keys
        self.window_size = window_size
        self.num_candidates = min(num_candidates, max(1, num_keys))
        self.embedding_dim = embedding_dim
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.device = torch.device(device or "cpu")
        self.model = _DeepLogLSTM(num_keys, embedding_dim, hidden_size, num_layers).to(self.device)

    # --- input encoding ---------------------------------------------------------------
    def _encode_key(self, key: int) -> int:
        """Map a key to an embedding row; unknown/out-of-range → reserved last row."""
        if 0 <= key < self.num_keys:
            return key
        return self.num_keys  # UNKNOWN slot

    # --- training ---------------------------------------------------------------------
    def fit(self, normal_sequences: list[list[int]]) -> None:
        torch.manual_seed(self.seed)  # reproducible training
        histories, targets = build_training_pairs(normal_sequences, self.window_size)
        if not histories:
            return
        x = torch.tensor(
            [[self._encode_key(k) for k in h] for h in histories],
            dtype=torch.long, device=self.device,
        )
        y = torch.tensor(targets, dtype=torch.long, device=self.device)
        loader = DataLoader(TensorDataset(x, y), batch_size=self.batch_size, shuffle=True)

        optimizer = torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        criterion = nn.CrossEntropyLoss()
        self.model.train()
        for _ in range(self.epochs):
            for xb, yb in loader:
                optimizer.zero_grad()
                loss = criterion(self.model(xb), yb)
                loss.backward()
                optimizer.step()
        self.model.eval()

    # --- inference --------------------------------------------------------------------
    @torch.no_grad()
    def predict(self, sequence: list[int]) -> DetectionResult:
        self.model.eval()
        flagged_positions: list[int] = []
        anomalous_certainties: list[float] = []  # 1 - p(actual) on flagged windows
        normal_certainties: list[float] = []      # p(actual) on non-flagged windows

        for pos, (history, nxt) in enumerate(sliding_windows(sequence, self.window_size)):
            xb = torch.tensor(
                [[self._encode_key(k) for k in history]], dtype=torch.long, device=self.device
            )
            probs = torch.softmax(self.model(xb), dim=1).squeeze(0)

            if not (0 <= nxt < self.num_keys):
                # Unseen template: certainly anomalous.
                flagged_positions.append(pos)
                anomalous_certainties.append(1.0)
                continue

            p_actual = float(probs[nxt])
            topk = torch.topk(probs, self.num_candidates).indices.tolist()
            if nxt in topk:
                normal_certainties.append(p_actual)
            else:
                flagged_positions.append(pos)
                anomalous_certainties.append(1.0 - p_actual)

        is_anomaly = bool(flagged_positions)
        if is_anomaly:
            anomaly_score = max(anomalous_certainties)
            confidence = sum(anomalous_certainties) / len(anomalous_certainties)
            detail = f"{len(flagged_positions)} window(s) outside top-{self.num_candidates}"
        else:
            anomaly_score = 0.0
            confidence = (
                sum(normal_certainties) / len(normal_certainties) if normal_certainties else 1.0
            )
            detail = "all windows within expected next-event set"

        return DetectionResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            confidence=confidence,
            detector=self.name,
            anomalous_positions=tuple(flagged_positions),
            detail=detail,
        )

    # --- persistence ------------------------------------------------------------------
    def state(self) -> dict:
        return {
            "model_state": self.model.state_dict(),
            "num_keys": self.num_keys,
            "window_size": self.window_size,
            "num_candidates": self.num_candidates,
            "embedding_dim": self.embedding_dim,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
        }

    @classmethod
    def from_state(cls, state: dict, device: str | None = None) -> "DeepLogDetector":
        det = cls(
            num_keys=state["num_keys"],
            window_size=state["window_size"],
            num_candidates=state["num_candidates"],
            embedding_dim=state["embedding_dim"],
            hidden_size=state["hidden_size"],
            num_layers=state["num_layers"],
            device=device,
        )
        det.model.load_state_dict(state["model_state"])
        det.model.eval()
        return det
