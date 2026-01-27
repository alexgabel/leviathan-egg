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

### Phase 1 — Core Engine
- Single-patch ABM
- Reproducible runs (seeded)
- Demonstrate 3 regimes

### Phase 2 — Phase Diagram
- Parameter sweeps
- Reversal criterion
- Regime classification

### Phase 3 — Multi-Patch Desynchronization
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