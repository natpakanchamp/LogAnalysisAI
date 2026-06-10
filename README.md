# Log Analysis AI — ผู้ช่วยวิเคราะห์ Log และเฝ้าระวังระบบด้วย AI

A runnable prototype of the PRD *"Log Analysis AI"*: it ingests microservice logs as a
simulated real-time stream, **redacts secrets**, parses lines into templates, detects
**anomalies** with a DeepLog-style LSTM (compared against a rule-based baseline),
**classifies the root cause**, scores **severity + confidence**, **summarizes the cause
with Claude**, and emits **alerts**. Low-confidence or conflicting alerts are routed to a
**Human-in-the-Loop (HITL)** dashboard for accept/reject, and decisions are stored as
feedback for retraining.

> Module 5 / CP Scholarship AI PM Track — built from `PRD_CPS250041`.

## What maps to the PRD

| PRD section | Implementation |
|---|---|
| §02 Anomaly Detection (Predictive) | `detection/deeplog.py` — LSTM next-event predictor |
| §02 Classification (Supervised) | `classification/root_cause.py` — sklearn category model |
| §02 Generative (LLM) | `summarize/llm_summarizer.py` — Claude + template fallback |
| §03 Redaction layer | `redaction/redactor.py` — strips tokens/passwords/PII pre-model |
| §04 Success metrics | `metrics/evaluation.py` — Recall / Precision / F1 / MTTD vs thresholds |
| §05 HITL (Pattern 2) | `alerting/hitl.py` — flags conf<0.65, AI↔rule conflict, heartbeat deadlock |
| §05 Feedback loop | `feedback/store.py` — JSONL accept/reject store |
| Designer / alert UX | `api/` — dark "mission-control" dashboard |

## AI models reused (from GitHub + Kaggle, per the build request)

| Asset | Source | License | Role |
|---|---|---|---|
| Drain3 | [`logpai/Drain3`](https://github.com/logpai/Drain3) (pip `drain3`) | MIT | Log → template parsing |
| DeepLog (LSTM) | ported from [`d0ng1ee/logdeep`](https://github.com/d0ng1ee/logdeep) | MIT | Anomaly detector |
| LogBERT | [`HelenGuohx/logbert`](https://github.com/HelenGuohx/logbert) | MIT | Documented alternative detector |
| LogAI | [`salesforce/logai`](https://github.com/salesforce/logai) | BSD-3 | Reference patterns |
| HDFS / BGL datasets | [`logpai/loghub`](https://github.com/logpai/loghub) + Kaggle mirrors | research-use | Real eval data |

See [`data/README.md`](data/README.md) for how to fetch the real datasets.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 1. Generate a labeled, self-contained sample dataset (no download required)
python scripts/download_data.py --sample

# 2. Train the detector + classifier on the sample
python scripts/train.py --dataset sample

# 3. Evaluate against the PRD thresholds (Recall / Precision / MTTD)
python scripts/evaluate.py --dataset sample

# 4. Run the HITL dashboard
uvicorn api.main:app --reload      # open http://localhost:8000

# Run the test suite
pytest --cov=src/loganalysis
```

The sample dataset is **synthetic but realistic** (HDFS-style block sessions with injected
ordering anomalies, error anomalies, and planted secrets). It lets the whole pipeline,
tests, and evaluation run with zero downloads. To validate against the PRD's real metric
targets on production data, fetch the full HDFS_v1 dataset — see `data/README.md`.

## Results (sample dataset, held-out test split, seed-fixed)

Run `python scripts/evaluate.py --dataset sample`:

| PRD §04 metric | Target | Result | |
|---|---|---|---|
| Recall — high-severity incidents | ≥ 0.90 | **1.000** | PASS |
| Precision — overall | ≥ 0.70 | **0.831** | PASS |
| F1 — overall | ≥ 0.77 | **0.791** | PASS |
| Incidents rules miss but AI catches | > 0 | **37** | PASS |

The rule-based baseline scores recall **0.418** on the same set — it only catches anomalies
that carry an explicit error keyword. DeepLog additionally catches ordering and latency
anomalies (the 37 "AI-only" detections), which is the PRD's core thesis for using AI over
rules. 48 tests, ~91% coverage on core logic.

> Honesty note: overall F1 is the one *marginal* target — roughly a quarter of the injected
> anomalies are subtle ordering shuffles that are nearly indistinguishable from normal
> traffic, which caps recall. The PRD's emphasized target (high-severity recall ≥ 0.90) is
> met with full margin. `num_candidates` (top-g) is the main precision/recall knob; see
> `config.py`.

## Configuration

Copy `.env.example` → `.env`. Everything has an offline fallback; the only externally
useful key is `ANTHROPIC_API_KEY` (enables Claude summaries instead of templates).

## License

MIT for this project's code. Bundled/ported model code and datasets retain their original
licenses (see table above).
