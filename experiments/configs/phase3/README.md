# Phase 3 Configs — Multi-Patch Desynchronization Contract

Status: Active (M3 coupling v1 + synchrony metrics)

Authoritative kickoff note:
- `paper/notes/phase3_kickoff.md`

## Scope Lock

Phase 3 introduces model elements that were out-of-scope for Phase 2:
- multi-patch execution
- explicit inter-patch coupling
- synchrony/desynchrony metrics

No retroactive Phase-2 claim edits are allowed during Phase 3 implementation.
Preflight check before Phase 3 changes:
- `python scripts/phase2_verify_frozen_artifacts.py`

## First Implementation Slice (Acceptance-Tests First)

Implementation status:
1. config schema and validation invariants
2. multi-patch world container/plumbing with single-patch regression preserved
3. weak signed coupling v1 + per-patch/synchrony output schema
4. runner compatibility with existing reproducibility/run-index contracts

Acceptance tests to implement first:
- `test_phase3_single_patch_regression`
- `test_phase3_uncoupled_independence`
- `test_phase3_positive_coupling_directional_effect`
- `test_phase3_negative_or_weak_coupling_allows_desync`
- `test_phase3_reproducible_per_patch_outputs`
- `test_phase3_output_schema_contract`

M2 gate command (must be green before exploratory Phase 3 runs):
- `PYTHONPATH=src python -m pytest -q tests/test_phase3_acceptance.py`

## Required Phase 3 Config Additions

- coupling parameter block (strength, sign, mode, topology)
- explicit patch-level seasonal phase offsets
- declared synchrony hypothesis per config

## Invariants

- retain reproducibility contract (config, seed, commit, metrics)
- preserve backward compatibility for Phase 1/2 configs
- Phase 1/2 configs must remain runnable without schema-breaking changes
