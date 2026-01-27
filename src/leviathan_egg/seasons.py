"""
Seasonality scalars for Leviathan Egg.

Phase 1.C:
- Pure functions (no state, no randomness)
- Periodic, smooth drivers based on sinusoidal forcing
- Optional sharp festival pulse layered on top
"""

from __future__ import annotations

import math
from typing import Dict

from leviathan_egg.config import Config


def _sin01(x: float) -> float:
    """
    Smooth periodic signal in [0, 1].
    sin01(0) = 0.5, sin01(pi/2) = 1.0, sin01(3pi/2) = 0.0
    """
    return 0.5 * (1.0 + math.sin(x))


def _pulse(x: float, *, center: float = 0.0, width: float = 0.2) -> float:
    """
    Periodic Gaussian-like pulse on the circle.
    - x in radians
    - center in radians
    - width controls sharpness (smaller = sharper)
    """
    # wrap distance on circle
    d = math.atan2(math.sin(x - center), math.cos(x - center))
    return math.exp(-(d * d) / (2.0 * width * width))


def seasonal_terms(t: int, cfg: Config, patch_id: int = 0) -> Dict[str, float]:
    """
    Compute seasonal scalar drivers at time t for a given patch.

    Returns a dict with:
        - aggregation_benefit
        - coordination_cost
        - hierarchy_rent
        - crisis
        - festival

    Deterministic given (t, cfg, patch_id).
    """
    season_cfg = cfg.seasonality
    period = season_cfg.seasonal_period

    if period <= 0:
        raise ValueError("seasonal_period must be positive")

    # Phase in radians, including patch-specific offset
    phase_offset = season_cfg.phase_offsets.get(f"patch_{patch_id}", 0.0)
    theta = 2.0 * math.pi * (t / period + phase_offset)

    # Base smooth seasonal signal in [0, 1]
    base = _sin01(theta)

    # Extract amplitudes (defaults to 0.0 if absent)
    amps = season_cfg.forcing_amplitudes
    a_agg = float(amps.get("aggregation_benefit", 0.0))
    a_coord = float(amps.get("coordination_cost", 0.0))
    a_rent = float(amps.get("hierarchy_rent", 0.0))
    a_crisis = float(amps.get("crisis", 0.0))
    a_festival = float(amps.get("festival", 0.0))

    # Sign convention: allows inversion of seasonal polarity
    sign = float(season_cfg.forcing_sign.get("authority_coupling", 1.0))

    # Smooth drivers
    aggregation_benefit = 1.0 + a_agg * base
    coordination_cost = 1.0 + a_coord * (1.0 - base)
    hierarchy_rent = 1.0 + sign * a_rent * base
    crisis = a_crisis * (1.0 - base)

    # Festival: sharper pulse near peak aggregation season
    festival_center = math.pi / 2.0  # where sin01 is maximal
    festival_pulse = _pulse(theta, center=festival_center, width=0.25)
    festival = a_festival * festival_pulse

    return {
        "aggregation_benefit": aggregation_benefit,
        "coordination_cost": coordination_cost,
        "hierarchy_rent": hierarchy_rent,
        "crisis": crisis,
        "festival": festival,
    }
