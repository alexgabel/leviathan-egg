# Leviathan Egg

**Exploring the dynamics of social organization through computational modeling.**

Understanding how complex social structures emerge, persist, and change over time is a fundamental challenge in the study of social systems. This project uses computational simulations to investigate how groups with flexible social bonds can organize themselves into different political forms and how these forms can shift with seasonal changes.

Key scientific questions include:
- How do egalitarian and hierarchical social structures arise and stabilize?
- What mechanisms drive seasonal reversals in political organization?
- How do multiple societies with overlapping territories maintain distinct social rhythms?
- What role does environmental seasonality play in shaping social dynamics?

Our approach employs agent-based simulations that model individuals interacting within multi-patch environments subject to seasonal forcing. This allows us to capture the interplay between individual behaviors, social ties, and external environmental cycles.

The repository is organized as follows:
- Core simulation code and configuration files for running experiments
- Scripts for data analysis and visualization
- Documentation and metadata to ensure reproducibility
- Alignment and project scope details are documented separately in [`PROJECT_SUMMARY.md`](PROJECT_SUMMARY.md)

For a comprehensive overview of the project goals, scope, and alignment, please refer to the `PROJECT_SUMMARY.md` file, which serves as the authoritative guide.

Current execution details are documented in:
- `paper/notes/phase4_kickoff.md` (current Phase 4 kickoff and implementation slice)
- `paper/notes/phase4_design.md` (Phase 4 design and acceptance tests)
- `experiments/configs/phase4/README.md` (Phase 4 config contract)

Phase 2 closure artifacts are archived at:
- `paper/notes/phase2_results_draft.md`
- `paper/notes/phase2_sanity_pass.md`
- `paper/notes/phase2_frozen_artifacts.sha256`

Before Phase 4 implementation changes, verify the frozen Phase 3 baseline:
- `python scripts/phase3_verify_baseline_lock.py --lock-file experiments/runs/phase3/desync_refine_lag8_fine/baseline_lock.yaml`

Before any Phase-4 exploratory run, acceptance tests must be green:
- `PYTHONPATH=src python -m pytest -q tests/test_phase4_acceptance.py`

Phase-4 execution scripts:
- `python scripts/phase4_generate_configs.py`
- `python scripts/phase4_run_manifest.py`
- `python scripts/phase4_prepare_analysis.py`
- `python scripts/phase4_plot_stage1.py`

First Phase-4 exploration outputs now live under:
- `experiments/runs/phase4/exploration_stage1/analysis_latest_per_config.csv`
- `experiments/runs/phase4/exploration_stage1/structure_profile_summary.csv`
- `experiments/runs/phase4/exploration_stage1/fig_phase4_structure_vs_hierarchy_scatter.png`
- `experiments/runs/phase4/exploration_stage1/fig_phase4_structure_profile_bars.png`

Legacy Phase-2 baseline verification remains available at:
- `python scripts/phase2_verify_frozen_artifacts.py`

<!-- This research is intended for submission to the International Conference on Computational Social Science (ICCS) and will be prepared following the Lecture Notes in Computer Science (LNCS) format. -->

## Phase 3 Claim Governance (Locked)

v1 (headline, conservative):
- robust desynchrony is not established under strict lag-gated criteria.

v2 (conditional, version-scoped):
- robust desynchrony is supported only under the frozen profile `experiments/configs/phase3/desync_v2_thresholds.yaml`
- and only within the reported sensitivity window (`0.920` to `0.939` from `experiments/runs/phase3/desync_refine_lag8_fine/sensitivity_antiphase_threshold.csv`).

Policy:
- any "robust desynchrony" wording must explicitly name classifier version (`v1` or `v2`).

## Phase 4 Claim Governance (Active)

Primary exploratory wording:
- structural signatures appear associated with hierarchy intensity under the current Phase-4 graph schema.

Current scoping:
- graph extraction is snapshot-derived structural observation v1
- claims must name the graph mode and schema version if a result depends on that choice

Reserved stronger wording:
- use "robustly" only after replicated criteria are predeclared and passed.
