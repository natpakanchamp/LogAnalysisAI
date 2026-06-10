# Plan: Log Analysis AI — Real-time Log Anomaly Detection & Root-Cause Assistant

**Source PRD**: `~/Downloads/PRD_CPS250041_ณัฐปคัลภ์.docx.pdf` (Natpakan Kanthasorn, True Digital Academy M5)
**Decisions**: Runnable MVP prototype · Claude API summarizer (template fallback) · Backend + lightweight dashboard
**Complexity**: Large (greenfield: ML + API + UI)

## Summary
A runnable prototype of the PRD's "ผู้ช่วยวิเคราะห์ Log" — it replays public system-log datasets (HDFS/BGL) as a simulated real-time stream, redacts secrets, parses logs to templates, detects anomalies with a DeepLog-style LSTM (vs a rule-based baseline), classifies root cause, scores severity + confidence, summarizes the cause with Claude, and emits alerts. Flagged alerts (confidence < 0.65, AI-vs-rule conflict, heartbeat deadlock) go to a HITL dashboard for accept/reject, writing feedback for retraining. An evaluation script scores Recall / Precision / MTTD against the PRD thresholds.

## Reusable AI Assets (verified, from GitHub + Kaggle)
| Asset | Source | License | Use in project |
|---|---|---|---|
| Drain3 | `logpai/Drain3` → pip `drain3` (IBM) | MIT | Streaming log → template parsing |
| DeepLog (LSTM) | ported from `d0ng1ee/logdeep` | MIT | Next-event anomaly detector (core model) |
| LogBERT | `HelenGuohx/logbert` | MIT | Stretch/alt detector (documented, not built v1) |
| LogAI | `salesforce/logai` | BSD-3 | Reference for parsing/feature patterns |
| LogHub HDFS/BGL | `logpai/loghub` + Kaggle mirrors | research-use | Train/eval datasets (2k sample for tests; full for metrics) |

## Tech Stack
Python 3.11 · PyTorch (DeepLog) · `drain3` (parsing) · scikit-learn (metrics/classifier) · `anthropic` SDK (`claude-haiku-4-5`) · FastAPI + vanilla JS dashboard · `pydantic-settings` (config) · pytest.

## Architecture / Pipeline
```
raw logs (HDFS/BGL replay)
  → ingestion/stream (simulated real-time)
  → redaction (scrub tokens/passwords/PII)   ← PRD §03 data risk
  → parsing/Drain3 (line → event id/template)
  → features/sequencer (event-id windows per block/session)
  → detection: DeepLog (LSTM)  +  rule_based baseline
  → classification/root_cause (category + suspect service/commit)
  → scoring/severity (severity + confidence)
  → summarize/LLM (Claude → human-readable cause; template fallback)
  → alerting/alert (JSON envelope: severity, confidence, summary, suspects)
  → alerting/hitl (flag triggers from PRD §05)
  → dashboard (feed + accept/reject) → feedback/store (JSONL, retrain input)
```

## File Layout (many small files, <800 lines each)
```
src/loganalysis/{config.py, pipeline.py}
  ingestion/{stream.py, loader.py}
  redaction/redactor.py
  parsing/drain_parser.py
  features/sequencer.py
  detection/{base.py, deeplog.py, rule_based.py}
  classification/root_cause.py
  scoring/severity.py
  summarize/{llm_summarizer.py, templates.py}
  alerting/{alert.py, hitl.py}
  feedback/store.py
  metrics/evaluation.py
api/{main.py, routes.py, static/(index.html, app.js, styles.css)}
scripts/{download_data.py, train.py, evaluate.py}
tests/{test_redactor, test_drain_parser, test_detection, test_hitl, test_alert, test_evaluation}.py
README.md · pyproject.toml · requirements.txt · .env.example · .gitignore · data/README.md
```

## Phases & Tasks
- **P0 Scaffold**: pyproject/requirements, config (thresholds from PRD §04), .gitignore (data/, models/, .env), .env.example, README, data/README.
- **P1 Data + Redaction + Parsing** *(TDD: redactor, drain wrapper)*: loghub loader + download script; secret redactor; Drain3 wrapper; sequencer.
- **P2 Detection** *(TDD: rule_based, synthetic-sequence detector test)*: Detector interface (repository pattern); rule baseline; DeepLog LSTM (ported, cited); train.py.
- **P3 Classification + Scoring + Summarize**: root-cause categorizer; severity+confidence; Claude summarizer + offline template fallback.
- **P4 Alerting + HITL + Feedback** *(TDD: alert envelope, hitl triggers)*: alert JSON envelope; HITL flag logic (conf<0.65 / AI-vs-rule conflict / heartbeat deadlock); JSONL feedback store.
- **P5 Pipeline + Metrics** *(TDD: evaluation math)*: orchestrate flow; evaluate.py → Recall/Precision/F1/MTTD vs thresholds (PASS/FAIL); rule-vs-AI "AI catches what rules miss" count.
- **P6 Dashboard**: FastAPI `/alerts`,`/feedback`,`/stream`; dark "mission-control" alert console (intentional, not a template) with severity/confidence chips + accept/reject HITL button.
- **P7 Verify**: run tests, produce eval report, README results, code review.

## Validation
```bash
pip install -e ".[dev]"
python scripts/download_data.py --sample        # loghub HDFS 2k sample
pytest -q --cov=src/loganalysis                  # target 80%+
python scripts/train.py --dataset hdfs_sample
python scripts/evaluate.py --dataset hdfs_sample # Recall/Precision/MTTD vs PRD thresholds
uvicorn api.main:app --reload                    # dashboard at :8000
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Full HDFS (~1.5GB) needed to truly hit Recall≥0.90 | High | Ship 2k sample for tests/demo; download script for full set; eval reports actual vs threshold |
| DeepLog port correctness | Medium | Validate on synthetic sequence with known injected anomaly |
| Training time | Medium | Few epochs on sample; document full-run settings |
| No Claude API key present | Low | Deterministic template fallback summarizer |
| loghub data license (research/NOASSERTION) | Low | Never commit data; document source + usage |

## Acceptance
- [ ] Pipeline runs end-to-end on HDFS sample and emits alert JSON with severity + confidence + summary
- [ ] HITL flagging matches PRD §05 triggers; dashboard accept/reject writes feedback
- [ ] Redaction strips tokens/passwords/PII before model
- [ ] evaluate.py reports Recall/Precision/F1/MTTD against PRD thresholds + "AI-beats-rules" count
- [ ] Tests pass, 80%+ coverage on core logic
- [ ] README documents which GitHub/Kaggle models were used and how to fetch data
