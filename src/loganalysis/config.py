"""Central configuration. Thresholds are sourced directly from the PRD (§04, §05).

All values have safe defaults so the pipeline runs offline with no environment setup.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
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
    # Read without the LOGANALYSIS_ prefix to match the conventional variable name.
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    llm_model: str = "claude-haiku-4-5"
    llm_max_tokens: int = 320

    # --- HITL trigger thresholds (PRD §05) -------------------------------------------
    confidence_threshold: float = 0.65  # below this → human review

    # --- Success-metric targets (PRD §04) --------------------------------------------
    recall_target_high_severity: float = 0.90
    precision_target_overall: float = 0.70
    f1_target: float = 0.77

    # --- DeepLog detector hyperparameters --------------------------------------------
    window_size: int = 10        # length of the event-key history window
    num_candidates: int = 2      # 'g': actual key must be in top-g predictions (tuned on sample)
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
