# Phase 2 Results Draft (Working)

Date: 2026-02-09
Status: Draft for Workstreams 2.E and 2.F

## 1) Methods Delta from Phase 1

- Dynamics scope stayed fixed to single-patch Phase-1-equivalent behavior.
- Regime classification used frozen threshold profiles and explicit `uncertain` output.
- Analysis remained staged:
  - Stage 1 exploration for candidate-region discovery
  - Stage 2 confirmation/refinement for replicated boundary evidence

## 2) Regime Structure Findings

### 2.1 Stage 1 (Exploration)

- Canonical profile (`regime_thresholds.yaml`, `tau=0.5`) on recentered 24-cell grid:
  - labels: `hierarchical=24`, no reversal detection
  - artifact: `experiments/runs/phase2/recenter_full/analysis_latest_per_config.csv`
- Sensitivity profile (`regime_thresholds_tau08_sensitivity.yaml`, `tau=0.8`) on same runs:
  - labels: `reversal=6`, `hierarchical=2`, `uncertain=16`
  - artifact: `experiments/runs/phase2/recenter_full/analysis_latest_per_config_tau08_sensitivity.csv`

Interpretation:
- A bounded candidate reversal region appears under the tau=0.8 profile, motivating
  Stage 2 boundary confirmation.

### 2.2 Stage 2 (Confirmation + Dense Refinement, tau=0.8 profile)

- Near-boundary dense runs and low-alpha refinement were replicated at 5 seeds/cell.
- Refinement results (`confirmation_refine_low_tau08`):
  - 100 runs total
  - labels: `reversal=60`, `uncertain=40`
  - artifact: `experiments/runs/phase2/confirmation_refine_low_tau08/analysis_latest_per_config_tau08.csv`
- Robustness verdicts (`min_successes=4`, `min_replicates=5`):
  - passing cells: `12 / 20`
  - passing boundaries: `4 / 4`
  - artifacts:
    - `experiments/runs/phase2/confirmation_refine_low_tau08/robustness_cells_tau08.csv`
    - `experiments/runs/phase2/confirmation_refine_low_tau08/robustness_boundaries_tau08.csv`
- Stage 2 figure-input tables:
  - probability map: `experiments/runs/phase2/confirmation_refine_low_tau08/stage2_probability_map_tau08.csv`
  - uncertainty overlay: `experiments/runs/phase2/confirmation_refine_low_tau08/stage2_uncertainty_overlay_tau08.csv`

Observed transition pattern:
- For each boundary (`b01`-`b04`), reversal probability is 1.0 at alpha
  `0.35-0.40`, then shifts to `uncertain` at alpha `0.42-0.44`.

## 3) Claim Governance Verdict

### Primary Claim (Phase-2 Headline)

"Seasonal reversals appear in a bounded region of parameter space."

### Stage-2 "Robustly" Upgrade Status (Not Passed)

The strict sanity pass (tau ensemble + hysteresis variant + strict boundary
gating) does not support classifier-invariant robust language at this time.

Governance note:
- Any "robustly" wording remains conditional and non-headline until stricter
  invariance criteria are satisfied.
- Do not generalize threshold-profile-specific behavior to the canonical
  tau=0.5 profile without matching replicated evidence.
- Formal gating evidence is maintained in the immutable appendix:
  `paper/notes/phase2_sanity_pass.md`.

### Conditional/Rejected Wording Record

Conditional wording (not approved as current headline claim):
"Under the tau=0.8 threshold profile, seasonal reversals emerge robustly in a
bounded local neighborhood of parameter space around the identified transition
boundaries."

## 4) Limitations and Deferred Work

- No multi-patch desynchronization claims in Phase 2.
- No network-geometry/hyperbolicity claims in Phase 2.
- No geography/topology expansion in Phase 2.
- Threshold-profile dependence must be stated explicitly in text and captions.

## 5) Frozen Artifact Manifest

- Publication artifact hashes are frozen at:
  `paper/notes/phase2_frozen_artifacts.sha256`.
