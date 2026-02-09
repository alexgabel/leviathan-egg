from __future__ import annotations

import copy

import numpy as np
import yaml

from leviathan_egg.config import load_config
from leviathan_egg.metrics import (
    PHASE3_SYNCHRONY_PLACEHOLDER_KEYS,
    collect_metrics,
    frac_hier_by_patch,
)
from leviathan_egg.seasons import seasonal_terms
from leviathan_egg.world import World


def _make_cfg_dict(
    *,
    num_patches: int,
    seed: int = 23,
    coupling: dict | None = None,
) -> dict:
    return {
        "schema_version": "1.0",
        "experiment_name": "phase3_acceptance",
        "description": "phase3 acceptance fixture",
        "author": "tests",
        "date_created": "2026-02-09",
        "world_structure": {
            "num_patches": num_patches,
            "population_sizes": {"agents": 40},
            "environmental_parameters": {},
        },
        "seasonality": {
            "seasonal_period": 60,
            "phase_offsets": {
                f"patch_{i}": round((i / max(1, num_patches)), 3)
                for i in range(num_patches)
            },
            "forcing_amplitudes": {
                "aggregation_benefit": 1.2,
                "coordination_cost": 0.9,
                "hierarchy_rent": 0.8,
                "crisis": 0.7,
                "festival": 0.6,
            },
            "forcing_sign": {"authority_coupling": 1},
        },
        "authority_and_power": {
            "violence_factor": 0.1,
            "information_spread_rate": 0.1,
            "charisma_levels": {"agents": 1.0},
            "authority_threshold": 3.0,
            "authority_steepness": 4.0,
            "benefit_scale": 2.0,
            "cost_scale": 0.8,
            "cost_exponent": 1.6,
            "rent_scale": 0.4,
            "domination_tax": 0.6,
            "lock_in_effects": True,
            "exit_friction_base": 0.0,
            "exit_friction_from_violence": 1.2,
            "exit_friction_from_information": 1.2,
            "memory_decay": 0.1,
            "prestige_noise": 0.05,
        },
        "runtime_and_reproducibility": {
            "total_steps": 200,
            "burn_in_period": 20,
            "random_seed": seed,
            "logging_frequency": 1,
        },
        "observation": {
            "metrics_to_log": [
                "frac_hier",
                "num_groups",
                "mean_group_size",
                "max_group_size",
                "gini_prestige",
                "festival",
                "crisis",
            ],
            "aggregation_windows": [60],
        },
        "inter_patch_coupling": coupling
        if coupling is not None
        else {
            "enabled": False,
            "mode": "none",
            "topology": "all_to_all",
            "strength": 0.0,
            "sign": 1,
            "lag_steps": 0,
            "normalize_by_degree": True,
            "target_metric": "frac_hier",
        },
    }


def _write_cfg(path, cfg: dict) -> None:
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def _run_patch_series(cfg, *, steps: int = 180) -> np.ndarray:
    world = World(cfg)
    n = cfg.world_structure.num_patches
    out = np.zeros((steps, n), dtype=float)
    for t in range(steps):
        world.step(t)
        by_patch = frac_hier_by_patch(world)
        for p in range(n):
            out[t, p] = by_patch[p]
    return out


def _synchrony_score(series: np.ndarray) -> float:
    """
    1 - mean absolute pairwise patch difference.
    Higher means more synchronized.
    """
    n = series.shape[1]
    if n <= 1:
        return 1.0
    diffs = []
    for i in range(n):
        for j in range(i + 1, n):
            diffs.append(np.abs(series[:, i] - series[:, j]))
    mean_abs_diff = np.mean(np.stack(diffs, axis=0), axis=0)
    return float(np.mean(1.0 - mean_abs_diff))


def test_phase3_single_patch_regression(tmp_path):
    base = _make_cfg_dict(num_patches=1, seed=101, coupling=None)
    no_block = copy.deepcopy(base)
    del no_block["inter_patch_coupling"]

    explicit_disabled = copy.deepcopy(base)

    p_no = tmp_path / "single_no_coupling_block.yaml"
    p_disabled = tmp_path / "single_explicit_disabled.yaml"
    _write_cfg(p_no, no_block)
    _write_cfg(p_disabled, explicit_disabled)

    cfg_no = load_config(p_no)
    cfg_disabled = load_config(p_disabled)

    w_no = World(cfg_no)
    w_disabled = World(cfg_disabled)

    rows_no = []
    rows_disabled = []
    for t in range(80):
        s_no = seasonal_terms(t, cfg_no, patch_id=0)
        s_disabled = seasonal_terms(t, cfg_disabled, patch_id=0)
        w_no.step(t)
        w_disabled.step(t)
        rows_no.append(collect_metrics(w_no, season=s_no))
        rows_disabled.append(collect_metrics(w_disabled, season=s_disabled))

    assert rows_no == rows_disabled
    assert w_no.snapshot() == w_disabled.snapshot()


