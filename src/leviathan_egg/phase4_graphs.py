from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np

from leviathan_egg.config import Config
from leviathan_egg.metrics import frac_hier_by_patch
from leviathan_egg.world import World


GRAPH_SCHEMA_VERSION = "phase4.v1"

GRAPH_WINDOW_FIELDS = (
    "run_id",
    "config_path",
    "seed",
    "git_commit",
    "schema_version",
    "graph_schema_version",
    "window_id",
    "patch_id",
    "graph_mode",
    "window_periods",
    "t_start",
    "t_end",
    "n_steps",
    "n_nodes",
    "n_edges",
    "is_directed",
    "edge_weight_sum",
    "density",
    "mean_degree",
    "degree_std",
    "degree_gini",
    "largest_component_fraction",
    "clustering_mean",
    "mean_shortest_path_lcc",
    "diameter_lcc",
    "degree_assortativity",
    "tree_excess_ratio",
    "branching_skew",
    "delta_hyperbolicity_proxy",
    "frac_hier_mean",
    "frac_hier_std",
    "frac_hier_min",
    "frac_hier_max",
    "regime_hint",
)

GRAPH_EDGE_FIELDS = (
    "run_id",
    "window_id",
    "patch_id",
    "graph_mode",
    "source",
    "target",
    "weight",
    "is_directed",
)


