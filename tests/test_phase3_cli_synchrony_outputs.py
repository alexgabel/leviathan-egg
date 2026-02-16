from __future__ import annotations

import csv

import yaml

from leviathan_egg.cli import run_simulation


def _write_multi_patch_config(path) -> None:
    cfg = {
        "schema_version": "1.0",
        "experiment_name": "phase3_cli_sync_outputs",
        "description": "verify synchrony outputs in metrics.csv",
        "author": "tests",
        "date_created": "2026-02-09",
        "world_structure": {
            "num_patches": 3,
            "population_sizes": {"agents": 24},
            "environmental_parameters": {},
        },
        "seasonality": {
            "seasonal_period": 40,
            "phase_offsets": {
                "patch_0": 0.0,
                "patch_1": 0.2,
                "patch_2": 0.4,
            },
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
            "total_steps": 60,
            "burn_in_period": 10,
            "random_seed": 99,
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
        "inter_patch_coupling": {
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
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def test_run_emits_synchrony_outputs_for_multi_patch(tmp_path):
    config_path = tmp_path / "phase3_multi_patch.yaml"
    _write_multi_patch_config(config_path)

    run_root = tmp_path / "runs"
    run_dir = run_simulation(config_path, run_root=run_root, max_retries=0)
    metrics_path = run_dir / "metrics.csv"

    with metrics_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    assert rows
    expected_fields = {
        "frac_hier_patch_0",
        "frac_hier_patch_1",
        "frac_hier_patch_2",
        "synchrony_order_parameter",
        "synchrony_phase_lock_fraction",
        "synchrony_mean_abs_phase_lag",
        "synchrony_antiphase_fraction",
    }
    assert expected_fields.issubset(set(fieldnames))
