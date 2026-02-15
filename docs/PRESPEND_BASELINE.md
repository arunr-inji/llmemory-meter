# Pre-Spend Baseline Freeze

Use this checklist before paid runs.

## Baseline Identity

- Branch: `codex/arunr-validation-publish-readiness`
- Config (full run): `configs/industry-benchmarks.yml`
- Config (pilot): `configs/industry-benchmarks-pilot.yml`
- Commit SHA: run `git rev-parse HEAD`

## Environment Snapshot

```bash
python3 --version
pip freeze > results/validation_runs/dependency_snapshot.txt
```

## Required Environment Variables

- `MEM0_API_KEY`
- `OPENAI_API_KEY` (used by Mem0 llm provider)
- `MEMGPT_API_KEY`
- `ZEP_API_KEY`

## Required Service

```bash
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant
```

## Pre-Spend Validation Commands

```bash
./scripts/validate_and_publish_prep.sh scripts/fixtures/industry_fixture.json
python3 scripts/check_metric_fixtures.py
python3 scripts/check_metrics_reconciliation.py scripts/fixtures/reconciliation_fixture.json --report-file results/validation_runs/reconciliation_fixture_report.json
python3 scripts/membench_eval.py scripts/fixtures/membench_hypothesis_fixture.jsonl
```

## Pilot Command

```bash
./run_overnight.sh configs/industry-benchmarks-pilot.yml
```

## Gate

Proceed to full paid runs only when all validation commands and pilot checks pass.
