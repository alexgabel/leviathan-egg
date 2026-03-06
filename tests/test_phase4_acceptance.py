from __future__ import annotations

import csv
from pathlib import Path

import yaml

from leviathan_egg.cli import run_simulation
from leviathan_egg.config import load_config
from leviathan_egg.phase4_graphs import (
    GRAPH_EDGE_FIELDS,
    GRAPH_WINDOW_FIELDS,
    Phase4WindowCollector,
    compute_graph_metrics,
)
from leviathan_egg.world import World


def _base_cfg_dict(
    *,
    experiment_name: str,
    authority_threshold: float,
    seed: int,
) -> dict:
    return {
        "schema_version": "1.0",
        "experiment_name": experiment_name,
        "description": "phase4 acceptance fixture",
        "author": "tests",
        "date_created": "2026-03-06",
        "world_structure": {
            "num_patches": 1,
            "population_sizes": {"agents": 18},
            "environmental_parameters": {},
        },
        "seasonality": {
            "seasonal_period": 20,
            "phase_offsets": {"patch_0": 0.0},
            "forcing_amplitudes": {
                "aggregation_benefit": 1.2,
                "coordination_cost": 0.7,
                "hierarchy_rent": 0.8,
                "crisis": 0.6,
                "festival": 0.5,
            },
            "forcing_sign": {"authority_coupling": 1},
        },
        "authority_and_power": {
            "violence_factor": 0.1,
            "information_spread_rate": 0.1,
            "charisma_levels": {"agents": 1.0},
            "authority_threshold": authority_threshold,
            "authority_steepness": 5.0,
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
            "prestige_noise": 0.01,
        },
        "runtime_and_reproducibility": {
            "total_steps": 70,
            "burn_in_period": 10,
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
            ],
            "aggregation_windows": [20],
        },
        "graph_extraction": {
            "enabled": True,
            "graph_mode": "directed_influence",
            "window_periods": 1,
            "emit_edge_list": True,
            "emit_window_metrics": True,
            "pool_patches": False,
        },
        "structural_metrics": {
            "metrics_to_compute": [
                "density",
                "clustering_mean",
                "tree_excess_ratio",
                "branching_skew",
                "delta_hyperbolicity_proxy",
            ],
            "hyperbolicity_proxy_mode": "tree_likeness",
        },
    }


def _write_cfg(path: Path, cfg: dict) -> None:
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def _collect_graph_rows(config_path: Path) -> list[dict[str, object]]:
    cfg = load_config(config_path)
    world = World(cfg)
    collector = Phase4WindowCollector(cfg)
    burn_in = cfg.runtime_and_reproducibility.burn_in_period
    total_steps = cfg.runtime_and_reproducibility.total_steps
    for t in range(total_steps):
        world.step(t)
        if t >= burn_in:
            collector.observe(world, t=t)
    rows, _ = collector.finalize(
        run_id="fixed_run",
        config_path=str(config_path),
        seed=cfg.runtime_and_reproducibility.random_seed,
        git_commit="fixed_commit",
        schema_version=cfg.schema_version,
    )
    return rows


def test_phase4_graph_extraction_deterministic(tmp_path):
    cfg_path = tmp_path / "phase4_deterministic.yaml"
    _write_cfg(
        cfg_path,
        _base_cfg_dict(
            experiment_name="phase4_deterministic",
            authority_threshold=0.8,
            seed=101,
        ),
    )

    rows_a = _collect_graph_rows(cfg_path)
    rows_b = _collect_graph_rows(cfg_path)

    assert rows_a == rows_b
    assert rows_a


def test_phase4_metrics_stable_on_synthetic_graphs():
    clique_edges = {(0, 1): 1.0, (0, 2): 1.0, (0, 3): 1.0, (1, 2): 1.0, (1, 3): 1.0, (2, 3): 1.0}
    path_edges = {(0, 1): 1.0, (1, 2): 1.0, (2, 3): 1.0}
    star_edges = {(0, 1): 1.0, (0, 2): 1.0, (0, 3): 1.0}

    clique = compute_graph_metrics(n_nodes=4, weighted_edges=clique_edges, directed=False)
    path = compute_graph_metrics(n_nodes=4, weighted_edges=path_edges, directed=False)
    star = compute_graph_metrics(n_nodes=4, weighted_edges=star_edges, directed=False)

    assert clique["density"] > path["density"]
    assert clique["clustering_mean"] > path["clustering_mean"]
    assert path["tree_excess_ratio"] < clique["tree_excess_ratio"]
    assert star["branching_skew"] > path["branching_skew"]


def test_phase4_hierarchical_vs_egalitarian_structural_difference(tmp_path):
    high_path = tmp_path / "phase4_high_hierarchy.yaml"
    low_path = tmp_path / "phase4_low_hierarchy.yaml"

    _write_cfg(
        high_path,
        _base_cfg_dict(
            experiment_name="phase4_high",
            authority_threshold=0.6,
            seed=202,
        ),
    )
    _write_cfg(
        low_path,
        _base_cfg_dict(
            experiment_name="phase4_low",
            authority_threshold=8.0,
            seed=202,
        ),
    )

    high_rows = _collect_graph_rows(high_path)
    low_rows = _collect_graph_rows(low_path)

    high_frac = sum(float(row["frac_hier_mean"]) for row in high_rows) / len(high_rows)
    low_frac = sum(float(row["frac_hier_mean"]) for row in low_rows) / len(low_rows)
    high_branching = sum(float(row["branching_skew"]) for row in high_rows) / len(high_rows)
    low_branching = sum(float(row["branching_skew"]) for row in low_rows) / len(low_rows)

    assert high_frac > low_frac + 0.2
    assert high_branching > low_branching + 0.5


def test_phase4_output_schema_contract(tmp_path):
    cfg_path = tmp_path / "phase4_schema.yaml"
    _write_cfg(
        cfg_path,
        _base_cfg_dict(
            experiment_name="phase4_schema",
            authority_threshold=0.8,
            seed=303,
        ),
    )

    run_root = tmp_path / "runs"
    run_dir = run_simulation(cfg_path, run_root=run_root, max_retries=0)

    graph_windows = run_dir / "graph_windows.csv"
    graph_edges = run_dir / "graph_edges.csv"
    graph_schema = run_dir / "graph_schema_version.txt"
    run_index = run_root / "run_index.csv"

    assert graph_windows.exists()
    assert graph_edges.exists()
    assert graph_schema.exists()
    assert run_index.exists()

    with graph_windows.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    assert rows
    assert set(GRAPH_WINDOW_FIELDS).issubset(set(fieldnames))

    with graph_edges.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        edge_rows = list(reader)
        edge_fields = reader.fieldnames or []
    assert edge_rows
    assert set(GRAPH_EDGE_FIELDS).issubset(set(edge_fields))

    assert graph_schema.read_text(encoding="utf-8").strip() == "phase4.v1"

    with run_index.open("r", encoding="utf-8") as f:
        index_rows = list(csv.DictReader(f))
    assert len(index_rows) == 1
    artifact_paths = index_rows[0]["artifact_paths"]
    assert "graph_windows:" in artifact_paths
    assert "graph_edges:" in artifact_paths
    assert "graph_schema_version:" in artifact_paths
