# Dataset Comparison — Synthetic vs. Real HDFS

Same model + hyperparameters (PRD §04/§05), trained and evaluated independently on each dataset. The template summarizer is used during evaluation (no LLM calls).

## Dataset shape

| | Synthetic (sample) | Real HDFS_v1 |
|---|---|---|
| Total sessions | 1800 | 12000 |
| Train / Test | 1260 / 540 | 8400 / 3600 |
| Test anomalies | 98 | 113 |
| Event templates (Drain) | 42 | 30 |
| Epochs | 60 | 60 |

## DeepLog detector metrics

| Metric | Synthetic | Real HDFS |
|---|---|---|
| Precision | 0.812 | 0.146 |
| Recall | 0.663 | 0.991 |
| F1 | 0.730 | 0.254 |
| Recall (high-severity) | 1.000 | 1.000 |
| Accuracy | 0.911 | 0.817 |
| TP / FP / FN / TN | 65/15/33/427 | 112/657/1/2830 |

## Rule-based baseline

| Metric | Synthetic | Real HDFS |
|---|---|---|
| Precision | 1.000 | 0.092 |
| Recall | 0.418 | 0.681 |
| AI-only catches (rules missed) | 28 | 36 |

## PRD threshold result

- Synthetic: **SOME NOT MET**
- Real HDFS: **SOME NOT MET**
