#!/usr/bin/env python3
"""Prepare Phase 4 analysis tables from run artifacts."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _parse_kv(text: str | None) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not text:
        return out
    for token in text.split(";"):
        token = token.strip()
        if not token or "=" not in token:
            continue
        k, v = token.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _manifest_by_basename(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for r in rows:
        base = Path(r["config_path"]).name
        out[base] = r
    return out


def _canonical_config_basename(path_str: str) -> str:
    base = Path(path_str).name
    if base.endswith("_smoke.yaml"):
        return base.replace("_smoke.yaml", ".yaml")
    return base


def _full_grid_suffix_block(rows: List[Dict[str, str]], target_basenames: set[str]) -> List[Dict[str, str]]:
    if not rows:
        return []
    seen: set[str] = set()
    start_idx = None
    for i in range(len(rows) - 1, -1, -1):
        base = rows[i]["config_basename"]
        if base in target_basenames:
            seen.add(base)
        if seen == target_basenames:
            start_idx = i
            break
    if start_idx is None:
        return []
    return rows[start_idx:]


def _latest_per_config(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    latest: Dict[str, Dict[str, str]] = {}
    for r in rows:
        base = r["config_basename"]
        if base not in latest or r["end_time"] > latest[base]["end_time"]:
            latest[base] = r
    return sorted(latest.values(), key=lambda r: r["config_basename"])


def _fmt(x: float) -> str:
    return f"{x:.6f}"


def _summarize_graph_windows(rows: List[Dict[str, str]]) -> Dict[str, str]:
    def arr(key: str) -> np.ndarray:
        return np.asarray([float(r[key]) for r in rows if r.get(key, "") != ""], dtype=float)

    density = arr("density")
    clustering = arr("clustering_mean")
    tree_excess = arr("tree_excess_ratio")
    branching = arr("branching_skew")
    hyper = arr("delta_hyperbolicity_proxy")
    frac_hier = arr("frac_hier_mean")

    return {
        "n_graph_windows": str(len(rows)),
        "density_mean": _fmt(float(np.mean(density))) if density.size else "",
        "density_std": _fmt(float(np.std(density))) if density.size else "",
        "clustering_mean": _fmt(float(np.mean(clustering))) if clustering.size else "",
        "tree_excess_ratio_mean": _fmt(float(np.mean(tree_excess))) if tree_excess.size else "",
        "branching_skew_mean": _fmt(float(np.mean(branching))) if branching.size else "",
        "delta_hyperbolicity_proxy_mean": _fmt(float(np.mean(hyper))) if hyper.size else "",
        "frac_hier_mean_of_windows": _fmt(float(np.mean(frac_hier))) if frac_hier.size else "",
        "frac_hier_std_of_windows": _fmt(float(np.std(frac_hier))) if frac_hier.size else "",
        "regime_hint_mode": max(
            {r.get("regime_hint", "") for r in rows},
            key=lambda label: sum(1 for rr in rows if rr.get("regime_hint", "") == label),
        ) if rows else "",
    }


def _join(
    *,
    run_rows: List[Dict[str, str]],
    manifest_by_base: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for run in run_rows:
        if run.get("status") != "SUCCESS":
            continue

        config_base = _canonical_config_basename(run["config_path"])
        manifest = manifest_by_base.get(config_base)
        if manifest is None:
            continue

        run_dir = Path(run["run_dir"])
        graph_windows_path = run_dir / "graph_windows.csv"
        if not graph_windows_path.exists():
            continue
        graph_rows = _read_csv(graph_windows_path)
        if not graph_rows:
            continue

        summary = _summarize_graph_windows(graph_rows)
        kv = {}
        kv.update(_parse_kv(manifest.get("sweep_value")))
        kv.update(_parse_kv(manifest.get("notes")))

        out.append(
            {
                "run_id": run["run_id"],
                "config_path": run["config_path"],
                "config_basename": config_base,
                "seed": run["seed"],
                "start_time": run["start_time"],
                "end_time": run["end_time"],
                "status": run["status"],
                "retry_count": run["retry_count"],
                "git_commit": run["git_commit"],
                "schema_version": run["schema_version"],
                "run_dir": run["run_dir"],
                "graph_windows_path": str(graph_windows_path),
                "graph_edges_path": str(run_dir / "graph_edges.csv"),
                "graph_schema_version_path": str(run_dir / "graph_schema_version.txt"),
                **summary,
                "sweep_axis": manifest.get("sweep_axis", ""),
                "sweep_value": manifest.get("sweep_value", ""),
                "hypothesis": manifest.get("hypothesis", ""),
                "stage": manifest.get("stage", ""),
                "manifest_seed": manifest.get("seed", ""),
                "manifest_notes": manifest.get("notes", ""),
                "source_profile": kv.get("source_profile", ""),
                "graph_mode": kv.get("graph_mode", ""),
                "window_periods": kv.get("window_periods", ""),
            }
        )
    out.sort(key=lambda r: r["start_time"])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Phase 4 analysis tables")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase4",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase4" / "manifest_stage1_exploration.csv",
    )
    parser.add_argument(
        "--latest-output",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase4" / "analysis_latest_per_config.csv",
    )
    parser.add_argument(
        "--block-output",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase4" / "analysis_full_grid_block.csv",
    )
    args = parser.parse_args()

    run_rows = _read_csv(args.run_root / "run_index.csv")
    manifest_rows = _read_csv(args.manifest)
    manifest_by_base = _manifest_by_basename(manifest_rows)

    joined = _join(run_rows=run_rows, manifest_by_base=manifest_by_base)
    latest_rows = _latest_per_config(joined)
    full_block_rows = _full_grid_suffix_block(joined, set(manifest_by_base.keys()))

    fieldnames = [
        "run_id",
        "config_path",
        "config_basename",
        "seed",
        "start_time",
        "end_time",
        "status",
        "retry_count",
        "git_commit",
        "schema_version",
        "run_dir",
        "graph_windows_path",
        "graph_edges_path",
        "graph_schema_version_path",
        "n_graph_windows",
        "density_mean",
        "density_std",
        "clustering_mean",
        "tree_excess_ratio_mean",
        "branching_skew_mean",
        "delta_hyperbolicity_proxy_mean",
        "frac_hier_mean_of_windows",
        "frac_hier_std_of_windows",
        "regime_hint_mode",
        "sweep_axis",
        "sweep_value",
        "hypothesis",
        "stage",
        "manifest_seed",
        "manifest_notes",
        "source_profile",
        "graph_mode",
        "window_periods",
    ]

    _write_csv(args.latest_output, latest_rows, fieldnames)
    _write_csv(args.block_output, full_block_rows, fieldnames)

    print(f"joined: rows={len(joined)}")
    print(f"latest_per_config: rows={len(latest_rows)}")
    print(f"full_grid_block: rows={len(full_block_rows)}")


if __name__ == "__main__":
    main()
