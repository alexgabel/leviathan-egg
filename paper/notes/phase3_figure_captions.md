# Phase 3 Figure Captions (Classifier-Versioned)

## Figure P3.1 — Desynchrony Probability by Strength (v1 vs v2)
File:
- `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_desync_probability_v1_v2.png`

Caption:
Desynchrony probability across lag-8 near-zero coupling strengths (`0.00` to `0.08`) under two classifier definitions. Classifier v1 (strict lag-gated) remains mostly boundary and does not pass the predeclared robustness gate (`p_desynchrony >= 0.8`, `n >= 16`). Classifier v2 (anti-phase-inclusive) crosses that gate in this run set, but this is interpreted only under the frozen profile `experiments/configs/phase3/desync_v2_thresholds.yaml` and the reported anti-phase sensitivity window (`0.920` to `0.939` in `sensitivity_antiphase_threshold.csv`).

## Figure P3.2 — Lag vs Anti-Phase Plane (v1 vs v2)
File:
- `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_lag_antiphase_plane_v1_v2.png`

Caption:
Cell-level means in lag/anti-phase space for the same lag-8 refinement grid. Marker size encodes desynchrony probability; color encodes strength. The vertical dashed line marks the strict lag cutoff and the horizontal dotted line marks the anti-phase cutoff. Points cluster near the lag threshold while anti-phase is consistently high, explaining why v1 is conservative and why v2 classifies many cells as desynchrony.

## Figure P3.3 — Desynchrony Core Trace (v2-selected)
File:
- `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_trace_desync_core_v2.png`

Caption:
Objective desynchrony core run selected by maximal v2 confidence (`representative_selection_v2.csv`, `selection_note=highest_v2_confidence_max_separation`). Top panel shows per-patch hierarchy trajectories; bottom panel shows synchrony metrics and thresholds. The run remains in low-order/low-lock, high anti-phase regime with lag near the lag threshold.

## Figure P3.4 — Boundary-Nearest Trace (v2-selected)
File:
- `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_trace_boundary_near_v2.png`

Caption:
Objective boundary run selected by minimal distance to v2 desynchrony crossing (`selection_note=closest_boundary_to_v2_desync_crossing`). The trajectory sits close to threshold surfaces and supports the near-boundary-regime interpretation.

## Figure P3.5 — Label Distributions in Lag/Anti-Phase Space (v1 vs v2)
File:
- `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_label_distributions_v1_v2.png`

Caption:
Lag/anti-phase scatter by label for v1 and v2 on the same runs. This panel is included to make overlap explicit rather than implied; class separation is partial and the operating regime remains near threshold boundaries.

## Figure P3.6 — v2 Anti-Phase Threshold Sensitivity (Window + Caveat)
File:
- `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_v2_antiphase_sensitivity.png`

Supporting table:
- `experiments/runs/phase3/desync_refine_lag8_fine/sensitivity_antiphase_threshold.csv`

Caption:
Artifact-only re-analysis of the frozen run set under classifier v2. Robust-v2 wording is supported only within the reported stability window (`0.920` to `0.939`, gate `min_robust_cells=1`) and only under the frozen profile `experiments/configs/phase3/desync_v2_thresholds.yaml`. Outside this window, robust-v2 conclusions are not supported.

## Governance Note

- Headline conservative statement (v1): robust desynchrony is not established under strict lag-gated criteria.
- Version-scoped conditional (v2): robust desynchrony may be stated only under:
  - frozen profile `experiments/configs/phase3/desync_v2_thresholds.yaml`
  - reported stability window `0.920` to `0.939` from `experiments/runs/phase3/desync_refine_lag8_fine/sensitivity_antiphase_threshold.csv`
- Any use of "robust desynchrony" must explicitly name classifier version.
- Narrative guardrail: describe Phase 3 as a near-boundary regime unless distribution overlap materially decreases.
