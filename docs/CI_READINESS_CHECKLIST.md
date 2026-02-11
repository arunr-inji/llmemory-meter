# CI Readiness Checklist

This checklist converts local validation into repeatable CI gates.

## Required CI Jobs

- `lint-and-imports`: basic static checks and import sanity.
- `smoke-longmemeval`: run a small LongMemEval config/smoke path.
- `schema-check`: assert required JSON output keys exist.
- `security-input-validation`: assert invalid judge models fail.

## Candidate CI Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
.venv/bin/python -m llmemory_meter.cli run --config configs/longmemeval-only.yml
```

```bash
.venv/bin/python llmemory evaluate --benchmark LongMemEval --judge bad-model --results longmemeval_results.json --config configs/longmemeval-only.yml
```

## Checklist

- [ ] CI workflow file exists under `.github/workflows/` for benchmark validation.
- [ ] CI installs dependencies from `requirements.txt`.
- [ ] CI runs at least one benchmark smoke command.
- [ ] CI verifies results JSON schema presence (`config`, `results`, benchmark keys).
- [ ] CI checks invalid judge model is rejected.
- [ ] CI uploads logs/results as artifacts on failure and success.
- [ ] CI runtime budget and timeout policy are documented.
- [ ] CI secrets strategy is documented (which jobs require API keys and which do not).

## Security and Reliability Gates

- Block merge when subprocess input validation checks fail.
- Block merge when benchmark command exits non-zero.
- Block merge when schema check fails.
- Warn-only gate for external dependency/network flakiness, with retry metadata recorded.

## Publishability Gate in CI

- [ ] Release candidate tag must pass all required jobs.
- [ ] Artifact bundle contains logs + result JSON + commit SHA metadata.
- [ ] Hybrid evaluation command and judge model are recorded in artifact metadata.
