# Phase 2 Threshold Changelog

This changelog tracks changes to `experiments/configs/phase2/regime_thresholds.yaml`.

## 2026-02-08

Version context:
- Phase 2 setup (M0)
- Thresholds frozen before bulk Stage 1 analysis

Threshold values:
- `tau: 0.5`
- `duty_egal_max: 0.2`
- `duty_hier_min: 0.8`
- `max_switch_rate_stable: 0.02`
- `min_switch_rate_reversal: 0.02`
- `min_dwell_fraction_of_period: 0.10`
- `min_abs_seasonal_coherence: 0.20`
- `seasonal_coherence_required: true`

Rationale summary:
- Distinguish stable occupancy (`duty`) from switching behavior.
- Require minimum dwell in both states for reversal classification.
- Gate reversals by seasonal coherence to reduce false positives from noise.

Change policy:
- No threshold edits during bulk Stage 1 runs.
- Any future change requires:
  - date-stamped entry in this file,
  - rationale and expected impact,
  - note of whether past labels were recomputed.

## 2026-02-08 (Path A Sensitivity Calibration)

Version context:
- Stage 1 recentered sweep (`recenter_full`) completed with uniform `hierarchical` labels
  under canonical thresholds.
- Path A initiated to probe boundary discovery without overwriting canonical thresholds.

Threshold profile used:
- `experiments/configs/phase2/regime_thresholds_tau08_sensitivity.yaml`
- identical to canonical profile except:
  - `tau: 0.8` (from 0.5)

Recomputed labels:
- `experiments/runs/phase2/recenter_full/regime_labels_tau08_sensitivity.csv`
- outcome counts on 24 runs:
  - `reversal: 6`
  - `hierarchical: 2`
  - `uncertain: 16`

Operational decision:
- Canonical frozen thresholds remain unchanged in `regime_thresholds.yaml`.
- Tau=0.8 profile is a calibration profile for confirmation-cell selection.
