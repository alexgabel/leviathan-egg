"""
Metrics / observation layer for Leviathan Egg.

Phase 1.E:
- Pure, read-only functions operating on world state
- No side effects
- Deterministic given inputs
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np

from leviathan_egg.world import World


PHASE3_SYNCHRONY_KEYS = (
    "synchrony_order_parameter",
    "synchrony_phase_lock_fraction",
    "synchrony_mean_abs_phase_lag",
)
# Back-compat alias used by existing tests/docs.
PHASE3_SYNCHRONY_PLACEHOLDER_KEYS = (
    *PHASE3_SYNCHRONY_KEYS,
    "synchrony_placeholder_flag",
)


def frac_hier(world: World) -> float:
    """
    Fraction of agents currently in hierarchical (authority_on) groups.
    """
    total_agents = len(world.agents)
    if total_agents == 0:
        return 0.0

    count = 0
    for g in world.groups.values():
        if g.authority_on:
            count += len(g.members)
    return count / total_agents


def num_groups(world: World) -> int:
    """
    Number of extant groups.
    """
    return len(world.groups)


def mean_group_size(world: World) -> float:
    """
    Mean group size across all groups.
    """
    if not world.groups:
        return 0.0
    sizes = [len(g.members) for g in world.groups.values()]
    return float(np.mean(sizes))


def max_group_size(world: World) -> int:
    """
    Maximum group size.
    """
    if not world.groups:
        return 0
    return max(len(g.members) for g in world.groups.values())


def gini_prestige(world: World) -> float:
    """
    Gini coefficient of agent prestige distribution.

    Returns 0.0 for perfectly equal prestige, approaching 1.0 for extreme inequality.
    """
    prestiges = np.array([a.prestige for a in world.agents.values()], dtype=float)
    if prestiges.size == 0:
        return 0.0

    # Shift to non-negative if necessary
    min_val = prestiges.min()
    if min_val < 0:
        prestiges = prestiges - min_val

    mean = prestiges.mean()
    if mean == 0:
        return 0.0

    diff_sum = np.abs(prestiges[:, None] - prestiges[None, :]).sum()
    gini = diff_sum / (2.0 * prestiges.size**2 * mean)
    return float(gini)


def frac_hier_by_patch(world: World) -> Dict[int, float]:
    """
    Per-patch fraction of agents in hierarchical groups.
    """
    values: Dict[int, float] = {}
    for patch_id in sorted(world.patches.keys()):
        patch = world.patches[patch_id]
        total_agents = len(patch.agent_ids)
        if total_agents == 0:
            values[patch_id] = 0.0
            continue

        hier_agents = 0
        for gid in patch.group_ids:
            g = world.groups[gid]
            if g.authority_on:
                hier_agents += len(g.members)
        values[patch_id] = hier_agents / total_agents
    return values


def synchrony_metrics(world: World) -> Dict[str, float]:
    """
    Compute Phase 3 synchrony summaries from per-patch hierarchy trajectories.

    Metrics:
    - synchrony_order_parameter: circular concentration of current patch hierarchy phases
    - synchrony_phase_lock_fraction: share of patch-pairs with small phase distance
    - synchrony_mean_abs_phase_lag: mean absolute best cross-correlation lag (steps)
    """
    by_patch = frac_hier_by_patch(world)
    patch_ids = sorted(by_patch.keys())
    n = len(patch_ids)
    if n <= 1:
        return {
            "synchrony_order_parameter": 1.0,
            "synchrony_phase_lock_fraction": 1.0,
            "synchrony_mean_abs_phase_lag": 0.0,
            "synchrony_placeholder_flag": 0.0,
        }

    values = np.array([by_patch[p] for p in patch_ids], dtype=float)
    phases = 2.0 * np.pi * values
    order_parameter = float(np.abs(np.mean(np.exp(1j * phases))))

    # Phase-lock is defined on circular distance in normalized hierarchy phase space.
    phase_lock_threshold = 0.15
    lock_threshold_rad = 2.0 * np.pi * phase_lock_threshold
    locked = []
    for i in range(n):
        for j in range(i + 1, n):
            raw = abs(phases[i] - phases[j])
            circ = min(raw, 2.0 * np.pi - raw)
            locked.append(1.0 if circ <= lock_threshold_rad else 0.0)
    phase_lock_fraction = float(np.mean(locked)) if locked else 1.0

    # Lag summary from recent per-patch hierarchy histories.
    period = max(1, int(world.cfg.seasonality.seasonal_period))
    max_lag = max(1, period // 4)
    window = max(period, 4 * max_lag)
    abs_lags = []
    for i in range(n):
        for j in range(i + 1, n):
            hi = np.asarray(world.patch_hierarchy_history(patch_ids[i], window=window), dtype=float)
            hj = np.asarray(world.patch_hierarchy_history(patch_ids[j], window=window), dtype=float)
            m = min(len(hi), len(hj))
            if m < 4:
                continue
            hi = hi[-m:] - np.mean(hi[-m:])
            hj = hj[-m:] - np.mean(hj[-m:])
            corr = np.correlate(hi, hj, mode="full")
            lags = np.arange(-m + 1, m)
            mask = np.abs(lags) <= max_lag
            if not np.any(mask):
                continue
            best_lag = int(lags[mask][int(np.argmax(corr[mask]))])
            abs_lags.append(abs(best_lag))
    mean_abs_phase_lag = float(np.mean(abs_lags)) if abs_lags else 0.0

    return {
        "synchrony_order_parameter": order_parameter,
        "synchrony_phase_lock_fraction": phase_lock_fraction,
        "synchrony_mean_abs_phase_lag": mean_abs_phase_lag,
        "synchrony_placeholder_flag": 0.0,
    }


def collect_phase3_scaffolding_metrics(world: World) -> Dict[str, float]:
    """
    Return Phase 3 scaffolding fields:
    - frac_hier_patch_{i} for each patch
    - synchrony summary slots
    """
    metrics: Dict[str, float] = {}
    if world.num_patches <= 1:
        return metrics

    per_patch = frac_hier_by_patch(world)
    for patch_id in sorted(per_patch.keys()):
        metrics[f"frac_hier_patch_{patch_id}"] = float(per_patch[patch_id])

    metrics.update(synchrony_metrics(world))
    return metrics


def collect_metrics(
    world: World,
    *,
    season: Optional[Dict[str, float]] = None,
    include_phase3_scaffolding: bool = False,
) -> Dict[str, float]:
    """
    Collect all Phase 1 metrics into a flat dict.

    `season` may optionally include raw scalar drivers (e.g. festival, crisis).
    `include_phase3_scaffolding` adds per-patch and synchrony summary fields.
    Default is `False` to keep Phase 1/2 outputs bit-for-bit stable.
    """
    metrics: Dict[str, float] = {
        "frac_hier": frac_hier(world),
        "num_groups": float(num_groups(world)),
        "mean_group_size": mean_group_size(world),
        "max_group_size": float(max_group_size(world)),
        "gini_prestige": gini_prestige(world),
    }

    if season is not None:
        # Only log known raw drivers if present
        for key in ("festival", "crisis"):
            if key in season:
                metrics[key] = float(season[key])

    if include_phase3_scaffolding:
        metrics.update(collect_phase3_scaffolding_metrics(world))

    return metrics
