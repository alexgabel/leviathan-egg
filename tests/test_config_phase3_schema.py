from __future__ import annotations

import pytest
import yaml

from leviathan_egg.config import ConfigError, load_config


def _base_config() -> dict:
    return {
        "schema_version": "1.0",
        "experiment_name": "phase3_schema_test",
        "description": "config schema test fixture",
        "author": "tests",
        "date_created": "2026-02-09",
        "world_structure": {
            "num_patches": 1,
            "population_sizes": {"agents": 64},
            "environmental_parameters": {},
        },
        "seasonality": {
            "seasonal_period": 40,
            "phase_offsets": {"patch_0": 0.0},
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
            "total_steps": 180,
            "burn_in_period": 20,
            "random_seed": 7,
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
            "aggregation_windows": [40],
        },
    }


def _write_yaml(path, obj) -> None:
    path.write_text(yaml.safe_dump(obj, sort_keys=False), encoding="utf-8")


def test_phase1_config_gets_disabled_coupling_defaults():
    cfg = load_config("experiments/configs/phase1_reversal.yaml")
    assert cfg.inter_patch_coupling.enabled is False
    assert cfg.inter_patch_coupling.mode == "none"
    assert cfg.inter_patch_coupling.strength == 0.0
    assert cfg.inter_patch_coupling.target_metric == "frac_hier"
    assert "inter_patch_coupling" in cfg.to_resolved_dict()


def test_phase3_explicit_coupling_schema_parses(tmp_path):
    config = _base_config()
    config["world_structure"]["num_patches"] = 3
    config["seasonality"]["phase_offsets"] = {
        "patch_0": 0.0,
        "patch_1": 0.25,
        "patch_2": 0.50,
    }
    config["inter_patch_coupling"] = {
        "enabled": True,
        "mode": "mean_field",
        "topology": "ring",
        "strength": 0.35,
        "sign": 1,
        "lag_steps": 2,
        "normalize_by_degree": True,
        "target_metric": "frac_hier",
    }

    path = tmp_path / "phase3_valid.yaml"
    _write_yaml(path, config)
    cfg = load_config(path)

    assert cfg.inter_patch_coupling.enabled is True
    assert cfg.inter_patch_coupling.mode == "mean_field"
    assert cfg.inter_patch_coupling.topology == "ring"
    assert cfg.inter_patch_coupling.strength == pytest.approx(0.35)
    assert cfg.inter_patch_coupling.sign == 1
    assert cfg.inter_patch_coupling.lag_steps == 2


def test_enabled_coupling_requires_multi_patch(tmp_path):
    config = _base_config()
    config["inter_patch_coupling"] = {
        "enabled": True,
        "mode": "mean_field",
        "topology": "all_to_all",
        "strength": 0.2,
        "sign": 1,
        "lag_steps": 0,
        "normalize_by_degree": True,
        "target_metric": "frac_hier",
    }
    path = tmp_path / "invalid_single_patch_coupling.yaml"
    _write_yaml(path, config)

    with pytest.raises(
        ConfigError, match=r"enabled=true requires world_structure.num_patches >= 2"
    ):
        load_config(path)


def test_missing_phase_offset_for_declared_patch_fails(tmp_path):
    config = _base_config()
    config["world_structure"]["num_patches"] = 2
    config["seasonality"]["phase_offsets"] = {"patch_0": 0.0}
    path = tmp_path / "invalid_missing_offset.yaml"
    _write_yaml(path, config)

    with pytest.raises(ConfigError, match=r"Missing required seasonality.phase_offsets"):
        load_config(path)