def test_phase3_uncoupled_independence(tmp_path):
    cfg_dict = _make_cfg_dict(num_patches=4, seed=202, coupling=None)
    path = tmp_path / "uncoupled.yaml"
    _write_cfg(path, cfg_dict)
    cfg = load_config(path)

    series = _run_patch_series(cfg, steps=180)
    tail = series[-100:]

    mean_pairwise_diff = float(np.mean(1.0 - _synchrony_score(tail)))
    assert mean_pairwise_diff > 0.02
    assert not np.array_equal(tail[:, 0], tail[:, 1])


def test_phase3_positive_coupling_directional_effect(tmp_path):
    uncoupled_cfg = _make_cfg_dict(num_patches=4, seed=303, coupling=None)
    coupled_cfg = _make_cfg_dict(
        num_patches=4,
        seed=303,
        coupling={
            "enabled": True,
            "mode": "mean_field",
            "topology": "all_to_all",
            "strength": 1.0,
            "sign": 1,
            "lag_steps": 0,
            "normalize_by_degree": True,
            "target_metric": "frac_hier",
        },
    )

    p_u = tmp_path / "uncoupled_dir.yaml"
    p_c = tmp_path / "coupled_dir.yaml"
    _write_cfg(p_u, uncoupled_cfg)
    _write_cfg(p_c, coupled_cfg)

    cfg_u = load_config(p_u)
    cfg_c = load_config(p_c)
    series_u = _run_patch_series(cfg_u, steps=180)[-100:]
    series_c = _run_patch_series(cfg_c, steps=180)[-100:]

    sync_u = _synchrony_score(series_u)
    sync_c = _synchrony_score(series_c)
    assert sync_c > sync_u + 0.02


def test_phase3_negative_or_weak_coupling_allows_desync(tmp_path):
    positive_cfg = _make_cfg_dict(
        num_patches=4,
        seed=404,
        coupling={
            "enabled": True,
            "mode": "mean_field",
            "topology": "all_to_all",
            "strength": 1.0,
            "sign": 1,
            "lag_steps": 0,
            "normalize_by_degree": True,
            "target_metric": "frac_hier",
        },
    )
    negative_cfg = _make_cfg_dict(
        num_patches=4,
        seed=404,
        coupling={
            "enabled": True,
            "mode": "mean_field",
            "topology": "all_to_all",
            "strength": 1.0,
            "sign": -1,
            "lag_steps": 0,
            "normalize_by_degree": True,
            "target_metric": "frac_hier",
        },
    )

    p_pos = tmp_path / "pos.yaml"
    p_neg = tmp_path / "neg.yaml"
    _write_cfg(p_pos, positive_cfg)
    _write_cfg(p_neg, negative_cfg)

    cfg_pos = load_config(p_pos)
    cfg_neg = load_config(p_neg)
    sync_pos = _synchrony_score(_run_patch_series(cfg_pos, steps=180)[-100:])
    sync_neg = _synchrony_score(_run_patch_series(cfg_neg, steps=180)[-100:])

    assert sync_neg < sync_pos - 0.02


def test_phase3_reproducible_per_patch_outputs(tmp_path):
    coupled_cfg = _make_cfg_dict(
        num_patches=4,
        seed=505,
        coupling={
            "enabled": True,
            "mode": "pairwise",
            "topology": "ring",
            "strength": 0.55,
            "sign": 1,
            "lag_steps": 2,
            "normalize_by_degree": True,
            "target_metric": "frac_hier",
        },
    )
    p = tmp_path / "repro.yaml"
    _write_cfg(p, coupled_cfg)
    cfg = load_config(p)

    s1 = _run_patch_series(cfg, steps=140)
    s2 = _run_patch_series(cfg, steps=140)
    assert np.array_equal(s1, s2)


def test_phase3_output_schema_contract(tmp_path):
    cfg_dict = _make_cfg_dict(num_patches=3, seed=606, coupling=None)
    p = tmp_path / "schema.yaml"
    _write_cfg(p, cfg_dict)
    cfg = load_config(p)
    world = World(cfg)
    world.step(0)

    season = seasonal_terms(0, cfg, patch_id=0)
    base = collect_metrics(world, season=season)
    assert "frac_hier_patch_0" not in base
    assert "synchrony_order_parameter" not in base

    with_phase3 = collect_metrics(
        world,
        season=season,
        include_phase3_scaffolding=True,
    )
    expected = {
        "frac_hier_patch_0",
        "frac_hier_patch_1",
        "frac_hier_patch_2",
        *PHASE3_SYNCHRONY_PLACEHOLDER_KEYS,
    }
    assert expected.issubset(set(with_phase3.keys()))
