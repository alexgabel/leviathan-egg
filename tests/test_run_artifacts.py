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
    assert rows[0]["metrics_path"] == str(run_dir / "metrics.csv")
    assert rows[0]["config_resolved_path"] == str(run_dir / "config_resolved.yaml")
    assert rows[0]["seed_path"] == str(run_dir / "seed.txt")
    assert rows[0]["git_commit_path"] == str(run_dir / "git_commit.txt")
    assert rows[0]["failed_marker_path"] == ""
    assert "metrics:" in rows[0]["artifact_paths"]
    assert "failed_marker:" not in rows[0]["artifact_paths"]


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
    assert rows[0]["failed_marker_path"] == str(failed_file)
    assert "failed_marker:" in rows[0]["artifact_paths"]


def test_run_index_schema_migrates_forward(tmp_path):
    run_root = tmp_path / "phase2"
    run_root.mkdir(parents=True, exist_ok=True)
    index_path = run_root / "run_index.csv"
    old_fields = [
        "run_id",
        "config_path",
        "seed",
        "status",
        "retry_count",
        "start_time",
        "end_time",
        "git_commit",
        "schema_version",
        "run_dir",
        "error",
    ]
    with index_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=old_fields)
        writer.writeheader()
        writer.writerow(
            {
                "run_id": "legacy_row",
                "config_path": "legacy.yaml",
                "seed": "1",
                "status": "SUCCESS",
                "retry_count": "0",
                "start_time": "2026-01-01T00:00:00Z",
                "end_time": "2026-01-01T00:01:00Z",
                "git_commit": "abc",
                "schema_version": "1.0",
                "run_dir": "legacy",
                "error": "",
            }
        )

    config_path = tmp_path / "cfg_ok.yaml"
    _write_config(config_path, agents=24)
    run_simulation(config_path, run_root=run_root, max_retries=0)

    with index_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    assert len(rows) == 2
    assert "metrics_path" in fieldnames
    assert "config_resolved_path" in fieldnames
    assert "artifact_paths" in fieldnames
    assert rows[0]["run_id"] == "legacy_row"
    assert rows[0]["metrics_path"] == "legacy/metrics.csv"
    assert rows[0]["failed_marker_path"] == ""
