# Phase 2 Protocol — Regime Mapping and Phase Diagram

Status: Active

Scientific goal:
Demonstrate that seasonal political reversals appear in a bounded, interpretable
single-patch parameter region using the frozen Phase-1 engine.

## 0. Guardrails

- No Phase-1 world dynamics changes in Phase 2.
- No multi-patch coupling dynamics in Phase 2.
- Thresholds are frozen before bulk plotting.
- Exploratory (Stage 1) and confirmatory (Stage 2) analyses are separated.
- Every run is either valid-complete or explicitly failed.

## 1. Stage Plan

## 1.A Formalize Regime Definitions

Objective:
Turn qualitative regimes into reproducible labels.

Deliverables:
- `phase2_regime_definition.md`
- classifier implementation in `src/leviathan_egg/regime.py`
- threshold source in `experiments/configs/phase2/regime_thresholds.yaml`

Exit criterion:
Any run can be labeled without visual inspection.

## 1.B Design Sweep

Objective:
Build a compact but expressive sampling design.

Deliverables:
- Stage 1 manifest: `manifest_exploration.csv`
- Stage 2 manifest: `manifest_confirmation.csv`
- hypotheses in `experiments/configs/phase2/README.md`

Design:
- Stage 1: 12-24 configs, 1 seed each
- Stage 2: candidate transition region only, denser slice, 3-5 seeds/cell

Exit criterion:
All configs are enumerable and hypothesis-tagged.

## 1.C Execute Runs and Log Provenance

Objective:
Generate reproducible run artifacts with explicit failure semantics.

Deliverables:
- run artifacts per run (`metrics.csv`, `config_resolved.yaml`, `seed.txt`, `git_commit.txt`)
- run index at `experiments/runs/phase2/run_index.csv`
- `FAILED.txt` for failed runs

Policy:
- default retry budget: 1 retry
- no silent overwrite

Exit criterion:
Any run can be replayed from config+seed+commit.

## 1.D Analyze Regimes

Objective:
Show regime structure and identify reversal candidates.

Deliverables:
- labels for all runs
- representative time-series plots
- short interpretation notes

Procedure:
- freeze thresholds before bulk analysis
- one pilot run allowed for threshold setting
- representative runs selected by objective rule (for example highest confidence)

Exit criterion:
At least one clean reversal candidate is documented.

## 1.E Phase Diagram

Objective:
Map regime occupancy in parameter space.

Deliverables:
- Stage 1 regime map (single-seed labels)
- Stage 2 regime probability map (multi-seed)
- uncertainty overlay (entropy/discord) for Stage 2 only

Exit criterion:
One publishable 2D slice with mechanism caption.

## 1.F Write Phase 2 Results Note

Objective:
Lock claims before Phase 3 expansion.

Deliverables:
- concise methods summary (delta from Phase 1)
- regime map and representative traces
- limitations and explicit Phase 3/4 deferrals

Exit criterion:
Phase 2 stands on its own.

## 2. Claim Policy and Hard Stop

Stage 1 allowed statement:
"Seasonal reversals appear in a bounded region of parameter space."

Stage 2 robust statement requires explicit criteria such as:
- seed robustness (`>=4/5` seeds in local neighborhood), and
- local perturbation stability around candidate cells.

Hard stop:
Phase 2 ends when bounded-region evidence is reproducible and documented.
