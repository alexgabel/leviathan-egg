#!/usr/bin/env python3
"""Render first Phase 4 structure-vs-hierarchy figures from analysis tables."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _f(row: Dict[str, str], key: str) -> float:
    return float(row[key]) if row.get(key, "") != "" else float("nan")


def _group_mean(rows: List[Dict[str, str]], key: str) -> float:
    vals = np.asarray([_f(r, key) for r in rows], dtype=float)
    vals = vals[~np.isnan(vals)]
    return float(np.mean(vals)) if vals.size else float("nan")


def _group_std(rows: List[Dict[str, str]], key: str) -> float:
    vals = np.asarray([_f(r, key) for r in rows], dtype=float)
    vals = vals[~np.isnan(vals)]
    return float(np.std(vals)) if vals.size else float("nan")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot first Phase 4 structure-vs-hierarchy figures")
    parser.add_argument("--analysis-csv", type=Path, required=True)
    parser.add_argument("--summary-csv", type=Path, required=True)
    parser.add_argument("--scatter-out", type=Path, required=True)
    parser.add_argument("--profile-bars-out", type=Path, required=True)
    args = parser.parse_args()

    rows = _read_csv(args.analysis_csv)
    if not rows:
        raise SystemExit("No rows found in analysis CSV")

    summary_rows: List[Dict[str, str]] = []
    by_profile: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        by_profile.setdefault(row.get("source_profile", ""), []).append(row)

    for profile, group in sorted(by_profile.items()):
        summary_rows.append(
            {
                "source_profile": profile,
                "n_configs": str(len(group)),
                "frac_hier_mean_of_windows_mean": f"{_group_mean(group, 'frac_hier_mean_of_windows'):.6f}",
                "tree_excess_ratio_mean": f"{_group_mean(group, 'tree_excess_ratio_mean'):.6f}",
                "branching_skew_mean": f"{_group_mean(group, 'branching_skew_mean'):.6f}",
                "delta_hyperbolicity_proxy_mean": f"{_group_mean(group, 'delta_hyperbolicity_proxy_mean'):.6f}",
                "density_mean": f"{_group_mean(group, 'density_mean'):.6f}",
                "clustering_mean": f"{_group_mean(group, 'clustering_mean'):.6f}",
            }
        )

    _write_csv(
        args.summary_csv,
        summary_rows,
        [
            "source_profile",
            "n_configs",
            "frac_hier_mean_of_windows_mean",
            "tree_excess_ratio_mean",
            "branching_skew_mean",
            "delta_hyperbolicity_proxy_mean",
            "density_mean",
            "clustering_mean",
        ],
    )

    plt.style.use("ggplot")

    # Scatter plane
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    profile_colors = {
        "hierarchical_lock": "#c44e52",
        "reversal": "#4c72b0",
        "low_hierarchy": "#55a868",
    }
    mode_markers = {
        "undirected_contact": "o",
        "directed_influence": "s",
    }
    for row in rows:
        profile = row.get("source_profile", "")
        mode = row.get("graph_mode", "")
        color = profile_colors.get(profile, "#444444")
        marker = mode_markers.get(mode, "o")
        axes[0].scatter(
            _f(row, "frac_hier_mean_of_windows"),
            _f(row, "tree_excess_ratio_mean"),
            color=color,
            marker=marker,
            s=80,
            alpha=0.85,
        )
        axes[1].scatter(
            _f(row, "frac_hier_mean_of_windows"),
            _f(row, "branching_skew_mean"),
            color=color,
            marker=marker,
            s=80,
            alpha=0.85,
        )

    axes[0].set_title("Hierarchy vs tree excess")
    axes[0].set_xlabel("mean frac_hier across graph windows")
    axes[0].set_ylabel("mean tree_excess_ratio")
    axes[1].set_title("Hierarchy vs branching skew")
    axes[1].set_xlabel("mean frac_hier across graph windows")
    axes[1].set_ylabel("mean branching_skew")
    fig.suptitle("Phase 4 Stage 1: first structure-vs-hierarchy views")
    fig.tight_layout()
    args.scatter_out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.scatter_out, dpi=160)
    plt.close(fig)

    # Profile bars
    profiles = [r["source_profile"] for r in summary_rows]
    frac = np.asarray([float(r["frac_hier_mean_of_windows_mean"]) for r in summary_rows], dtype=float)
    tree = np.asarray([float(r["tree_excess_ratio_mean"]) for r in summary_rows], dtype=float)
    branch = np.asarray([float(r["branching_skew_mean"]) for r in summary_rows], dtype=float)
    hyper = np.asarray([float(r["delta_hyperbolicity_proxy_mean"]) for r in summary_rows], dtype=float)

    x = np.arange(len(profiles))
    width = 0.2
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(x - width / 2, frac, width=width, label="frac_hier", color="#4c72b0")
    axes[0].bar(x + width / 2, tree, width=width, label="tree_excess", color="#c44e52")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(profiles, rotation=15)
    axes[0].set_title("Hierarchy intensity vs tree excess")
    axes[0].legend()

    axes[1].bar(x - width / 2, branch, width=width, label="branching_skew", color="#8172b2")
    axes[1].bar(x + width / 2, hyper, width=width, label="hyperbolicity_proxy", color="#55a868")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(profiles, rotation=15)
    axes[1].set_title("Structural signature summary by source profile")
    axes[1].legend()

    fig.suptitle("Phase 4 Stage 1: profile-level structural summaries")
    fig.tight_layout()
    args.profile_bars_out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.profile_bars_out, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
