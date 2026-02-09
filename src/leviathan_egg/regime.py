"""
Phase 2 regime classification utilities.

This module classifies post-burn-in hierarchy time series into:
- egalitarian
- hierarchical
- reversal
- uncertain
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
import yaml


@dataclass(frozen=True)
class RegimeThresholds:
    tau: float = 0.5
    duty_egal_max: float = 0.2
    duty_hier_min: float = 0.8
    max_switch_rate_stable: float = 0.02
    min_switch_rate_reversal: float = 0.02
    min_dwell_fraction_of_period: float = 0.10
    min_abs_seasonal_coherence: float = 0.20
    seasonal_coherence_required: bool = True


@dataclass(frozen=True)
class RegimeResult:
    label: str
    duty: float
    switch_count: int
    switch_rate: float
    max_dwell_hier: int
    max_dwell_egal: int
    seasonal_coherence: Optional[float]
    seasonal_lag: Optional[int]
    confidence: float


def load_regime_thresholds(path: str | Path) -> RegimeThresholds:
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected mapping at {p}, got {type(raw).__name__}")
    return RegimeThresholds(
        tau=float(raw.get("tau", RegimeThresholds.tau)),
        duty_egal_max=float(raw.get("duty_egal_max", RegimeThresholds.duty_egal_max)),
        duty_hier_min=float(raw.get("duty_hier_min", RegimeThresholds.duty_hier_min)),
        max_switch_rate_stable=float(
            raw.get("max_switch_rate_stable", RegimeThresholds.max_switch_rate_stable)
        ),
        min_switch_rate_reversal=float(
            raw.get("min_switch_rate_reversal", RegimeThresholds.min_switch_rate_reversal)
        ),
        min_dwell_fraction_of_period=float(
            raw.get(
                "min_dwell_fraction_of_period",
                RegimeThresholds.min_dwell_fraction_of_period,
            )
        ),
        min_abs_seasonal_coherence=float(
            raw.get("min_abs_seasonal_coherence", RegimeThresholds.min_abs_seasonal_coherence)
        ),
        seasonal_coherence_required=bool(
            raw.get("seasonal_coherence_required", RegimeThresholds.seasonal_coherence_required)
        ),
    )


def classify_regime(
    frac_hier: Sequence[float],
    *,
    period_steps: int,
    seasonal_driver: Optional[Sequence[float]] = None,
    thresholds: Optional[RegimeThresholds] = None,
) -> RegimeResult:
    th = thresholds or RegimeThresholds()
    x = _validate_frac_hier(frac_hier, period_steps=period_steps)
    states = x > th.tau
    return _classify_with_states(
        x=x,
        states=states,
        period_steps=period_steps,
        seasonal_driver=seasonal_driver,
        thresholds=th,
    )


def classify_regime_hysteresis(
    frac_hier: Sequence[float],
    *,
    period_steps: int,
    lower_tau: float,
    upper_tau: float,
    seasonal_driver: Optional[Sequence[float]] = None,
    thresholds: Optional[RegimeThresholds] = None,
) -> RegimeResult:
    """
    Classify regimes with Schmitt-trigger style binarization.

    State transitions require crossing different thresholds:
    - OFF -> ON only when frac_hier >= upper_tau
    - ON -> OFF only when frac_hier <= lower_tau

    This suppresses label brittleness from near-threshold jitter.
    """
    if not np.isfinite(lower_tau) or not np.isfinite(upper_tau):
        raise ValueError("lower_tau/upper_tau must be finite")
    if lower_tau >= upper_tau:
        raise ValueError("lower_tau must be strictly less than upper_tau")
    if lower_tau < 0.0 or upper_tau > 1.0:
        raise ValueError("lower_tau/upper_tau must lie within [0, 1]")

    th = thresholds or RegimeThresholds()
    x = _validate_frac_hier(frac_hier, period_steps=period_steps)
    states = _hysteresis_states(x, lower_tau=lower_tau, upper_tau=upper_tau)
    return _classify_with_states(
        x=x,
        states=states,
        period_steps=period_steps,
        seasonal_driver=seasonal_driver,
        thresholds=th,
    )


def _validate_frac_hier(frac_hier: Sequence[float], *, period_steps: int) -> np.ndarray:
    x = np.asarray(frac_hier, dtype=float)
    if x.ndim != 1 or x.size < 3:
        raise ValueError("frac_hier must be a 1D sequence with at least 3 points")
    if period_steps <= 0:
        raise ValueError("period_steps must be positive")
    return x


def _hysteresis_states(x: np.ndarray, *, lower_tau: float, upper_tau: float) -> np.ndarray:
    states = np.zeros(x.size, dtype=bool)
    mid = 0.5 * (lower_tau + upper_tau)
    if x[0] >= upper_tau:
        state = True
    elif x[0] <= lower_tau:
        state = False
    else:
        state = bool(x[0] >= mid)

    for i, v in enumerate(x):
        if state:
            if v <= lower_tau:
                state = False
        else:
            if v >= upper_tau:
                state = True
        states[i] = state
    return states


def _classify_with_states(
    *,
    x: np.ndarray,
    states: np.ndarray,
    period_steps: int,
    seasonal_driver: Optional[Sequence[float]],
    thresholds: RegimeThresholds,
) -> RegimeResult:
    th = thresholds

    duty = float(states.mean())
    transitions = int(np.count_nonzero(states[1:] != states[:-1]))
    switch_rate = transitions / max(1, states.size - 1)

    max_dwell_hier = _max_dwell(states, True)
    max_dwell_egal = _max_dwell(states, False)
    min_dwell_steps = max(1, int(round(th.min_dwell_fraction_of_period * period_steps)))

    coherence: Optional[float] = None
    lag: Optional[int] = None
    if seasonal_driver is not None:
        coherence, lag = _max_abs_lagged_corr(x, np.asarray(seasonal_driver, dtype=float), period_steps)

    can_be_stable = switch_rate <= th.max_switch_rate_stable

    if duty <= th.duty_egal_max and can_be_stable:
        conf = _clip01(
            0.5
            + 0.5 * (th.duty_egal_max - duty) / max(1e-9, th.duty_egal_max)
            + 0.5 * (th.max_switch_rate_stable - switch_rate) / max(1e-9, th.max_switch_rate_stable)
        )
        return RegimeResult(
            label="egalitarian",
            duty=duty,
            switch_count=transitions,
            switch_rate=switch_rate,
            max_dwell_hier=max_dwell_hier,
            max_dwell_egal=max_dwell_egal,
            seasonal_coherence=coherence,
            seasonal_lag=lag,
            confidence=conf,
        )

    if duty >= th.duty_hier_min and can_be_stable:
        conf = _clip01(
            0.5
            + 0.5 * (duty - th.duty_hier_min) / max(1e-9, 1.0 - th.duty_hier_min)
            + 0.5 * (th.max_switch_rate_stable - switch_rate) / max(1e-9, th.max_switch_rate_stable)
        )
        return RegimeResult(
            label="hierarchical",
            duty=duty,
            switch_count=transitions,
            switch_rate=switch_rate,
            max_dwell_hier=max_dwell_hier,
            max_dwell_egal=max_dwell_egal,
            seasonal_coherence=coherence,
            seasonal_lag=lag,
            confidence=conf,
        )

    has_duty_balance = th.duty_egal_max < duty < th.duty_hier_min
    has_switching = switch_rate >= th.min_switch_rate_reversal
    has_dwell = max_dwell_hier >= min_dwell_steps and max_dwell_egal >= min_dwell_steps
    has_coherence = (
        True
        if not th.seasonal_coherence_required
        else (coherence is not None and abs(coherence) >= th.min_abs_seasonal_coherence)
    )

    if has_duty_balance and has_switching and has_dwell and has_coherence:
        conf = _clip01(
            0.4
            + 0.3 * (switch_rate - th.min_switch_rate_reversal) / max(1e-9, 1.0 - th.min_switch_rate_reversal)
            + 0.3
            * (
                0.0
                if coherence is None
                else (abs(coherence) - th.min_abs_seasonal_coherence)
                / max(1e-9, 1.0 - th.min_abs_seasonal_coherence)
            )
        )
        return RegimeResult(
            label="reversal",
            duty=duty,
            switch_count=transitions,
            switch_rate=switch_rate,
            max_dwell_hier=max_dwell_hier,
            max_dwell_egal=max_dwell_egal,
            seasonal_coherence=coherence,
            seasonal_lag=lag,
            confidence=conf,
        )

    return RegimeResult(
        label="uncertain",
        duty=duty,
        switch_count=transitions,
        switch_rate=switch_rate,
        max_dwell_hier=max_dwell_hier,
        max_dwell_egal=max_dwell_egal,
        seasonal_coherence=coherence,
        seasonal_lag=lag,
        confidence=0.25,
    )


def _max_dwell(states: np.ndarray, value: bool) -> int:
    max_run = 0
    run = 0
    for s in states:
        if bool(s) == value:
            run += 1
            if run > max_run:
                max_run = run
        else:
            run = 0
    return max_run


def _max_abs_lagged_corr(x: np.ndarray, y: np.ndarray, period_steps: int) -> tuple[float, int]:
    if x.shape != y.shape:
        raise ValueError("seasonal_driver must have same length as frac_hier")

    x0 = x - x.mean()
    y0 = y - y.mean()
    x_sd = float(x0.std())
    y_sd = float(y0.std())
    if x_sd == 0.0 or y_sd == 0.0:
        return 0.0, 0

    best_corr = 0.0
    best_lag = 0
    max_lag = min(period_steps, max(1, x.size - 2))
    for lag in range(max_lag):
        if lag == 0:
            a = x0
            b = y0
        else:
            a = x0[:-lag]
            b = y0[lag:]
        if a.size < 3:
            break
        corr = float(np.corrcoef(a, b)[0, 1])
        if abs(corr) > abs(best_corr):
            best_corr = corr
            best_lag = lag
    return best_corr, best_lag


def _clip01(v: float) -> float:
    return float(np.clip(v, 0.0, 1.0))
