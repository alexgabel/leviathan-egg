"""
Metrics / observation layer for Leviathan Egg.

Phase 1.E:
- Pure, read-only functions operating on world state
- No side effects
- Deterministic given inputs
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional

import numpy as np

from leviathan_egg.world import World


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


def collect_metrics(
    world: World,
    *,
    season: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Collect all Phase 1 metrics into a flat dict.

    `season` may optionally include raw scalar drivers (e.g. festival, crisis)
    for logging alongside endogenous metrics.
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

    return metrics
