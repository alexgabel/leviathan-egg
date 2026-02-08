# Phase 2 Data Dictionary

## 1) Run Artifact Columns

Source: `experiments/runs/phase2/run_index.csv`

- `run_id`: unique run directory identifier.
- `config_path`: config file path used for run.
- `seed`: random seed used by simulation.
- `status`: `SUCCESS` or `FAILED`.
- `retry_count`: number of retries used after initial attempt.
- `start_time`: run start timestamp (UTC).
- `end_time`: run end timestamp (UTC).
- `git_commit`: commit hash captured at run time.
- `schema_version`: resolved config schema version.
- `run_dir`: output directory for this run.
- `error`: flattened traceback when status is `FAILED`.

## 2) Metrics Columns

Source: `metrics.csv` per run

- `t`: simulation time step after burn-in filtering.
- `frac_hier`: fraction of agents in `authority_on` groups.
- `num_groups`: number of extant groups.
- `mean_group_size`: mean size across groups.
- `max_group_size`: largest observed group size at step `t`.
- `gini_prestige`: inequality of prestige distribution.
- `festival`: seasonal festival driver value (if logged).
- `crisis`: seasonal crisis driver value (if logged).

## 3) Regime Classifier Inputs

- primary signal: `frac_hier(t)`
- binary projection: `h(t) = 1[frac_hier(t) > tau]`
- optional seasonal driver for coherence: `crisis(t)` preferred, `festival(t)` fallback
- seasonal period: `seasonality.seasonal_period` from resolved config

## 4) Regime Classifier Outputs

Source: `experiments/runs/phase2/regime_labels.csv`

- `label`: one of `egalitarian`, `hierarchical`, `reversal`, `uncertain`.
- `confidence`: heuristic confidence in `[0, 1]`.
- `duty`: mean occupancy of `h(t)=1`.
- `switch_count`: number of state transitions in `h(t)`.
- `switch_rate`: `switch_count / (|T|-1)`.
- `max_dwell_hier`: max contiguous run where `h(t)=1`.
- `max_dwell_egal`: max contiguous run where `h(t)=0`.
- `seasonal_coherence`: max absolute lagged correlation vs seasonal driver.
- `seasonal_lag`: lag at which max coherence occurs.
- `thresholds_path`: threshold file used for labeling.
- `labeled_at`: labeling timestamp (UTC).

## 5) Interpretation Notes

- `uncertain` is an explicit outcome for borderline/contradictory runs.
- Stage 1 conclusions should use appearance language, not robustness language.
- Robustness claims require Stage 2 replicated cells and explicit criteria.
