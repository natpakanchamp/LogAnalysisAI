"""Central configuration. Thresholds are sourced directly from the PRD (§04, §05).

All values have safe defaults so the pipeline runs offline with no environment setup.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root (…/LogAnalysisAI), independent of the current working directory.
ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings, overridable via environment variables or a ``.env`` file."""

    model_config = SettingsConfigDict(
        env_prefix="LOGANALYSIS_",
        env_file=".env",
        extra="ignore",
        protected_namespaces=(),
    )

    # --- LLM summarizer (Generative AI, PRD §02) -------------------------------------
    # Uses the Google Gemini API (free tier). Read the key without the LOGANALYSIS_
    # prefix to match Google's conventional variable names (GEMINI_API_KEY / GOOGLE_API_KEY).
    gemini_api_key: str = Field(
        default="", validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY")
    )
    llm_model: str = "gemini-2.5-flash"
    llm_max_tokens: int = 320

    # --- HITL trigger thresholds (PRD §05) -------------------------------------------
    confidence_threshold: float = 0.65  # below this → human review

    # --- Success-metric targets (PRD §04) --------------------------------------------
    recall_target_high_severity: float = 0.90
    precision_target_overall: float = 0.70
    f1_target: float = 0.77

    # --- DeepLog detector hyperparameters --------------------------------------------
    window_size: int = 10        # length of the event-key history window
    # 'g': the actual next key must fall in the model's top-g predictions, else the window is
    # flagged. This is the main precision/recall knob and is dataset-dependent (see
    # scripts/sweep_candidates.py): g=2 is optimal for the synthetic sample (F1 0.79), while
    # real HDFS_v1 needs g=4 (F1 0.25 -> 0.84) because production logs vary more per window.
    num_candidates: int = 2
    num_candidates_hdfs: int = 4  # empirical optimum for HDFS_v1 (sweep, high-sev recall 1.0)
    embedding_dim: int = 32
    hidden_size: int = 64
    num_layers: int = 2
    epochs: int = 60
    batch_size: int = 64
    learning_rate: float = 1e-3

    # --- Paths ------------------------------------------------------------------------
    data_dir: Path = ROOT_DIR / "data"
    models_dir: Path = ROOT_DIR / "models"

    def dataset_dir(self, name: str) -> Path:
        return self.data_dir / name

    def artifact_path(self, name: str) -> Path:
        return self.models_dir / name


# Resolve the .env relative to the repo root regardless of CWD.
settings = Settings(_env_file=ROOT_DIR / ".env")  # type: ignore[call-arg]
