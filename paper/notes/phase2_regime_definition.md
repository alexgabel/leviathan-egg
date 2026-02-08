# Phase 2 Regime Definition (Operational)

This file defines the canonical Phase 2 classifier contract.

Primary signal:
- `x(t) = frac_hier(t)` for post-burn-in window `T`

Binary state projection:
- `h(t) = 1[x(t) > tau]`

Computed features:
- `duty = (1/|T|) * sum_t h(t)`
- `switch_count = sum_t 1[h(t) != h(t-1)]`
- `switch_rate = switch_count / (|T|-1)`
- `dwell_hier_max = max contiguous run length where h(t)=1`
- `dwell_egal_max = max contiguous run length where h(t)=0`
- optional seasonal coherence and lag against a seasonal driver `s(t)`:
  - `coherence = max_{lag in [0, P)} |corr(x(t), s(t+lag))|`
  - `lag* = argmax_{lag in [0, P)} |corr(x(t), s(t+lag))|`
  - where `P = seasonal_period`

## Labels

- `egalitarian`
  - `duty <= duty_egal_max`
  - `switch_rate <= max_switch_rate_stable`
- `hierarchical`
  - `duty >= duty_hier_min`
  - `switch_rate <= max_switch_rate_stable`
- `reversal`
  - `duty_egal_max < duty < duty_hier_min`
  - `switch_rate >= min_switch_rate_reversal`
  - both states satisfy minimum dwell:
    - `dwell_hier_max >= L_min`
    - `dwell_egal_max >= L_min`
    - `L_min = ceil(min_dwell_fraction_of_period * seasonal_period)`
  - seasonal coherence gate (if enabled):
    - `coherence >= min_abs_seasonal_coherence`
- `uncertain`
  - anything borderline, contradictory, or failing required gates
  - includes runs with intermediate duty but insufficient switching/dwell/coherence

Decision rule ordering:
1. test `egalitarian`
2. test `hierarchical`
3. test `reversal`
4. else `uncertain`

## Threshold Governance

Threshold values are stored in:
- `experiments/configs/phase2/regime_thresholds.yaml`

Threshold keys:
- `tau`
- `duty_egal_max`
- `duty_hier_min`
- `max_switch_rate_stable`
- `min_switch_rate_reversal`
- `min_dwell_fraction_of_period`
- `min_abs_seasonal_coherence`
- `seasonal_coherence_required`

Rules:
- thresholds are frozen before bulk analysis
- one pilot run may be used to set thresholds
- threshold changes require a dated note and rationale

## Confidence (Optional)

Classifier may emit a confidence score in `[0, 1]` based on margin from threshold boundaries.
The score does not override label logic; it supports representative-case selection.
