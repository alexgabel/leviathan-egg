from __future__ import annotations

import yaml

from leviathan_egg.config import load_config
from leviathan_egg.metrics import (
    PHASE3_SYNCHRONY_PLACEHOLDER_KEYS,
    collect_metrics,
    collect_phase3_scaffolding_metrics,
)
from leviathan_egg.seasons import seasonal_terms
from leviathan_egg.world import World


def _base_config(num_patches: int = 1) -> dict:
    phase_offsets = {f"patch_{i}": round(0.2 * i, 3) for i in range(num_patches)}
    return {
        "schema_version": "1.0",
        "experiment_name": "phase3_metrics_schema_test",
        "description": "metrics schema test fixture",
        "author": "tests",
        "date_created": "2026-02-09",
        "world_structure": {
            "num_patches": num_patches,
            "population_sizes": {"agents": 32},
            "environmental_parameters": {},
        },
        "seasonality": {
            "seasonal_period": 40,
            "phase_offsets": phase_offsets,
            "forcing_amplitudes": {
                "aggregation_benefit": 0.8,
                "coordination_cost": 0.4,
                "hierarchy_rent": 0.5,
                "crisis": 0.3,
                "festival": 0.5,
            },
            "forcing_sign": {"authority_coupling": 1},
        },
        "authority_and_power": {
            "violence_factor": 0.2,
            "information_spread_rate": 0.2,
            "charisma_levels": {"agents": 1.0},
            "authority_threshold": 1.0,
            "authority_steepness": 3.0,
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
            "total_steps": 120,
            "burn_in_period": 20,
            "random_seed": 19,
            "logging_frequency": 1,
        },
        "observation": {
            "metrics_to_log": [
                "frac_hier",
                "num_groups",
                "mean_group_size",
                "max_group_size",
                "gini_prestige",
            ],
            "aggregation_windows": [40],
        },
    }


def _write_yaml(path, obj) -> None:
    path.write_text(yaml.safe_dump(obj, sort_keys=False), encoding="utf-8")


def test_single_patch_collect_metrics_schema_is_stable(tmp_path):
    cfg_dict = _base_config(num_patches=1)
    path = tmp_path / "single_patch.yaml"
    _write_yaml(path, cfg_dict)
    cfg = load_config(path)
    world = World(cfg)
    world.step(0)

    season = seasonal_terms(0, cfg, patch_id=0)
    metrics = collect_metrics(world, season=season)

    assert list(metrics.keys()) == [
        "frac_hier",
        "num_groups",
        "mean_group_size",
        "max_group_size",
        "gini_prestige",
        "festival",
        "crisis",
    ]


def test_multipatch_scaffolding_metrics_opt_in(tmp_path):
    cfg_dict = _base_config(num_patches=3)
    path = tmp_path / "multipatch.yaml"
    _write_yaml(path, cfg_dict)
    cfg = load_config(path)
    world = World(cfg)
    world.step(0)

    season = seasonal_terms(0, cfg, patch_id=0)
    base_metrics = collect_metrics(world, season=season)
    assert "frac_hier_patch_0" not in base_metrics
    assert "synchrony_order_parameter" not in base_metrics

    phase3_metrics = collect_phase3_scaffolding_metrics(world)
    assert set(phase3_metrics.keys()) == {
        "frac_hier_patch_0",
        "frac_hier_patch_1",
        "frac_hier_patch_2",
        *PHASE3_SYNCHRONY_PLACEHOLDER_KEYS,
    }

    merged = collect_metrics(
        world,
        season=season,
        include_phase3_scaffolding=True,
    )
    assert "frac_hier_patch_0" in merged
    assert "frac_hier_patch_1" in merged
    assert "frac_hier_patch_2" in merged
    for key in PHASE3_SYNCHRONY_PLACEHOLDER_KEYS:
        assert key in merged
