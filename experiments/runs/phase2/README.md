# Phase 2 Run Directory Contract

Each run directory must include:
- `metrics.csv`
- `config_resolved.yaml`
- `seed.txt`
- `git_commit.txt`

Failure contract:
- failed runs must contain `FAILED.txt`
- failed runs must still be recorded in `run_index.csv`

Run index file:
- `run_index.csv` in this directory is the canonical run ledger for Phase 2.
