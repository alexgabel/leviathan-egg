# Phase 3 Design Draft — Political Desynchronization

Key question:
Do political calendars synchronize across patches or remain persistently out of phase?

Planned additions:
- multi-patch world dynamics
- weak signed patch coupling
- synchrony metrics (for example Kuramoto-style order parameter, phase-lock statistics)

Acceptance tests (pre-implementation):
- uncoupled baseline preserves independent phase behavior
- positive coupling increases synchrony above baseline
- negative/weak coupling permits stable out-of-phase regimes
- per-patch outputs are reproducible with fixed seed

Output schema target:
- per-patch hierarchy time series
- global synchrony summary per run
- lag/phase-lock summaries
