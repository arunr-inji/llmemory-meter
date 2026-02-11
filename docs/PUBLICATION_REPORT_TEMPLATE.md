# Publication Report Template

Use this template for the final results package.

## 1. Summary

- Study objective:
- Release tag / commit SHA:
- Run window (UTC):
- Primary configs:
- Benchmarks included:
- Memory tools included:

## 2. Environment and Reproducibility

- OS / runtime:
- Python version:
- Dependency snapshot (`pip freeze` file path):
- Dataset versions / source URLs:
- Secrets policy used (no keys in outputs):

## 3. Methodology

- Run command(s):
- Number of repeated trials per config:
- Timeout / retry settings:
- Judge model for LongMemEval hybrid evaluation:
- Any exclusions and why:

## 4. Core Results

### 4.1 Aggregate Metrics

| Tool | Benchmark | Success Rate | Avg Latency (ms) | Token Usage | Cost Estimate |
|---|---|---|---|---|---|
| | | | | | |

### 4.2 Hybrid Evaluation (LongMemEval)

| Tool | Judge Model | Accuracy | Notes |
|---|---|---|---|
| | | | |

### 4.3 Reliability Across Repeats

| Tool | Benchmark | Trials | Mean | Std Dev | Failure Count |
|---|---|---|---|---|---|
| | | | | | |

## 5. Statistical Notes

- Confidence interval method:
- Significance testing used (if any):
- Known limitations in interpretation:

## 6. Security and Data Integrity Checks

- Input validation status:
- Subprocess boundary review status:
- Dataset download integrity checks:
- Any unresolved risks:

## 7. Known Issues and Caveats

- Operational caveats:
- Benchmark-specific caveats:
- Cost caveats:

## 8. Artifact Manifest

- Raw logs directory:
- Raw results directory:
- Processed tables path:
- Plots path:
- Final report path:
- Checksums / provenance manifest path:

## 9. Reproduction Instructions

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run_overnight.sh configs/industry-benchmarks.yml
.venv/bin/python llmemory evaluate --benchmark LongMemEval --judge gpt-4o --results <results_file> --config configs/industry-benchmarks.yml
```

## 10. Approval

- Technical reviewer:
- Security reviewer:
- Publish decision:
- Date:
