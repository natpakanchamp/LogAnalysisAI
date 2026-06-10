# Datasets

This project trains and evaluates on system-log datasets. Two options:

## 1. Synthetic sample (default, no download)

```bash
python scripts/download_data.py --sample
```

Writes `data/sample/` with:
- `logs.jsonl` — HDFS-style log lines (timestamp, service, block_id, message), some with
  planted secrets to exercise the redaction layer.
- `labels.csv` — `block_id,label,anomaly_type` ground truth.

Anomaly types injected:
- `ordering` — valid event keys in an abnormal order (no error keyword). DeepLog catches
  these; the rule-based baseline misses them. This demonstrates the PRD business metric
  *"incidents rule-based can't detect but AI does > 0"*.
- `error` — a session containing an explicit error/exception event.

## 2. Real LogHub datasets (for true metric validation)

The PRD's thresholds (e.g. Recall ≥ 0.90 on high-severity) are best validated on the full
public datasets from [`logpai/loghub`](https://github.com/logpai/loghub):

### HDFS_v1
- 11.2M log messages, 575,061 blocks, 16,838 (2.93%) anomalous — block-level labels.
- Download: https://github.com/logpai/loghub (HDFS link → Zenodo), or Kaggle mirrors of
  the HDFS log dataset.
- Place `HDFS.log` and `anomaly_label.csv` under `data/hdfs/`, then:
  ```bash
  python scripts/train.py --dataset hdfs
  python scripts/evaluate.py --dataset hdfs
  ```

### BGL
- 4.7M messages, 348,460 (7.34%) anomalous — line-level labels.
- Place `BGL.log` under `data/bgl/`.

> Datasets are **not committed** (see `.gitignore`) and are provided by LogHub for research
> use. Respect their original terms.
