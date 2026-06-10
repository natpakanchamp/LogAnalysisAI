"""Save/load the trained artifact bundle (parser + detector + classifier)."""

from __future__ import annotations

from pathlib import Path

import torch

from loganalysis.classification.root_cause import RootCauseClassifier
from loganalysis.detection.deeplog import DeepLogDetector
from loganalysis.parsing.drain_parser import DrainParser

BUNDLE_NAME = "model_bundle.pt"


def save_bundle(
    path: Path, parser: DrainParser, detector: DeepLogDetector, classifier: RootCauseClassifier
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {"parser": parser, "deeplog": detector.state(), "classifier": classifier.state()},
        path,
    )


def load_bundle(
    path: Path, device: str | None = None
) -> tuple[DrainParser, DeepLogDetector, RootCauseClassifier]:
    # weights_only=False: the bundle contains the (trusted, locally produced) parser and
    # sklearn objects, not just tensors.
    data = torch.load(Path(path), weights_only=False, map_location=device or "cpu")
    parser: DrainParser = data["parser"]
    detector = DeepLogDetector.from_state(data["deeplog"], device=device)
    classifier = RootCauseClassifier.from_state(data["classifier"])
    return parser, detector, classifier
