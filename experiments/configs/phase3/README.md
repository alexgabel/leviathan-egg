# Phase 3 Configs — Multi-Patch Desynchronization Contract

Status: Active (M3 coupling v1 + synchrony metrics)

Authoritative kickoff note:
- `paper/notes/phase3_kickoff.md`

## Scope Lock

Phase 3 introduces model elements that were out-of-scope for Phase 2:
- multi-patch execution
- explicit inter-patch coupling
- synchrony/desynchrony metrics

No retroactive Phase-2 claim edits are allowed during Phase 3 implementation.
Preflight check before Phase 3 changes:
- `python scripts/phase2_verify_frozen_artifacts.py`

## First Implementation Slice (Acceptance-Tests First)

Implementation status:
1. config schema and validation invariants
2. multi-patch world container/plumbing with single-patch regression preserved
3. weak signed coupling v1 + per-patch/synchrony output schema
4. runner compatibility with existing reproducibility/run-index contracts

Acceptance tests to implement first:
- `test_phase3_single_patch_regression`
- `test_phase3_uncoupled_independence`
- `test_phase3_positive_coupling_directional_effect`
- `test_phase3_negative_or_weak_coupling_allows_desync`
- `test_phase3_reproducible_per_patch_outputs`
- `test_phase3_output_schema_contract`

M2 gate command (must be green before exploratory Phase 3 runs):
- `PYTHONPATH=src python -m pytest -q tests/test_phase3_acceptance.py`

## Required Phase 3 Config Additions

- coupling parameter block (strength, sign, mode, topology)
- explicit patch-level seasonal phase offsets
- declared synchrony hypothesis per config

## Output Contract (Phase 3)

Multi-patch runs (`num_patches > 1`) emit synchrony outputs in `metrics.csv`:
- `synchrony_order_parameter`
- `synchrony_phase_lock_fraction`
- `synchrony_mean_abs_phase_lag`
- `frac_hier_patch_<patch_id>` per patch

## Stage-1 Exploration Manifest

- `experiments/configs/phase3/manifest_stage1_exploration.csv`
- 24-row factorial (`phase_profile` x `topology` x `coupling_sign` x `coupling_strength`)
- One seed per row (5101-5124), `stage=exploration`

## Execution Workflow

1. Generate/refresh YAMLs from manifest:
- `python scripts/phase3_generate_configs.py --manifest experiments/configs/phase3/manifest_stage1_exploration.csv --stage exploration`

2. Run Stage-1 exploration:
- `python scripts/phase3_run_manifest.py --manifest experiments/configs/phase3/manifest_stage1_exploration.csv --stage exploration --run-root experiments/runs/phase3/exploration_stage1 --max-retries 1`

3. Build Stage-1 analysis table (artifact-derived thresholds):
- `python scripts/phase3_prepare_analysis.py --run-root experiments/runs/phase3/exploration_stage1 --manifest experiments/configs/phase3/manifest_stage1_exploration.csv --latest-output experiments/runs/phase3/exploration_stage1/analysis_latest_per_config.csv --block-output experiments/runs/phase3/exploration_stage1/analysis_full_grid_block.csv --label-mode quantile --quantile-lo 0.25 --quantile-hi 0.75 --thresholds-output experiments/runs/phase3/exploration_stage1/analysis_thresholds_quantile.csv`

4. Generate Stage-2 boundary confirmation manifest:
- `python scripts/phase3_generate_confirmation.py --analysis-csv experiments/runs/phase3/exploration_stage1/analysis_latest_per_config.csv --manifest-out experiments/configs/phase3/manifest_confirmation.csv --boundary-out experiments/configs/phase3/boundary_cells_auto.csv --replicates 5 --seed-base 6101`
- If `boundaries=0`, rerun step 3 with `--label-mode quantile` (or wider `--quantile-lo/--quantile-hi`) and regenerate.

5. Generate Stage-2 YAMLs + run confirmation:
- `python scripts/phase3_generate_configs.py --manifest experiments/configs/phase3/manifest_confirmation.csv --stage confirmation`
- `python scripts/phase3_run_manifest.py --manifest experiments/configs/phase3/manifest_confirmation.csv --stage confirmation --run-root experiments/runs/phase3/confirmation_stage2 --max-retries 1`

## Invariants

- retain reproducibility contract (config, seed, commit, metrics)
- preserve backward compatibility for Phase 1/2 configs
- Phase 1/2 configs must remain runnable without schema-breaking changes
