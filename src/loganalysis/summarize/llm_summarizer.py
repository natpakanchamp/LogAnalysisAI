"""LLM root-cause summarizer (PRD §02: Generative AI).

Uses Anthropic Claude to turn structured detection output into a short, human-readable
root-cause explanation for the on-call engineer. Falls back to a deterministic template
when no API key is configured or any error occurs — the pipeline must never fail because
the LLM is unavailable (PRD §06 mitigations).
"""

from __future__ import annotations

from loganalysis.config import settings
from loganalysis.summarize.templates import template_summary

_SYSTEM_PROMPT = (
    "You are an SRE assistant. Given structured anomaly-detection output from a log "
    "monitoring system, write a concise root-cause summary for the on-call engineer in "
    "2-3 sentences. State the most likely cause, the suspect service/commit, and one next "
    "step. Be specific and do not invent details beyond the evidence."
)


class Summarizer:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.model = model or settings.llm_model
        self._client = None
        key = api_key if api_key is not None else settings.anthropic_api_key
        if key:
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=key)
            except Exception:  # pragma: no cover - import/credential issues degrade gracefully
                self._client = None

    @property
    def uses_llm(self) -> bool:
        return self._client is not None

    def summarize(
        self,
        *,
        category: str,
        severity: str,
        suspect_service: str,
        suspect_commit: str,
        sample_messages: list[str],
        detectors: list[str],
        anomaly_score: float,
        confidence: float,
    ) -> str:
        fallback = template_summary(
            category=category, severity=severity, suspect_service=suspect_service,
            suspect_commit=suspect_commit, sample_messages=sample_messages, detectors=detectors,
        )
        if self._client is None:
            return fallback

        prompt = _build_prompt(
            category=category, severity=severity, suspect_service=suspect_service,
            suspect_commit=suspect_commit, sample_messages=sample_messages,
            detectors=detectors, anomaly_score=anomaly_score, confidence=confidence,
        )
        try:
            message = self._client.messages.create(
                model=self.model,
                max_tokens=settings.llm_max_tokens,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                block.text for block in message.content if getattr(block, "type", "") == "text"
            ).strip()
            return text or fallback
        except Exception:  # pragma: no cover - network/credential failures fall back
            return fallback


def _build_prompt(
    *, category: str, severity: str, suspect_service: str, suspect_commit: str,
    sample_messages: list[str], detectors: list[str], anomaly_score: float, confidence: float,
) -> str:
    evidence = "\n".join(f"  - {m[:160]}" for m in sample_messages[:5]) or "  - (none)"
    return (
        f"Anomaly detected.\n"
        f"Severity: {severity}\n"
        f"Root-cause category (classifier): {category}\n"
        f"Suspect service: {suspect_service}\n"
        f"Suspect commit: {suspect_commit or 'unknown'}\n"
        f"Detectors that fired: {', '.join(detectors) or 'none'}\n"
        f"Anomaly score: {anomaly_score:.2f} | Model confidence: {confidence:.2f}\n"
        f"Sample log lines (already redacted):\n{evidence}\n"
    )
