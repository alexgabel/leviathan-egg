# Phase 3 Configs — Multi-Patch Desynchronization Contract

Phase 3 introduces new model elements not allowed in Phase 2:
- multi-patch execution
- explicit inter-patch coupling
- synchrony/desynchrony metrics

Required additions for Phase 3 configs:
- coupling parameter block (strength, sign, mode)
- explicit patch-level seasonal phase offsets
- declared synchrony hypothesis per config

Invariants:
- retain reproducibility contract (config, seed, commit, metrics)
- preserve backward compatibility for Phase 1/2 configs
