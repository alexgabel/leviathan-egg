import numpy as np
import pytest

from leviathan_egg.regime import (
    RegimeThresholds,
    classify_regime,
    classify_regime_hysteresis,
)


def test_classifies_stable_egalitarian():
    x = np.full(200, 0.1)
    y = np.sin(np.linspace(0.0, 4.0 * np.pi, x.size))
    out = classify_regime(x, period_steps=50, seasonal_driver=y)
    assert out.label == "egalitarian"
    assert out.switch_count == 0


def test_classifies_stable_hierarchical():
    x = np.full(200, 0.9)
    y = np.sin(np.linspace(0.0, 4.0 * np.pi, x.size))
    out = classify_regime(x, period_steps=50, seasonal_driver=y)
    assert out.label == "hierarchical"
    assert out.switch_count == 0


def test_classifies_reversal_with_switching_and_coherence():
    period = 40
    t = np.arange(400)
    # Square-like alternation across seasons.
    x = np.where((t // (period // 2)) % 2 == 0, 0.85, 0.15)
    y = np.sin(2.0 * np.pi * t / period)

    thresholds = RegimeThresholds(
        tau=0.5,
        duty_egal_max=0.2,
        duty_hier_min=0.8,
        max_switch_rate_stable=0.005,
        min_switch_rate_reversal=0.01,
        min_dwell_fraction_of_period=0.1,
        min_abs_seasonal_coherence=0.1,
        seasonal_coherence_required=True,
    )
    out = classify_regime(x, period_steps=period, seasonal_driver=y, thresholds=thresholds)
    assert out.label == "reversal"
    assert out.switch_count > 0


def test_borderline_series_is_uncertain():
    # Near-threshold jitter with no meaningful dwell structure.
    x = np.where(np.arange(300) % 2 == 0, 0.49, 0.51)
    y = np.sin(np.linspace(0.0, 6.0 * np.pi, x.size))
    out = classify_regime(x, period_steps=60, seasonal_driver=y)
    assert out.label == "uncertain"
    assert out.switch_count > 0


def test_hysteresis_reduces_threshold_chatter():
    t = np.arange(500)
    x = 0.80 + 0.02 * np.sin(2.0 * np.pi * t / 5.0)
    y = np.sin(2.0 * np.pi * t / 50.0)
    th = RegimeThresholds(tau=0.80)

    plain = classify_regime(x, period_steps=50, seasonal_driver=y, thresholds=th)
    hyst = classify_regime_hysteresis(
        x,
        period_steps=50,
        lower_tau=0.78,
        upper_tau=0.82,
        seasonal_driver=y,
        thresholds=th,
    )
    assert hyst.switch_count <= plain.switch_count


def test_hysteresis_threshold_order_is_validated():
    x = np.full(100, 0.8)
    with pytest.raises(ValueError):
        classify_regime_hysteresis(x, period_steps=50, lower_tau=0.85, upper_tau=0.80)
