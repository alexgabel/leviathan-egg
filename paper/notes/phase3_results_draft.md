# Phase 3 Results Draft (Working)

Date: 2026-02-15
Status: Draft for Phase-3 analysis/governance lock

## 1) Methods Delta from Earlier Phase-3 Runs

- Scope: multi-patch, staggered phases, ring topology, negative coupling (`sign=-1`).
- Refinement run root:
  - `experiments/runs/phase3/desync_refine_lag8_fine/`
- Final targeted sweep:
  - lag fixed at `8`
  - strengths `0.00` to `0.08` (step `0.01`)
  - `16` replicates per strength
  - doubled run length (`48000` steps, burn-in `4800`)
- Reproducibility status:
  - `144/144` successful runs
  - single run commit hash in run index

## 2) Classifier Versions

### 2.1 Classifier v1 (strict lag-gated)

Definition summary:
- desynchrony requires all three:
  - low order
  - low lock
  - high lag (strict lag gate)

Evidence:
- run-level labels:
  - `experiments/runs/phase3/desync_refine_lag8_fine/analysis_latest_per_config.csv`
- cell table:
  - `experiments/runs/phase3/desync_refine_lag8_fine/desync_cells_v1.csv`
- robust-cell table:
  - `experiments/runs/phase3/desync_refine_lag8_fine/desync_robust_cells_v1.csv`

Observed:
- run labels: `desynchrony=40`, `boundary=104`
- robust cells (`>=0.8` desync fraction, n>=16): `0/9`

### 2.2 Classifier v2 (anti-phase-inclusive)

Definition summary:
- desynchrony requires low order + low lock, and then:
  - high lag OR high anti-phase fraction

Threshold profile:
- `experiments/configs/phase3/desync_v2_thresholds.yaml`

Anti-phase threshold sensitivity artifacts:
- `experiments/runs/phase3/desync_refine_lag8_fine/sensitivity_antiphase_threshold.csv`
- `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_v2_antiphase_sensitivity.png`
- reported robust-v2 stability window (current gate: `min_robust_cells=1`): `0.920` to `0.939`

Evidence:
- run-level labels:
  - `experiments/runs/phase3/desync_refine_lag8_fine/analysis_latest_per_config_v2.csv`
- cell table:
  - `experiments/runs/phase3/desync_refine_lag8_fine/desync_cells_v2.csv`
- robust-cell table:
  - `experiments/runs/phase3/desync_refine_lag8_fine/desync_robust_cells_v2.csv`

Observed:
- run labels: `desynchrony=123`, `boundary=21`
- robust cells (`>=0.8` desync fraction, n>=16): `7/9`

## 3) Evidence Tables (Side-by-Side Summary)

| Classifier | Robust cells passed | Robustness gate |
| --- | --- | --- |
| v1 strict lag-gated | 0 / 9 | `p_desynchrony >= 0.8`, `n >= 16` |
| v2 anti-phase-inclusive | 7 / 9 | `p_desynchrony >= 0.8`, `n >= 16`, anti-phase gate retained |

Interpretation:
- v1 remains conservative and mostly labels boundary states.
- v2 captures persistent anti-phase regimes that v1 treats as near-threshold.
- both results are retained and reported; v2 is not substituted silently for v1.

## 4) Phase-3 Claim Language Lock (Version-Explicit)

Primary headline claim (v1, conservative):
"Negative coupling yields persistent anti-phase/boundary regimes; robust desynchrony is not established under strict lag-gated criteria (classifier v1)."

Conditional v2 claim (version/profile/window-scoped only):
"Under classifier v2 (anti-phase-inclusive), robust desynchrony is supported only under the frozen threshold profile `experiments/configs/phase3/desync_v2_thresholds.yaml` and only within the reported anti-phase sensitivity window (`0.920` to `0.939` in `sensitivity_antiphase_threshold.csv`)."

Governance rule:
- Any use of "robust desynchrony" must include classifier version (`v1` or `v2`).
- Any v2 "robust" wording must include both:
  - profile path: `experiments/configs/phase3/desync_v2_thresholds.yaml`
  - stability window source: `experiments/runs/phase3/desync_refine_lag8_fine/sensitivity_antiphase_threshold.csv`
- Headline/default framing remains v1-conservative unless explicitly discussing v2 profile-scoped sensitivity results.
- No retroactive edits to Phase-2 claims.

## 5) Figures (Phase 3)

- Probability comparison:
  - `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_desync_probability_v1_v2.png`
- Lag/anti-phase plane:
  - `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_lag_antiphase_plane_v1_v2.png`
- Desynchrony core trace (v2-selected max-separation):
  - `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_trace_desync_core_v2.png`
- Boundary-nearest trace (v2-selected near crossing):
  - `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_trace_boundary_near_v2.png`
- Label distributions (lag/anti-phase) to expose overlap:
  - `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_label_distributions_v1_v2.png`
- v2 anti-phase sensitivity curve/table:
  - `experiments/runs/phase3/desync_refine_lag8_fine/fig_phase3_v2_antiphase_sensitivity.png`
  - `experiments/runs/phase3/desync_refine_lag8_fine/sensitivity_antiphase_threshold.csv`
- Representative selection table:
  - `experiments/runs/phase3/desync_refine_lag8_fine/representative_selection_v2.csv`
- Figure captions:
  - `paper/notes/phase3_figure_captions.md`

Figure intent:
- first figure shows desync probability shift from v1 to v2 across strength.
- second figure shows why lag-only gating is restrictive despite strong anti-phase signal.
- core/boundary trace pair provides objective exemplars for the near-boundary regime.
- distribution figure makes class overlap explicit and prevents overstating class separation.
- sensitivity figure/table defines the v2 stability window (`0.920` to `0.939`) and documents threshold-profile-scoped caveats.
