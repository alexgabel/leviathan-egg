from __future__ import annotations

import yaml

from leviathan_egg.config import load_config
from leviathan_egg.world import World


def _base_config(num_patches: int = 2) -> dict:
    return {
        "schema_version": "1.0",
        "experiment_name": "phase3_world_scaffold_test",
        "description": "world multipatch scaffold fixture",
        "author": "tests",
        "date_created": "2026-02-09",
        "world_structure": {
            "num_patches": num_patches,
            "population_sizes": {"agents": 32},
            "environmental_parameters": {},
        },
        "seasonality": {
            "seasonal_period": 40,
            "phase_offsets": {"patch_0": 0.0, "patch_1": 0.33},
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
            "random_seed": 17,
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


def _write_config(path, cfg: dict) -> None:
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def test_multipatch_uncoupled_is_deterministic(tmp_path):
    cfg_dict = _base_config()
    config_path = tmp_path / "multipatch_uncoupled.yaml"
    _write_config(config_path, cfg_dict)
    cfg = load_config(config_path)
    assert cfg.inter_patch_coupling.enabled is False

    w1 = World(cfg)
    w2 = World(cfg)
    for t in range(50):
        w1.step(t)
        w2.step(t)
    assert w1.snapshot() == w2.snapshot()


def test_agents_and_groups_remain_patch_consistent(tmp_path):
    cfg_dict = _base_config()
    config_path = tmp_path / "multipatch_consistency.yaml"
    _write_config(config_path, cfg_dict)
    cfg = load_config(config_path)
    w = World(cfg)

    for t in range(30):
        w.step(t)

    for aid, agent in w.agents.items():
        gid = agent.group_id
        assert gid in w.groups
        assert w.groups[gid].patch_id == agent.patch_id
        assert aid in w.patches[agent.patch_id].agent_ids

    for patch_id, patch in w.patches.items():
        for gid in patch.group_ids:
            assert gid in w.groups
            assert w.groups[gid].patch_id == patch_id


def test_enabled_coupling_executes_with_patch_local_constraints(tmp_path):
    cfg_dict = _base_config()
    cfg_dict["inter_patch_coupling"] = {
        "enabled": True,
        "mode": "mean_field",
        "topology": "all_to_all",
        "strength": 0.2,
        "sign": 1,
        "lag_steps": 0,
        "normalize_by_degree": True,
        "target_metric": "frac_hier",
    }
    config_path = tmp_path / "multipatch_coupled.yaml"
    _write_config(config_path, cfg_dict)
    cfg = load_config(config_path)
    w = World(cfg)
    for t in range(20):
        w.step(t)
        assert all(abs(v) <= 0.25 for v in w.last_coupling_bias_by_patch.values())

    for aid, agent in w.agents.items():
        gid = agent.group_id
        assert w.groups[gid].patch_id == agent.patch_id
