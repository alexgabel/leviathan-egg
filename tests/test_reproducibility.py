import yaml

from leviathan_egg.cli import run_simulation


def _write_small_config(path):
    cfg = {
        "schema_version": "1.0",
        "experiment_name": "test_repro",
        "description": "small deterministic run",
        "author": "tests",
        "date_created": "2026-02-08",
        "world_structure": {
            "num_patches": 1,
            "population_sizes": {"agents": 32},
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
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def test_reproducible_metrics_and_metadata(tmp_path):
    config_path = tmp_path / "cfg.yaml"
    _write_small_config(config_path)

    run_root = tmp_path / "runs"
    run1 = run_simulation(config_path, run_root=run_root, max_retries=0)
    run2 = run_simulation(config_path, run_root=run_root, max_retries=0)

    metrics1 = (run1 / "metrics.csv").read_text(encoding="utf-8")
    metrics2 = (run2 / "metrics.csv").read_text(encoding="utf-8")
    assert metrics1 == metrics2

    resolved = yaml.safe_load((run1 / "config_resolved.yaml").read_text(encoding="utf-8"))
    assert resolved["schema_version"] == "1.0"

    assert (run1 / "seed.txt").read_text(encoding="utf-8").strip() == "7"
    assert (run1 / "git_commit.txt").read_text(encoding="utf-8").strip() != ""
