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

## Baseline Lock (Phase-3 Desync Closeout)

Canonical closeout inputs are locked to:
- run root: `experiments/runs/phase3/desync_refine_lag8_fine`
- threshold profile: `experiments/configs/phase3/desync_v2_thresholds.yaml`
- lock file: `experiments/runs/phase3/desync_refine_lag8_fine/baseline_lock.yaml`

Verification command:
- `python scripts/phase3_verify_baseline_lock.py`

Policy:
- no new exploratory sweeps while lock status is `LOCKED`
- only permit new runs if `scripts/phase3_closure_check.py` fails a closure gate

## Claim Language Lock (Must Match Notes)

Headline claim (v1, conservative):
- "Negative coupling yields persistent anti-phase/boundary regimes; robust desynchrony is not established under strict lag-gated criteria (classifier v1)."

Conditional v2 claim (allowed only when fully scoped):
- "Under classifier v2 (anti-phase-inclusive), robust desynchrony is supported only under the frozen threshold profile `experiments/configs/phase3/desync_v2_thresholds.yaml` and only within the reported anti-phase sensitivity window (`0.920` to `0.939` in `experiments/runs/phase3/desync_refine_lag8_fine/sensitivity_antiphase_threshold.csv`)."

Governance requirements:
- Any "robust desynchrony" wording must name classifier version (`v1` or `v2`).
- Any v2 robust wording must include both:
  - frozen profile path: `experiments/configs/phase3/desync_v2_thresholds.yaml`
  - stability-window artifact: `experiments/runs/phase3/desync_refine_lag8_fine/sensitivity_antiphase_threshold.csv`
- Use near-boundary framing unless overlap clearly decreases.

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
- `synchrony_antiphase_fraction`
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

## Near-Zero Desync Refinement (Lag Bottleneck Check)

If desync classification is blocked only by lag while order/lock indicate desync tendency:

1. Generate refinement manifest with doubled runtime:
- `python scripts/phase3_generate_desync_refine.py --manifest-out experiments/configs/phase3/manifest_desync_refine.csv --seed-base 9101`

2. Generate configs and run refinement:
- `python scripts/phase3_generate_configs.py --manifest experiments/configs/phase3/manifest_desync_refine.csv --stage confirmation`
- `python scripts/phase3_run_manifest.py --manifest experiments/configs/phase3/manifest_desync_refine.csv --stage confirmation --run-root experiments/runs/phase3/desync_refine --max-retries 1`
- conservative parallel alternative for laptops (2 shards):
- `python scripts/phase3_run_manifest_sharded.py --manifest experiments/configs/phase3/manifest_desync_refine.csv --stage confirmation --run-root experiments/runs/phase3/desync_refine --shards 2 --max-retries 1`

3. Prepare analysis with frozen thresholds + anti-phase output:
- `python scripts/phase3_prepare_analysis.py --run-root experiments/runs/phase3/desync_refine --manifest experiments/configs/phase3/manifest_desync_refine.csv --latest-output experiments/runs/phase3/desync_refine/analysis_latest_per_config.csv --block-output experiments/runs/phase3/desync_refine/analysis_full_grid_block.csv --label-mode fixed --sync-order-hi 0.93347525 --sync-lock-hi 0.84820575 --sync-lag-hi 21.8140085 --desync-order-lo 0.91162775 --desync-lock-lo 0.759961 --desync-lag-lo 28.20011175`

4. Build cell-level desync verdict table:
- `python scripts/phase3_desync_verdict.py --analysis-csv experiments/runs/phase3/desync_refine/analysis_latest_per_config.csv --threshold-profile experiments/configs/phase3/desync_v2_thresholds.yaml --cells-output experiments/runs/phase3/desync_refine/desync_cells.csv --robust-output experiments/runs/phase3/desync_refine/desync_robust_cells.csv`

5. Quantify anti-phase threshold sensitivity (artifact-only re-analysis):
- `python scripts/phase3_antiphase_sensitivity.py --analysis-csv experiments/runs/phase3/desync_refine_lag8_fine/analysis_latest_per_config.csv --threshold-profile experiments/configs/phase3/desync_v2_thresholds.yaml --antiphase-min 0.92 --antiphase-max 0.95 --antiphase-step 0.001 --output-csv experiments/runs/phase3/desync_refine_lag8_fine/sensitivity_antiphase_threshold.csv --fig-output experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_v2_antiphase_sensitivity.png`

6. Generate classifier-comparison figures (v1 vs v2):
- `python scripts/phase3_plot_classifier_comparison.py --cells-v1 experiments/runs/phase3/desync_refine_lag8_fine/desync_cells_v1.csv --cells-v2 experiments/runs/phase3/desync_refine_lag8_fine/desync_cells_v2.csv --fig-probability experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_desync_probability_v1_v2.png --fig-plane experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_lag_antiphase_plane_v1_v2.png`

7. One-command closeout (verdict tables + sensitivity + figures):
- `python scripts/phase3_closeout.py --run-root experiments/runs/phase3/desync_refine_lag8_fine --profile experiments/configs/phase3/desync_v2_thresholds.yaml`

## Invariants

- retain reproducibility contract (config, seed, commit, metrics)
- preserve backward compatibility for Phase 1/2 configs
- Phase 1/2 configs must remain runnable without schema-breaking changes
