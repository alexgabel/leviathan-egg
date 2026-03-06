# Phase 4 Design Spec — Structural Signatures

Key question:
Do high-hierarchy phases exhibit consistent graph-structural signatures relative
to low-hierarchy phases?

## Scope Lock

Phase 4 adds structural observation only:
- interaction graph extraction from already-simulated behavior
- graph metric computation by window
- association tests against hierarchy intensity

Phase 4 must not:
- change Phase-3 claims, profiles, or classifier outcomes
- introduce new agent cognition or social mechanisms
- silently alter Phase-1/2/3 dynamics on non-Phase-4 code paths

## Exact Graph Extraction Windowing

Primary extraction rule:

- Let `P` be `seasonality.seasonal_period` from the resolved config.
- Let `B` be `runtime_and_reproducibility.burn_in_period`.
- Let `T` be `runtime_and_reproducibility.total_steps`.
- Let `W = window_periods * P`, where `window_periods` is a Phase-4 config knob.
- Use only complete post-burn-in windows.

Window construction:

1. Define the first eligible window end as `t_end = B + W`.
2. Construct non-overlapping right-closed windows:
   - `window_000`: `[B + 1, B + W]`
   - `window_001`: `[B + W + 1, B + 2W]`
   - continue while `t_end <= T`
3. Drop any partial trailing window.
4. For single-patch runs, emit one graph per window.
5. For multi-patch runs, emit one graph per `(window_id, patch_id)` pair and one
   optional pooled graph only if explicitly enabled.

Graph extraction modes (frozen names):

- `undirected_contact`
  - edge `(i, j)` exists if agents `i` and `j` co-occur in at least one logged
    interaction event during the window
  - edge weight is the count of such events
- `directed_influence`
  - edge `i -> j` exists if `i` is logged as initiating, recruiting, coercing,
    or otherwise directing an interaction toward `j` during the window
  - edge weight is the count of directed events

If a required event stream is absent, the run must fail explicitly rather than
emit an underspecified graph artifact.

## Required Output Artifacts

Phase-4 runs must preserve the standard run contract and additionally emit:

1. `graph_windows.csv`
- one row per extracted graph window

2. `graph_edges.csv`
- auditable edge list for each extracted graph

3. `graph_schema_version.txt`
- frozen graph-output schema identifier

## Output Schema Columns

### `graph_windows.csv`

Required columns:

- `run_id`
- `config_path`
- `seed`
- `git_commit`
- `schema_version`
- `graph_schema_version`
- `window_id`
- `patch_id`
- `graph_mode`
- `window_periods`
- `t_start`
- `t_end`
- `n_steps`
- `n_nodes`
- `n_edges`
- `is_directed`
- `edge_weight_sum`
- `density`
- `mean_degree`
- `degree_std`
- `degree_gini`
- `largest_component_fraction`
- `clustering_mean`
- `mean_shortest_path_lcc`
- `diameter_lcc`
- `degree_assortativity`
- `tree_excess_ratio`
- `branching_skew`
- `delta_hyperbolicity_proxy`
- `frac_hier_mean`
- `frac_hier_std`
- `frac_hier_min`
- `frac_hier_max`
- `regime_hint`

### `graph_edges.csv`

Required columns:

- `run_id`
- `window_id`
- `patch_id`
- `graph_mode`
- `source`
- `target`
- `weight`
- `is_directed`

## Stage-1 Exploration Design

Stage 1 remains narrow and structural:

- single-patch only
- one seed per config
- no coupling experiments
- compare known source profiles under fixed extraction settings

Planned factorial:

- source profile: `reversal`, `hierarchical_lock`, `low_hierarchy`
- graph mode: `undirected_contact`, `directed_influence`
- window periods: `1`, `2`

Total: 12 configs

Manifest:
- `experiments/configs/phase4/manifest_stage1_exploration.csv`

## Acceptance Tests (Must Be Green Before Exploratory Runs)

1. `test_phase4_graph_extraction_deterministic`
- same config + seed yields byte-identical `graph_windows.csv` and
  `graph_edges.csv`
- pass criterion: repeated run hashes match exactly

2. `test_phase4_metrics_stable_on_synthetic_graphs`
- verify relative metric ordering on controlled graphs:
  - clique: density and clustering greater than ring/path
  - tree/path: `tree_excess_ratio` lower than clique
  - star: branching skew greater than path
- pass criterion: all specified inequalities hold

3. `test_phase4_hierarchical_vs_egalitarian_structural_difference`
- held configs/windows with higher `frac_hier_mean` must differ from lower
  windows on at least one preregistered structural axis
  (`tree_excess_ratio`, `branching_skew`, or `delta_hyperbolicity_proxy`)
- pass criterion: directional difference is present and reproducible across
  repeated runs of the held fixture

4. `test_phase4_output_schema_contract`
- required files and required columns are present
- pass criterion: schema validation succeeds without optional fallbacks

5. `test_phase4_run_index_contract`
- Phase-4 runs retain existing run-index fields and artifact-path guarantees
- pass criterion: no Phase-2/3 reproducibility field disappears or is renamed

No Phase-4 exploratory run is valid until all five tests are green.

## Claim Governance

Pre-results wording:
- "structural signatures are being evaluated"

Allowed claim after Stage 1 only:
- "high-hierarchy windows appear associated with specific structural signatures"

Reserved stronger wording:
- "robustly" only after replicated evidence and predeclared stability checks

## Immediate Implementation Sequence

1. add Phase-4 contract docs and manifest
2. implement acceptance tests
3. implement graph extraction
4. implement structural metrics
5. run smoke configs
6. run Stage-1 exploration
