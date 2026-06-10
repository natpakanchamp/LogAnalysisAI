"""Supervised root-cause classifier (PRD §02: Classification).

Maps a session's event-key histogram to a root-cause category
(normal / abnormal_sequence / io_error / deadlock / latency). A logistic-regression model
is deliberate and lightweight: it trains in milliseconds and exposes calibrated class
probabilities we reuse as a classification confidence.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

NORMAL_CATEGORY = "normal"


class RootCauseClassifier:
    def __init__(self, num_keys: int) -> None:
        self.num_keys = num_keys
        self._model: LogisticRegression | None = None
        self._fallback_category = NORMAL_CATEGORY

    def _featurize(self, sequence: list[int]) -> np.ndarray:
        vec = np.zeros(self.num_keys, dtype=np.float64)
        for key in sequence:
            if 0 <= key < self.num_keys:
                vec[key] += 1.0
        total = vec.sum()
        if total > 0:
            vec /= total  # normalize to a distribution over event keys
        return vec

    def fit(self, sequences: list[list[int]], categories: list[str]) -> None:
        if not sequences:
            return
        x = np.vstack([self._featurize(s) for s in sequences])
        y = np.asarray(categories)
        unique = set(y.tolist())
        if len(unique) < 2:
            # Only one class present — nothing to learn; remember it as the fallback.
            self._fallback_category = next(iter(unique))
            self._model = None
            return
        # Modern scikit-learn (>=1.7) handles multinomial automatically; the old
        # ``multi_class`` argument was removed.
        self._model = LogisticRegression(max_iter=1000)
        self._model.fit(x, y)

    def predict(self, sequence: list[int]) -> tuple[str, float]:
        """Return (category, confidence)."""
        if self._model is None:
            return self._fallback_category, 1.0
        x = self._featurize(sequence).reshape(1, -1)
        proba = self._model.predict_proba(x)[0]
        idx = int(np.argmax(proba))
        return str(self._model.classes_[idx]), float(proba[idx])

    # --- persistence ------------------------------------------------------------------
    def state(self) -> dict:
        return {
            "num_keys": self.num_keys,
            "model": self._model,
            "fallback_category": self._fallback_category,
        }

    @classmethod
    def from_state(cls, state: dict) -> "RootCauseClassifier":
        clf = cls(num_keys=state["num_keys"])
        clf._model = state["model"]
        clf._fallback_category = state.get("fallback_category", NORMAL_CATEGORY)
        return clf