def _gini(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    values = np.asarray(values, dtype=float)
    min_val = float(values.min())
    if min_val < 0.0:
        values = values - min_val
    mean = float(values.mean())
    if mean <= 1e-12:
        return 0.0
    diff_sum = np.abs(values[:, None] - values[None, :]).sum()
    return float(diff_sum / (2.0 * values.size * values.size * mean))


def _canonical_edge(u: int, v: int, *, directed: bool) -> Tuple[int, int]:
    if directed:
        return (int(u), int(v))
    return (int(min(u, v)), int(max(u, v)))


def snapshot_edges(world: World, *, patch_id: int, graph_mode: str) -> Dict[Tuple[int, int], float]:
    weighted_edges: Dict[Tuple[int, int], float] = defaultdict(float)

    for gid in sorted(world.patches[patch_id].group_ids):
        group = world.groups[gid]
        members = sorted(group.members)
        if graph_mode == "undirected_contact":
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    weighted_edges[_canonical_edge(members[i], members[j], directed=False)] += 1.0
        elif graph_mode == "directed_influence":
            if not group.authority_on or group.leader_id is None:
                continue
            for member_id in members:
                if member_id == group.leader_id:
                    continue
                weighted_edges[(int(group.leader_id), int(member_id))] += 1.0
        else:
            raise ValueError(f"Unsupported graph_mode: {graph_mode}")

    return dict(weighted_edges)


def _build_neighbor_map(
    n_nodes: int,
    edges: Iterable[Tuple[int, int]],
) -> List[set[int]]:
    neighbors = [set() for _ in range(n_nodes)]
    for u, v in edges:
        neighbors[u].add(v)
        neighbors[v].add(u)
    return neighbors


def _connected_components(neighbors: List[set[int]]) -> List[List[int]]:
    seen = set()
    components: List[List[int]] = []
    for node in range(len(neighbors)):
        if node in seen:
            continue
        stack = [node]
        comp = []
        seen.add(node)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in neighbors[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        components.append(comp)
    return components


def _largest_component(neighbors: List[set[int]]) -> List[int]:
    components = _connected_components(neighbors)
    if not components:
        return []
    return max(components, key=len)


def _local_clustering(node: int, neighbors: List[set[int]]) -> float:
    nbrs = list(neighbors[node])
    k = len(nbrs)
    if k < 2:
        return 0.0
    links = 0
    for i in range(k):
        for j in range(i + 1, k):
            if nbrs[j] in neighbors[nbrs[i]]:
                links += 1
    return float((2.0 * links) / (k * (k - 1)))


def _shortest_paths_from(source: int, neighbors: List[set[int]], allowed: set[int]) -> Dict[int, int]:
    distances = {source: 0}
    queue = [source]
    while queue:
        cur = queue.pop(0)
        for nxt in neighbors[cur]:
            if nxt not in allowed or nxt in distances:
                continue
            distances[nxt] = distances[cur] + 1
            queue.append(nxt)
    return distances


def compute_graph_metrics(
    *,
    n_nodes: int,
    weighted_edges: Dict[Tuple[int, int], float],
    directed: bool,
) -> Dict[str, float]:
    if n_nodes < 0:
        raise ValueError("n_nodes must be non-negative")

    if directed:
        directed_edges = list(weighted_edges.keys())
        undirected_edges = list({_canonical_edge(u, v, directed=False) for u, v in directed_edges})
    else:
        directed_edges = list(weighted_edges.keys())
        undirected_edges = directed_edges

    neighbors = _build_neighbor_map(n_nodes, undirected_edges)
    degrees = np.array([len(nbrs) for nbrs in neighbors], dtype=float)
    edge_weight_sum = float(sum(weighted_edges.values()))
    n_edges = len(directed_edges)

    max_edges = n_nodes * max(0, n_nodes - 1)
    if not directed:
        max_edges = max_edges / 2.0
    density = float(n_edges / max_edges) if max_edges > 0 else 0.0

    components = _connected_components(neighbors)
    largest = max((len(c) for c in components), default=0)
    largest_component_fraction = float(largest / n_nodes) if n_nodes > 0 else 0.0

    clustering_values = np.array(
        [_local_clustering(node, neighbors) for node in range(n_nodes)], dtype=float
    )

    lcc = _largest_component(neighbors)
    if len(lcc) >= 2:
        lcc_set = set(lcc)
        pair_distances = []
        diameter = 0
        for node in lcc:
            dists = _shortest_paths_from(node, neighbors, lcc_set)
            for other, dist in dists.items():
                if other > node:
                    pair_distances.append(dist)
                diameter = max(diameter, dist)
        mean_shortest_path_lcc = float(np.mean(pair_distances)) if pair_distances else 0.0
        diameter_lcc = float(diameter)
    else:
        mean_shortest_path_lcc = 0.0
        diameter_lcc = 0.0

    if undirected_edges and np.std(degrees) > 1e-12:
        x = np.array([degrees[u] for u, _ in undirected_edges], dtype=float)
        y = np.array([degrees[v] for _, v in undirected_edges], dtype=float)
        if np.std(x) > 1e-12 and np.std(y) > 1e-12:
            degree_assortativity = float(np.corrcoef(x, y)[0, 1])
        else:
            degree_assortativity = 0.0
    else:
        degree_assortativity = 0.0

    num_components = len(components)
    m_undir = len(undirected_edges)
    tree_excess = max(0, m_undir - n_nodes + num_components)
    tree_excess_ratio = float(tree_excess / max(1, m_undir))

    if directed:
        out_degrees = np.zeros(n_nodes, dtype=float)
        for u, _ in directed_edges:
            out_degrees[u] += 1.0
        degree_for_skew = out_degrees
    else:
        degree_for_skew = degrees
    std = float(np.std(degree_for_skew))
    if std > 1e-12:
        centered = (degree_for_skew - float(np.mean(degree_for_skew))) / std
        branching_skew = float(np.mean(centered**3))
    else:
        branching_skew = 0.0

    clustering_mean = float(np.mean(clustering_values)) if n_nodes > 0 else 0.0
    delta_hyperbolicity_proxy = float(
        max(0.0, 1.0 - min(1.0, clustering_mean + tree_excess_ratio))
    )

    return {
        "n_nodes": float(n_nodes),
        "n_edges": float(n_edges),
        "edge_weight_sum": edge_weight_sum,
        "density": density,
        "mean_degree": float(np.mean(degrees)) if n_nodes > 0 else 0.0,
        "degree_std": float(np.std(degrees)) if n_nodes > 0 else 0.0,
        "degree_gini": _gini(degrees),
        "largest_component_fraction": largest_component_fraction,
        "clustering_mean": clustering_mean,
        "mean_shortest_path_lcc": mean_shortest_path_lcc,
        "diameter_lcc": diameter_lcc,
        "degree_assortativity": degree_assortativity,
        "tree_excess_ratio": tree_excess_ratio,
        "branching_skew": branching_skew,
        "delta_hyperbolicity_proxy": delta_hyperbolicity_proxy,
    }


def _regime_hint(frac_hier_mean: float) -> str:
    if frac_hier_mean >= 0.8:
        return "hierarchical"
    if frac_hier_mean <= 0.2:
        return "egalitarian"
    return "mixed"


@dataclass
class _WindowState:
    t_start: int
    t_end: int
    n_steps: int = 0
    edge_weights_by_patch: Dict[int, Dict[Tuple[int, int], float]] = field(default_factory=dict)
    frac_hier_by_patch: Dict[int, List[float]] = field(default_factory=dict)


class Phase4WindowCollector:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.window_size = int(
            cfg.graph_extraction.window_periods * cfg.seasonality.seasonal_period
        )
        self.window_index = 0
        self.current: _WindowState | None = None
        self.window_rows: List[Dict[str, object]] = []
        self.edge_rows: List[Dict[str, object]] = []

    def _start_window(self, t: int, patch_ids: List[int]) -> None:
        self.current = _WindowState(
            t_start=t,
            t_end=t,
            edge_weights_by_patch={patch_id: {} for patch_id in patch_ids},
            frac_hier_by_patch={patch_id: [] for patch_id in patch_ids},
        )

    def observe(self, world: World, *, t: int) -> None:
        if self.window_size <= 0:
            return

        patch_ids = sorted(world.patches.keys())
        if self.current is None:
            self._start_window(t, patch_ids)

        current = self.current
        assert current is not None
        current.t_end = t
        current.n_steps += 1

        frac_by_patch = frac_hier_by_patch(world)
        for patch_id in patch_ids:
            patch_edges = snapshot_edges(
                world,
                patch_id=patch_id,
                graph_mode=self.cfg.graph_extraction.graph_mode,
            )
            aggregate = current.edge_weights_by_patch.setdefault(patch_id, {})
            for edge, weight in patch_edges.items():
                aggregate[edge] = aggregate.get(edge, 0.0) + float(weight)
            current.frac_hier_by_patch.setdefault(patch_id, []).append(frac_by_patch[patch_id])

        if current.n_steps >= self.window_size:
            self._close_window(world)

    def _close_window(self, world: World) -> None:
        current = self.current
        assert current is not None
        directed = self.cfg.graph_extraction.graph_mode == "directed_influence"
        window_id = f"window_{self.window_index:03d}"

        for patch_id in sorted(current.edge_weights_by_patch.keys()):
            patch = world.patches[patch_id]
            metrics = compute_graph_metrics(
                n_nodes=len(patch.agent_ids),
                weighted_edges=current.edge_weights_by_patch[patch_id],
                directed=directed,
            )
            frac_vals = np.asarray(current.frac_hier_by_patch[patch_id], dtype=float)
            frac_mean = float(np.mean(frac_vals)) if frac_vals.size else 0.0
            self.window_rows.append(
                {
                    "window_id": window_id,
                    "patch_id": patch_id,
                    "graph_mode": self.cfg.graph_extraction.graph_mode,
                    "window_periods": self.cfg.graph_extraction.window_periods,
                    "t_start": current.t_start,
                    "t_end": current.t_end,
                    "n_steps": current.n_steps,
                    "n_nodes": int(metrics["n_nodes"]),
                    "n_edges": int(metrics["n_edges"]),
                    "is_directed": int(directed),
                    "edge_weight_sum": metrics["edge_weight_sum"],
                    "density": metrics["density"],
                    "mean_degree": metrics["mean_degree"],
                    "degree_std": metrics["degree_std"],
                    "degree_gini": metrics["degree_gini"],
                    "largest_component_fraction": metrics["largest_component_fraction"],
                    "clustering_mean": metrics["clustering_mean"],
                    "mean_shortest_path_lcc": metrics["mean_shortest_path_lcc"],
                    "diameter_lcc": metrics["diameter_lcc"],
                    "degree_assortativity": metrics["degree_assortativity"],
                    "tree_excess_ratio": metrics["tree_excess_ratio"],
                    "branching_skew": metrics["branching_skew"],
                    "delta_hyperbolicity_proxy": metrics["delta_hyperbolicity_proxy"],
                    "frac_hier_mean": frac_mean,
                    "frac_hier_std": float(np.std(frac_vals)) if frac_vals.size else 0.0,
                    "frac_hier_min": float(np.min(frac_vals)) if frac_vals.size else 0.0,
                    "frac_hier_max": float(np.max(frac_vals)) if frac_vals.size else 0.0,
                    "regime_hint": _regime_hint(frac_mean),
                }
            )

            for (source, target), weight in sorted(current.edge_weights_by_patch[patch_id].items()):
                self.edge_rows.append(
                    {
                        "window_id": window_id,
                        "patch_id": patch_id,
                        "graph_mode": self.cfg.graph_extraction.graph_mode,
                        "source": source,
                        "target": target,
                        "weight": weight,
                        "is_directed": int(directed),
                    }
                )

        self.window_index += 1
        self.current = None

    def finalize(
        self,
        *,
        run_id: str,
        config_path: str,
        seed: int,
        git_commit: str,
        schema_version: str,
    ) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
        rows = []
        for row in self.window_rows:
            rows.append(
                {
                    "run_id": run_id,
                    "config_path": config_path,
                    "seed": seed,
                    "git_commit": git_commit,
                    "schema_version": schema_version,
                    "graph_schema_version": GRAPH_SCHEMA_VERSION,
                    **row,
                }
            )

        edge_rows = []
        for row in self.edge_rows:
            edge_rows.append(
                {
                    "run_id": run_id,
                    **row,
                }
            )
        return rows, edge_rows


def write_phase4_artifacts(
    run_dir: Path,
    *,
    graph_window_rows: List[Dict[str, object]],
    graph_edge_rows: List[Dict[str, object]],
) -> None:
    graph_windows_path = run_dir / "graph_windows.csv"
    graph_edges_path = run_dir / "graph_edges.csv"
    graph_schema_path = run_dir / "graph_schema_version.txt"

    with graph_windows_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(GRAPH_WINDOW_FIELDS))
        writer.writeheader()
        for row in graph_window_rows:
            writer.writerow(row)

    with graph_edges_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(GRAPH_EDGE_FIELDS))
        writer.writeheader()
        for row in graph_edge_rows:
            writer.writerow(row)

    graph_schema_path.write_text(GRAPH_SCHEMA_VERSION + "\n", encoding="utf-8")
