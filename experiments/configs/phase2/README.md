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

Run index contract:
- `experiments/runs/phase2/run_index.csv` includes explicit artifact paths:
  `metrics_path`, `config_resolved_path`, `seed_path`, `git_commit_path`,
  `failed_marker_path`, and aggregate `artifact_paths`.
- backfill legacy run-index files after runner upgrades:
  - `.venv/bin/python scripts/phase2_backfill_run_index.py --run-root experiments/runs/phase2`

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

Objective representative selection + required time-series plots (`frac_hier`, `festival`, `crisis`):
- `.venv/bin/python scripts/phase2_select_representative_plots.py --run-root experiments/runs/phase2 --labels experiments/runs/phase2/regime_labels.csv --analysis-csv experiments/runs/phase2/analysis_latest_per_config.csv --method highest_confidence --output-csv experiments/runs/phase2/representative_cases.csv --plot-dir experiments/runs/phase2/representative_plots --tau 0.5`

## Path A (Tau=0.8 Calibration)

Calibrate labels for boundary discovery (without changing canonical thresholds):
- `.venv/bin/python scripts/phase2_label_runs.py --run-root experiments/runs/phase2/recenter_full --thresholds experiments/configs/phase2/regime_thresholds_tau08_sensitivity.yaml --output experiments/runs/phase2/recenter_full/regime_labels_tau08_sensitivity.csv`
- `.venv/bin/python scripts/phase2_prepare_analysis.py --run-root experiments/runs/phase2/recenter_full --labels experiments/runs/phase2/recenter_full/regime_labels_tau08_sensitivity.csv --manifest experiments/configs/phase2/manifest_exploration.csv --latest-output experiments/runs/phase2/recenter_full/analysis_latest_per_config_tau08_sensitivity.csv --block-output experiments/runs/phase2/recenter_full/analysis_full_grid_block_tau08_sensitivity.csv`

Generate confirmation cells/configs from tau=0.8 boundary selection:
- `.venv/bin/python scripts/phase2_generate_confirmation_tau08.py --analysis-csv experiments/runs/phase2/recenter_full/analysis_latest_per_config_tau08_sensitivity.csv --boundary-csv-out experiments/configs/phase2/boundary_cells_auto_tau08.csv`
- this programmatically derives boundary pairs from Stage-1 analysis labels,
  then populates `manifest_confirmation.csv` and writes `phase2c_tau08_*.yaml` configs

Run confirmation batch:
- `.venv/bin/python scripts/phase2_run_manifest.py --manifest experiments/configs/phase2/manifest_confirmation.csv --stage confirmation --run-root experiments/runs/phase2/confirmation_tau08 --max-retries 1`

## Near-Crossing Refinement (Final Robustness)

Generate refinement configs/manifest near the measured transition with 5 seeds per cell:
- `.venv/bin/python scripts/phase2_generate_confirmation_refine.py --boundary-csv experiments/configs/phase2/boundary_cells_auto_tau08.csv --transition-summary experiments/runs/phase2/confirmation_dense_tau08/transition_summary_tau08.csv --alphas 0.45,0.50,0.55 --replicates 5 --manifest-out experiments/configs/phase2/manifest_confirmation_refine.csv --config-prefix phase2r_tau08 --seed-base 6101 --threshold-profile-note regime_thresholds_tau08_sensitivity.yaml`

Run the refinement manifest:
- `.venv/bin/python scripts/phase2_run_manifest.py --manifest experiments/configs/phase2/manifest_confirmation_refine.csv --stage confirmation --run-root experiments/runs/phase2/confirmation_refine_tau08 --max-retries 1`

Label + prepare analysis tables:
- `.venv/bin/python scripts/phase2_label_runs.py --run-root experiments/runs/phase2/confirmation_refine_tau08 --thresholds experiments/configs/phase2/regime_thresholds_tau08_sensitivity.yaml --output experiments/runs/phase2/confirmation_refine_tau08/regime_labels_tau08.csv`
- `.venv/bin/python scripts/phase2_prepare_analysis.py --run-root experiments/runs/phase2/confirmation_refine_tau08 --labels experiments/runs/phase2/confirmation_refine_tau08/regime_labels_tau08.csv --manifest experiments/configs/phase2/manifest_confirmation_refine.csv --latest-output experiments/runs/phase2/confirmation_refine_tau08/analysis_latest_per_config_tau08.csv --block-output experiments/runs/phase2/confirmation_refine_tau08/analysis_full_block_tau08.csv`

Robustness verdict tables (claim governance for Stage 2):
- `.venv/bin/python scripts/phase2_robustness_verdict.py --analysis-csv experiments/runs/phase2/confirmation_refine_tau08/analysis_latest_per_config_tau08.csv --target-label reversal --min-successes 4 --min-replicates 5 --cells-output experiments/runs/phase2/confirmation_refine_tau08/robustness_cells_tau08.csv --boundaries-output experiments/runs/phase2/confirmation_refine_tau08/robustness_boundaries_tau08.csv`

Generate Stage 2 figure-input tables (probability + uncertainty overlays):
- `.venv/bin/python scripts/phase2_stage2_figure_inputs.py --cells-csv experiments/runs/phase2/confirmation_refine_tau08/robustness_cells_tau08.csv --boundaries-csv experiments/runs/phase2/confirmation_refine_tau08/robustness_boundaries_tau08.csv --probability-output experiments/runs/phase2/confirmation_refine_tau08/stage2_probability_map_tau08.csv --uncertainty-output experiments/runs/phase2/confirmation_refine_tau08/stage2_uncertainty_overlay_tau08.csv`

Render final Stage 2 map figures (2.E):
- `.venv/bin/python scripts/phase2_plot_stage2_maps.py --probability-csv experiments/runs/phase2/confirmation_refine_tau08/stage2_probability_map_tau08.csv --uncertainty-csv experiments/runs/phase2/confirmation_refine_tau08/stage2_uncertainty_overlay_tau08.csv --heatmap-out experiments/runs/phase2/confirmation_refine_tau08/fig_stage2_probability_heatmap_tau08.png --overlay-out experiments/runs/phase2/confirmation_refine_tau08/fig_stage2_entropy_discord_overlay_tau08.png`

## Strict Sanity Pass (Before "Robustly" Language)

Run threshold-ensemble + hysteresis stress test (with strict boundary gating):
- `.venv/bin/python scripts/phase2_sanity_pass.py --run-root experiments/runs/phase2/confirmation_refine_low_tau08 --analysis-csv experiments/runs/phase2/confirmation_refine_low_tau08/analysis_latest_per_config_tau08.csv --base-thresholds experiments/configs/phase2/regime_thresholds_tau08_sensitivity.yaml --tau-grid 0.76,0.78,0.80,0.82,0.84 --hysteresis-width 0.02 --target-label reversal --min-successes 4 --min-replicates 5 --min-cells-passing-boundary 3`

Key sanity outputs:
- `sanity_threshold_ensemble_runs.csv`
- `sanity_threshold_ensemble_cells.csv`
- `sanity_threshold_stability_cells.csv`
- `sanity_threshold_boundary_settings.csv`
- `sanity_threshold_boundary_stability.csv`

Interpretation rule:
- If reversal only appears under narrow single-threshold settings but collapses under
  hysteresis or strict boundary criteria, do not use global "robustly" wording.
