# Phase 4 Kickoff — Structural Signatures

Date: 2026-03-06
Status: Kickoff plan after Phase-3 desynchronization closure

## Closure Gate Status (Phase 3)

- Phase-3 claims are frozen at the closeout baseline in `experiments/runs/phase3/desync_refine_lag8_fine`.
- No retroactive classifier/profile changes are allowed for Phase 3.
- Phase-3 claim governance remains version-scoped:
  - classifier v1: no robust desynchrony under strict lag-gated criteria
  - classifier v2: robust desynchrony only under the frozen profile `experiments/configs/phase3/desync_v2_thresholds.yaml` and its reported stability window

Explicit policy:
"Phase 3 claims are frozen; Phase 4 work must not reframe, retune, or back-edit
Phase-3 headline conclusions."

## Scope Statement

Phase 4 is limited to structural signatures only:
- interaction graph extraction
- structural metric computation
- association of graph structure with hierarchy intensity

Out of scope in this kickoff slice:
- new social dynamics
- new coupling regimes
- Phase-3 classifier changes
- paper-level claim escalation beyond structural-signature evidence

## First Implementation Slice (Contracts Before Code)

Objective:
Define the exact graph-extraction contract, output schema, and acceptance tests
before implementing any Phase-4 instrumentation.

Slice P4-S1 deliverables:
1. Kickoff note and design spec
- `paper/notes/phase4_kickoff.md`
- `paper/notes/phase4_design.md`

2. Config contract
- `experiments/configs/phase4/README.md`
- `experiments/configs/phase4/manifest_stage1_exploration.csv`

3. Acceptance-test plan
- deterministic graph extraction
- controlled synthetic graph metric checks
- hierarchy-structure association checks on held configs
- Phase-4 output schema contract

## Immediate Deliverables

1. Finalize Phase-4 contract docs.
2. Implement acceptance tests before exploratory runs.
3. Only then add Phase-4 graph extraction and structural metrics code.

## Non-Goals (This Slice)

- No Phase-4 scientific claims yet.
- No retroactive edits to Phase-3 claims or artifacts.
- No Phase-5 packaging work.
