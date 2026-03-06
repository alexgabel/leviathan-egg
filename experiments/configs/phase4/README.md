# Phase 4 Configs — Structural Signature Contract

Status: Kickoff (contracts before code)

Authoritative kickoff note:
- `paper/notes/phase4_kickoff.md`

Authoritative design spec:
- `paper/notes/phase4_design.md`

## Scope Lock

Phase 4 is limited to structural signatures:
- interaction graph extraction
- graph metric computation by window
- association with hierarchy intensity

Phase 4 must not:
- change Phase-3 claims or classifier/profile governance
- alter non-Phase-4 dynamics semantics
- bypass the standard manifest -> generated YAML -> run-index harness

Preflight check before Phase-4 code or runs:
- `python scripts/phase3_verify_baseline_lock.py --lock-file experiments/runs/phase3/desync_refine_lag8_fine/baseline_lock.yaml`

## Phase-3 Freeze Invariant

The following are frozen and must remain untouched by Phase-4 work:
- Phase-3 closeout run root:
  `experiments/runs/phase3/desync_refine_lag8_fine`
- Phase-3 threshold profile:
  `experiments/configs/phase3/desync_v2_thresholds.yaml`

Policy:
- no retroactive classifier/profile changes for Phase 3
- no new Phase-3 exploratory sweeps while the closeout baseline is locked

## Harness Contract

Phase 4 follows the same execution harness as Phase 2/3:

1. manifest defines the Stage-1 exploration sweep
2. generator writes YAML configs under `experiments/configs/phase4/`
3. runner writes run directories under `experiments/runs/phase4/`
4. `run_index.csv` records standard reproducibility fields and artifact paths

Required manifest:
- `experiments/configs/phase4/manifest_stage1_exploration.csv`

Expected future scripts:
- `scripts/phase4_generate_configs.py`
- `scripts/phase4_run_manifest.py`
- `scripts/phase4_prepare_analysis.py`

## Stage-1 Exploration Contract

Stage 1 is a 12-config, one-seed-per-config sweep over:
- source profile: `reversal`, `hierarchical_lock`, `low_hierarchy`
- graph mode: `undirected_contact`, `directed_influence`
- extraction window: `1` or `2` seasonal periods

Manifest semantics:
- `config_path`: planned YAML path under `experiments/configs/phase4/`
- `sweep_axis`: stable label for the exploration design
- `sweep_value`: compact encoding of the source profile + extraction settings
- `hypothesis`: expected qualitative structural outcome
- `seed`: unique seed per config
- `stage`: `exploration`
- `notes`: additional frozen metadata for the future generator/runner

## Required Phase-4 Config Additions

Every Phase-4 config must include the standard fields from
`experiments/configs/README.md` plus:

- `graph_extraction.graph_mode`
- `graph_extraction.window_periods`
- `graph_extraction.emit_edge_list`
- `graph_extraction.emit_window_metrics`
- `graph_extraction.pool_patches` (default `false`)
- `structural_metrics.metrics_to_compute`
- `structural_metrics.hyperbolicity_proxy_mode`
- `source_profile`

## Output Contract

In addition to the standard run artifacts, Phase-4 runs must emit:
- `graph_windows.csv`
- `graph_edges.csv`
- `graph_schema_version.txt`

The exact required columns and windowing rules are defined in
`paper/notes/phase4_design.md`.

## Activation Rule

This directory is contract-first. Do not launch Phase-4 exploratory runs until:
- acceptance tests in `paper/notes/phase4_design.md` are implemented and green
- graph extraction schema is implemented
- Phase-3 baseline lock still verifies

## Claim Governance

Primary wording for Phase-4 exploratory results must remain conservative:
- "structural signatures appear associated with hierarchy intensity"

Reserved stronger wording:
- use "robustly" only after predeclared replicated criteria pass
- if structural metrics or extraction modes differ across analyses, name the exact
  graph mode and schema version explicitly

Current implementation scope:
- snapshot-derived structural observation v1
- graph schema version recorded in `graph_schema_version.txt`
