#!/usr/bin/env python3
"""Generate Stage-2 Phase 2 plots from probability/uncertainty CSV inputs.

Outputs:
- fig_stage2_probability_heatmap.png
- fig_stage2_entropy_discord_overlay.png
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _boundary_sort_key(boundary_id: str) -> tuple[int, str]:
    try:
        if boundary_id.startswith("b"):
            return (int(boundary_id[1:]), boundary_id)
    except ValueError:
        pass
    return (10_000, boundary_id)


def _numeric_edges(centers: List[float]) -> np.ndarray:
    if len(centers) == 1:
        c = centers[0]
        return np.array([c - 0.5, c + 0.5], dtype=float)

    c = np.array(centers, dtype=float)
    mids = (c[:-1] + c[1:]) / 2.0
    left = c[0] - (mids[0] - c[0])
    right = c[-1] + (c[-1] - mids[-1])
    return np.concatenate([[left], mids, [right]])


def _build_matrix(
    rows: List[Dict[str, str]],
    *,
    value_key: str,
    boundary_ids: List[str],
    alphas: List[float],
) -> np.ndarray:
    matrix = np.full((len(boundary_ids), len(alphas)), np.nan, dtype=float)
    b_idx = {b: i for i, b in enumerate(boundary_ids)}
    a_idx = {a: i for i, a in enumerate(alphas)}

    for row in rows:
        b = row.get("boundary_id", "")
        a_raw = row.get("alpha", "")
        if not b or not a_raw:
            continue
        try:
            a = float(a_raw)
            value = float(row.get(value_key, "nan"))
        except ValueError:
            continue
        if b in b_idx and a in a_idx:
            matrix[b_idx[b], a_idx[a]] = value
    return matrix


def _set_axes(ax: plt.Axes, *, alphas: List[float], boundary_ids: List[str], title: str) -> None:
    ax.set_title(title)
    ax.set_xlabel("Interpolation alpha")
    ax.set_ylabel("Boundary ID")
    ax.set_xticks(alphas)
    ax.set_yticks(np.arange(len(boundary_ids)) + 0.5)
    ax.set_yticklabels(boundary_ids)
    ax.set_xlim(_numeric_edges(alphas)[0], _numeric_edges(alphas)[-1])
    ax.set_ylim(len(boundary_ids), 0)


def _plot_probability_heatmap(
    *,
    p_reversal: np.ndarray,
    alphas: List[float],
    boundary_ids: List[str],
    out_path: Path,
    dpi: int,
) -> None:
    x_edges = _numeric_edges(alphas)
    y_edges = np.arange(len(boundary_ids) + 1, dtype=float)

    fig, ax = plt.subplots(figsize=(9.5, 4.8), constrained_layout=True)
    mesh = ax.pcolormesh(
        x_edges,
        y_edges,
        p_reversal,
        cmap="viridis",
        vmin=0.0,
        vmax=1.0,
        shading="flat",
    )
    _set_axes(
        ax,
        alphas=alphas,
        boundary_ids=boundary_ids,
        title="Phase 2 Stage-2 Reversal Probability Map (tau=0.8 profile)",
    )
    cb = fig.colorbar(mesh, ax=ax)
    cb.set_label("P(reversal) across replicates")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)


def _plot_entropy_discord_overlay(
    *,
    p_reversal: np.ndarray,
    entropy: np.ndarray,
    discord: np.ndarray,
    alphas: List[float],
    boundary_ids: List[str],
    out_path: Path,
    dpi: int,
) -> None:
    x_edges = _numeric_edges(alphas)
    y_edges = np.arange(len(boundary_ids) + 1, dtype=float)

    fig, ax = plt.subplots(figsize=(9.5, 4.8), constrained_layout=True)
    base = ax.pcolormesh(
        x_edges,
        y_edges,
        p_reversal,
        cmap="viridis",
        vmin=0.0,
        vmax=1.0,
        shading="flat",
    )

    centers_x = np.array(alphas, dtype=float)
    centers_y = np.arange(len(boundary_ids), dtype=float) + 0.5
    grid_x, grid_y = np.meshgrid(centers_x, centers_y)

    if np.nanmax(entropy) > 0:
        levels = [0.1, 0.25, 0.5, 0.75]
        cs = ax.contour(
            grid_x,
            grid_y,
            entropy,
            levels=levels,
            colors="white",
            linewidths=1.1,
        )
        ax.clabel(cs, inline=True, fmt=lambda x: f"H={x:.2f}", fontsize=8)
    else:
        ax.text(
            0.02,
            0.98,
            "Entropy is zero in all cells",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=9,
            color="white",
            bbox={"facecolor": "black", "alpha": 0.4, "pad": 3},
        )

    # Circle size encodes discord.
    discord_sizes = 30.0 + (discord * 350.0)
    ax.scatter(
        grid_x.flatten(),
        grid_y.flatten(),
        s=discord_sizes.flatten(),
        facecolors="none",
        edgecolors="black",
        linewidths=1.0,
        label="Discord (size = 1 - max probability)",
    )

    _set_axes(
        ax,
        alphas=alphas,
        boundary_ids=boundary_ids,
        title="Stage-2 Heatmap with Entropy Contours and Discord Overlay",
    )
    cb = fig.colorbar(base, ax=ax)
    cb.set_label("P(reversal) across replicates")
    ax.legend(loc="upper right", frameon=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 2 Stage-2 map figures")
    parser.add_argument("--probability-csv", type=Path, required=True, help="stage2_probability_map*.csv path")
    parser.add_argument("--uncertainty-csv", type=Path, required=True, help="stage2_uncertainty_overlay*.csv path")
    parser.add_argument("--heatmap-out", type=Path, required=True, help="Output PNG for probability heatmap")
    parser.add_argument("--overlay-out", type=Path, required=True, help="Output PNG for entropy/discord overlay figure")
    parser.add_argument("--dpi", type=int, default=220, help="PNG resolution")
    args = parser.parse_args()

    prob_rows = _read_csv(args.probability_csv)
    unc_rows = _read_csv(args.uncertainty_csv)

    if not prob_rows:
        raise ValueError(f"No rows in probability CSV: {args.probability_csv}")
    if not unc_rows:
        raise ValueError(f"No rows in uncertainty CSV: {args.uncertainty_csv}")

    boundary_ids = sorted(
        {r["boundary_id"] for r in prob_rows if r.get("boundary_id")},
        key=_boundary_sort_key,
    )
    alphas = sorted({float(r["alpha"]) for r in prob_rows if r.get("alpha")})
    if not boundary_ids or not alphas:
        raise ValueError("Missing boundary/alpha coordinates in probability CSV")

    p_reversal = _build_matrix(
        prob_rows,
        value_key="p_reversal",
        boundary_ids=boundary_ids,
        alphas=alphas,
    )
    entropy = _build_matrix(
        unc_rows,
        value_key="entropy_normalized",
        boundary_ids=boundary_ids,
        alphas=alphas,
    )
    discord = _build_matrix(
        unc_rows,
        value_key="discord",
        boundary_ids=boundary_ids,
        alphas=alphas,
    )

    _plot_probability_heatmap(
        p_reversal=p_reversal,
        alphas=alphas,
        boundary_ids=boundary_ids,
        out_path=args.heatmap_out,
        dpi=args.dpi,
    )
    _plot_entropy_discord_overlay(
        p_reversal=p_reversal,
        entropy=entropy,
        discord=discord,
        alphas=alphas,
        boundary_ids=boundary_ids,
        out_path=args.overlay_out,
        dpi=args.dpi,
    )

    print(f"Wrote heatmap: {args.heatmap_out}")
    print(f"Wrote overlay: {args.overlay_out}")


if __name__ == "__main__":
    main()
