# Phase 3 Kickoff — Political Desynchronization

Date: 2026-02-09
Status: Kickoff plan after Phase-2 closure checkpoint

## Closure Gate Status (Phase 2)

- Primary claim locked to "appears" in `paper/notes/phase2_results_draft.md`.
- Sanity appendix linked and frozen in `paper/notes/phase2_sanity_pass.md`.
- Frozen artifact manifest exists at `paper/notes/phase2_frozen_artifacts.sha256`.
- Claim governance ambiguity resolved: no classifier-invariant "robustly" headline claim.

## Scope Statement

Phase 3 starts now, but only with scaffolding:
- no retroactive changes to Phase-2 claims or figures
- no modification of frozen Phase-2 artifacts
- no hidden Phase-3 dynamics edits in Phase-2 code paths

Explicit policy:
"Phase 2 claims are frozen; Phase 3 work must not reframe or back-edit Phase-2
headline conclusions."

## First Implementation Slice (Scaffolding Only)

Objective:
Prepare multi-patch infrastructure and output contracts without introducing full
coupled political dynamics yet.

Slice P3-S1 tasks:
1. Config scaffolding
- Define explicit coupling schema in config parsing (strength, sign, topology, mode).
- Add validation invariants (patch count consistency, coupling bounds, seed policy).
- Keep defaults equivalent to uncoupled behavior.

2. World scaffolding
- Introduce multi-patch container/state plumbing in `world.py` behind Phase-3 config paths.
- Preserve Phase-1-equivalent behavior when `num_patches=1` or coupling is disabled.
- Do not yet tune scientific coupling mechanisms beyond pass-through scaffolding.

3. Metrics/output scaffolding
- Add per-patch time-series output schema targets:
  - `frac_hier_patch_i`
  - optional patch-local seasonal phase metadata
- Add global synchrony-summary placeholders:
  - order parameter slot
  - phase-lock/lag summary slots
- Ensure run artifacts remain Phase-2 contract-compatible.

4. Runner/CLI scaffolding
- Keep existing reproducibility guarantees and run-index contract unchanged.
- Add schema-versioned output fields only (no breaking rename/removal).

## Acceptance Tests to Implement First

Implement tests before enabling substantive coupling behavior:

1. `test_phase3_single_patch_regression`
- For equivalent config/seed, single-patch outputs match pre-Phase-3 behavior.

2. `test_phase3_uncoupled_independence`
- With `num_patches > 1` and coupling disabled/zero, patches evolve independently
  under their own phase offsets (no forced synchrony).

3. `test_phase3_positive_coupling_directional_effect`
- Enabling positive coupling increases synchrony metric above uncoupled baseline
  in a controlled fixture.

4. `test_phase3_negative_or_weak_coupling_allows_desync`
- Weak/negative coupling allows persistent out-of-phase behavior in fixture runs.

5. `test_phase3_reproducible_per_patch_outputs`
- Fixed seed reproduces per-patch time series and synchrony summaries exactly.

6. `test_phase3_output_schema_contract`
- Required per-patch and global synchrony fields are present with stable names.

## Phase 3 Immediate Deliverables

1. Implement P3-S1 scaffolding only.
2. Add/greenlight acceptance tests above.
3. Produce `phase3_scaffold_notes.md` with:
- config schema additions
- output schema additions
- explicit list of dynamics not yet enabled.

## Non-Goals (This Slice)

- No claim-making on synchronization science yet.
- No graph-geometry/hyperbolicity work (Phase 4).
- No rewriting or relaxing Phase-2 claim governance.
