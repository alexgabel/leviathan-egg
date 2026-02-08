import csv

import pytest
import yaml

from leviathan_egg.cli import run_simulation


def _write_config(path, *, agents: int):
    cfg = {
        "schema_version": "1.0",
        "experiment_name": "test_artifacts",
        "description": "artifact contract run",
        "author": "tests",
        "date_created": "2026-02-08",
        "world_structure": {
            "num_patches": 1,
            "population_sizes": {"agents": agents},
            "environmental_parameters": {},
        },
        "seasonality": {
            "seasonal_period": 40,
            "phase_offsets": {"patch_0": 0.0},
            "forcing_amplitudes": {
                "aggregation_benefit": 0.5,
                "coordination_cost": 0.5,
                "hierarchy_rent": 0.5,
                "crisis": 0.3,
                "festival": 0.4,
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
            "total_steps": 80,
            "burn_in_period": 10,
            "random_seed": 11,
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
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def test_success_run_writes_contract_and_run_index(tmp_path):
    config_path = tmp_path / "cfg_ok.yaml"
    _write_config(config_path, agents=24)

    run_root = tmp_path / "phase2"
    run_dir = run_simulation(config_path, run_root=run_root, max_retries=0)

    for file_name in ("metrics.csv", "config_resolved.yaml", "seed.txt", "git_commit.txt"):
        assert (run_dir / file_name).exists()

    index_path = run_root / "run_index.csv"
    assert index_path.exists()

    with index_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["status"] == "SUCCESS"
    assert rows[0]["schema_version"] == "1.0"


def test_failed_run_writes_failed_marker_and_index(tmp_path):
    config_path = tmp_path / "cfg_bad.yaml"
    _write_config(config_path, agents=0)

    run_root = tmp_path / "phase2"
    with pytest.raises(RuntimeError):
        run_simulation(config_path, run_root=run_root, max_retries=0)

    run_dirs = [p for p in run_root.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    failed_file = run_dirs[0] / "FAILED.txt"
    assert failed_file.exists()

    with (run_root / "run_index.csv").open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["status"] == "FAILED"
