# Phase 2 Figure Captions (2.E)

## Figure 2E-A: Stage-2 Reversal Probability Heatmap (tau=0.8 profile)

Near-boundary dense refinement (5 seeds per cell) shows a bounded transition
region in which reversal probability is high at lower interpolation values and
collapses at higher interpolation values. For each boundary (`b01`-`b04`),
`P(reversal)=1.0` at alpha `0.35-0.40`, then the regime shifts away from
reversal at alpha `0.42-0.44`. This figure provides the Stage-2
probability-aware phase-map input for claim governance.

## Figure 2E-B: Entropy/Discord Overlay on Stage-2 Probability Map

Uncertainty is reported as an overlay rather than hidden. Normalized entropy and
discord (`1 - max label probability`) are shown on top of the reversal-probability
map to make boundary confidence explicit. In this refinement batch, each cell is
internally consistent across replicates (entropy and discord near zero), so
uncertainty appears as label-region transitions rather than within-cell noise.

## Claim Wording Guardrail

Stage 1 wording: "Seasonal reversals appear in a bounded region of parameter
space."

Stage 2 upgrade status: robust wording is not passed under strict sanity
criteria; keep "appears" as the headline claim.

Conditional/rejected wording record (not approved as headline): "Under the
tau=0.8 threshold profile, seasonal reversals emerge robustly in a bounded
local neighborhood of parameter space around the identified transition
boundaries."

Do not generalize the robust wording to the canonical tau=0.5 profile without
matching replicated evidence.
