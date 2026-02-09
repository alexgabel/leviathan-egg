# Leviathan Egg
**Reversible domination, seasonal forcing, and political desynchronization in fission–fusion societies**

## 1. Purpose (Do Not Drift)
Leviathan Egg is a minimal, reproducible agent-based model exploring how
seasonal or periodic forcing, combined with reversible authority structures,
can generate:
1. Stable egalitarian societies
2. Stable hierarchical societies
3. Seasonal reversals of political form

The model explicitly allows **desynchronized political calendars** across
coexisting societies (patches).

This project does NOT attempt historical reconstruction, normative claims,
or universal laws of state formation.

## 2. Core Research Questions
1. Under what conditions do seasonal reversals of hierarchy occur?
2. Do political calendars synchronize globally or remain locally phase-shifted?
3. Can seasonal hierarchy direction invert across ecologies?
4. Do hierarchical phases exhibit measurable tree-like / hyperbolic
   network signatures?

## 3. Theoretical Background (High-Level)
Authority is modeled via three separable channels:
- Violence (exit friction / coercion)
- Information (asymmetry, memory, bureaucratic lock-in)
- Charisma (temporary prestige amplification, festivals)

Seasonality is treated as periodic forcing on aggregation benefits and
coordination needs, not as a fixed "winter = hierarchy" rule.

## 4. Project Phases and Deliverables

### Phase Transition Note (Phase 1 → Phase 2)

Phase 1 (Core Engine) is complete and frozen under the tag `phase1-complete`.
All simulation dynamics, seasonal forcing, authority mechanisms, metrics,
and the CLI runner are considered **stable**.

Phase 2 operates strictly on top of the Phase‑1 engine and introduces:
- No changes to agent dynamics or world update rules
- No new social mechanisms or parameters
- No multi‑patch interactions

Any required changes to the core engine invalidate Phase‑2 results and must
be deferred to a later phase.

### Phase 1 — Core Engine
- Single-patch ABM
- Reproducible runs (seeded)
- Demonstrate 3 regimes

### Phase 2 — Phase Diagram (closed; results frozen)

Phase 2 focuses on systematic exploration of parameter space in a **single‑patch**
world to identify and classify qualitative political regimes.

Execution is explicitly two-stage:
- Stage 1 (exploration): map broad regime structure and identify candidate reversal zones
- Stage 2 (confirmation): replicate and densify only near candidate boundaries

Scope:
- Parameter sweeps over:
  - seasonal forcing amplitude and bias
  - violence / exit friction
  - information / memory lock‑in
  - charisma / festival amplification
- Long, seeded runs using the Phase‑1 engine
- No modification of world dynamics
- `world_structure.num_patches` and extra `seasonality.phase_offsets` fields are inert in
  Phase 2 because only `patch_0` is simulated in the Phase‑1 world engine

Deliverables:
- Operational regime definitions:
  - Stable egalitarian
  - Stable hierarchical
  - Seasonal political reversal
  - Uncertain / borderline
- Quantitative reversal criteria based on time‑series metrics
- Phase diagrams over selected parameter axes
- Representative time‑series figures
- Frozen Phase‑2 thresholds before bulk analysis
- Reproducible run index and failure markers

Non‑goals (explicit):
- No multi‑patch or synchronization analysis (Phase 3)
- No network or hyperbolicity metrics (Phase 4)
- No optimization, learning, or adaptive agents

Claim policy:
- Stage 1 allowed claim: "reversals appear in a bounded region"
- classifier-invariant "robustly" upgrade is not passed under strict sanity criteria
- frozen artifact manifest: `paper/notes/phase2_frozen_artifacts.sha256`

### Phase 3 — Multi-Patch Desynchronization (current kickoff)
- Independent seasonal phases
- Signed seasonal coupling
- Synchrony metrics

### Phase 4 — Structural Signatures
- Interaction graphs
- Hyperbolicity / tree-likeness metrics
- Correlation with hierarchy

### Phase 5 — Paper Packaging
- Mini-paper draft
- Reproducible figures
- Open configs

## 5. Non-Goals
- No agent cognition modeling
- No ethnographic calibration
- No normative political claims
- No machine learning components

## 6. Reproducibility Contract
Every run must record:
- Full resolved config
- Random seed
- Git commit hash
- Machine-independent metrics

Any result without this metadata is invalid.

## 7. Success Criteria
The project is successful if:
- Seasonal reversals appear in a bounded parameter region
- Multi-patch worlds exhibit persistent desynchronization
- Hierarchical phases show consistent structural signatures

Anything beyond this is optional.
