# Phase 2 Configs — Regime Mapping Contract

Phase 2 runs are single-patch sweeps on top of the frozen Phase-1 engine.

## Scope Lock (Do Not Drift)

Allowed changes per config:
- seasonality amplitude / bias
- violence / exit friction knobs
- information / memory knobs
- charisma / festival knobs

Not allowed in Phase 2:
- modifying world update logic
- introducing multi-patch coupling dynamics
- adding new social mechanisms or agent cognition

Note:
- `world_structure.num_patches` and extra patch phase offsets may appear in schema,
  but only `patch_0` behavior is in-scope for Phase 2 execution.

## Required Config Fields

Each Phase 2 config must include:
- `schema_version`
- `experiment_name`
- `description`
- `author`
- `date_created`
- all required sections from `experiments/configs/README.md`

Each config must also document:
- sweep axis and value
- hypothesis (expected qualitative regime)
- unique random seed

## Staged Sweep Design

Phase 2 uses two stages.

1. Stage 1 (exploration)
- broad mapping sweep
- target size: 12-24 configs
- one seed per config
- manifest: `manifest_exploration.csv`
- implemented matrix: 24-cell recentered factorial
  - seasonal profile (amplitude + sign/bias): `anti_strong`, `baseline`, `pro_strong`
  - violence profile: `low`, `high`
  - information/memory lock-in profile: `low`, `high`
  - festival mode: `off`, `on`

2. Stage 2 (confirmation)
- only candidate transition regions from Stage 1
- denser local parameter slices
- 3-5 seeds per config cell
- manifest: `manifest_confirmation.csv`

## Classification Contract

- Canonical regime definition: `paper/notes/phase2_regime_definition.md`
- Canonical thresholds: `regime_thresholds.yaml`
- Thresholds must be frozen before bulk plotting.
- One pilot run may be used to set thresholds, and must be documented.

## Claim Governance

- Stage 1 wording: "reversals appear in a bounded region."
- "Robustly" is reserved for Stage 2 after explicit seed-based criteria are met.

## Reproducibility and Run Artifacts

Results are invalid without:
- `metrics.csv`
- `config_resolved.yaml`
- `seed.txt`
- `git_commit.txt`

Failure policy:
- failed runs must emit `FAILED.txt`
- failures must remain indexed in run tracking
- no silent overwrites of prior runs

Recommended invocation for Phase 2 runs:
- `leviathan-egg run --config <path> --run-root experiments/runs/phase2`

## Reproducible Workflow Scripts

Generate factorial configs + manifests:
- `.venv/bin/python scripts/phase2_generate_configs.py`

Run configs from manifest:
- `.venv/bin/python scripts/phase2_run_manifest.py --manifest experiments/configs/phase2/manifest_exploration.csv --run-root experiments/runs/phase2`

Smoke subset example (first 3 cells):
- `.venv/bin/python scripts/phase2_run_manifest.py --manifest experiments/configs/phase2/manifest_exploration.csv --run-root experiments/runs/phase2 --limit 3`
- fast smoke subset (shortened runtime override):
  - `.venv/bin/python scripts/phase2_run_manifest.py --manifest experiments/configs/phase2/manifest_exploration.csv --run-root experiments/runs/phase2/smoke --limit 3 --override-total-steps 1200 --override-burn-in 120`

Label successful runs:
- `.venv/bin/python scripts/phase2_label_runs.py --run-root experiments/runs/phase2 --thresholds experiments/configs/phase2/regime_thresholds.yaml --output experiments/runs/phase2/regime_labels.csv`

Prepare bias-safe analysis tables before plotting:
- `.venv/bin/python scripts/phase2_prepare_analysis.py --run-root experiments/runs/phase2 --manifest experiments/configs/phase2/manifest_exploration.csv`
- outputs:
  - `experiments/runs/phase2/analysis_latest_per_config.csv`
  - `experiments/runs/phase2/analysis_full_grid_block.csv`

## Path A (Tau=0.8 Calibration)

Calibrate labels for boundary discovery (without changing canonical thresholds):
- `.venv/bin/python scripts/phase2_label_runs.py --run-root experiments/runs/phase2/recenter_full --thresholds experiments/configs/phase2/regime_thresholds_tau08_sensitivity.yaml --output experiments/runs/phase2/recenter_full/regime_labels_tau08_sensitivity.csv`
- `.venv/bin/python scripts/phase2_prepare_analysis.py --run-root experiments/runs/phase2/recenter_full --labels experiments/runs/phase2/recenter_full/regime_labels_tau08_sensitivity.csv --manifest experiments/configs/phase2/manifest_exploration.csv --latest-output experiments/runs/phase2/recenter_full/analysis_latest_per_config_tau08_sensitivity.csv --block-output experiments/runs/phase2/recenter_full/analysis_full_grid_block_tau08_sensitivity.csv`

Generate confirmation cells/configs from tau=0.8 boundary selection:
- `.venv/bin/python scripts/phase2_generate_confirmation_tau08.py`
- this populates `manifest_confirmation.csv` and writes `phase2c_tau08_*.yaml` configs

Run confirmation batch:
- `.venv/bin/python scripts/phase2_run_manifest.py --manifest experiments/configs/phase2/manifest_confirmation.csv --stage confirmation --run-root experiments/runs/phase2/confirmation_tau08 --max-retries 1`
