# Phase 2 Strict Sanity Pass

Date: 2026-02-09
Run root: `experiments/runs/phase2/confirmation_refine_low_tau08`

Appendix status:
- Immutable evidence appendix for reviewers (claim-gating artifact).

## Goal

Stress-test the Stage-2 reversal claim against:
- threshold sensitivity across tau values
- less brittle hysteresis state extraction
- stricter boundary pass criteria

## Command

```bash
.venv/bin/python scripts/phase2_sanity_pass.py \
  --run-root experiments/runs/phase2/confirmation_refine_low_tau08 \
  --analysis-csv experiments/runs/phase2/confirmation_refine_low_tau08/analysis_latest_per_config_tau08.csv \
  --base-thresholds experiments/configs/phase2/regime_thresholds_tau08_sensitivity.yaml \
  --tau-grid 0.76,0.78,0.80,0.82,0.84 \
  --hysteresis-width 0.02 \
  --target-label reversal \
  --min-successes 4 \
  --min-replicates 5 \
  --min-cells-passing-boundary 3
```

## Produced Artifacts

- `sanity_threshold_ensemble_runs.csv`
- `sanity_threshold_ensemble_cells.csv`
- `sanity_threshold_stability_cells.csv`
- `sanity_threshold_boundary_settings.csv`
- `sanity_threshold_boundary_stability.csv`

## Cited Gating Artifacts (Required)

- `experiments/runs/phase2/confirmation_refine_low_tau08/sanity_threshold_ensemble_cells.csv`
- `experiments/runs/phase2/confirmation_refine_low_tau08/sanity_threshold_stability_cells.csv`
- `experiments/runs/phase2/confirmation_refine_low_tau08/sanity_threshold_boundary_stability.csv`

## Findings

### 1) Single-threshold tau ensemble is highly sensitive

- Cell-level `p_reversal` span across tau settings is maximal (`span=1.0`) for all 20 cells.
- No cell passes in *all* tau settings (`pass_all=0` for all cells).
- Boundary strict pass (`min_cells_passing_boundary=3`) is only `3/5` settings per boundary.

Interpretation:
- Reversal verdict is not tau-stable.

### 2) Hysteresis variant suppresses reversal under strict width

With `hysteresis_width=0.02`:
- `pass_target=0` for all 20 cells across all tau settings.
- boundary strict pass is `0/5` settings for each boundary.

With `hysteresis_width=0.01` (sensitivity check):
- only sparse reversal at tau `0.78` (4 passing cells total),
- still no boundary passes strict criterion in any setting.

Interpretation:
- The observed transition appears brittle to near-threshold relabeling choices.

### 3) Claim governance impact

- Stage 1 "appears" wording remains valid.
- Stage 2 global "robustly" wording is not supported by strict sanity criteria.
- Any robust statement should be explicitly scoped to the single-threshold tau profile
  and reported as threshold-dependent, pending additional evidence.
