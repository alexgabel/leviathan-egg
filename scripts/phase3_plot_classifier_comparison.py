#!/usr/bin/env python3
"""Generate Phase-3 classifier comparison figures (v1 vs v2)."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _to_float(rows: List[Dict[str, str]], key: str) -> np.ndarray:
    return np.asarray([float(r[key]) for r in rows], dtype=float)


def _sort_cells(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return sorted(rows, key=lambda r: float(r["strength"]))


def _plot_probability_curve(
    *,
    v1_cells: List[Dict[str, str]],
    v2_cells: List[Dict[str, str]],
    output_path: Path,
    robust_threshold: float,
) -> None:
    s = _to_float(v1_cells, "strength")
    p1 = _to_float(v1_cells, "p_desynchrony")
    p2 = _to_float(v2_cells, "p_desynchrony")

    plt.figure(figsize=(9, 5))
    plt.plot(s, p1, marker="o", linewidth=2.0, label="Classifier v1 (strict lag-gated)")
    plt.plot(s, p2, marker="s", linewidth=2.0, label="Classifier v2 (anti-phase-inclusive)")
    plt.axhline(robust_threshold, color="black", linestyle="--", linewidth=1.25, label=f"Robustness gate ({robust_threshold:.2f})")
    plt.ylim(-0.02, 1.02)
    plt.xlabel("Coupling strength (negative sign, lag=8)")
    plt.ylabel("P(desynchrony) across replicates")
    plt.title("Phase 3: Desynchrony Probability by Classifier Version")
    plt.grid(alpha=0.25)
    plt.legend(loc="lower right", frameon=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


def _plot_lag_antiphase_plane(
    *,
    v1_cells: List[Dict[str, str]],
    v2_cells: List[Dict[str, str]],
    output_path: Path,
    lag_threshold: float,
    antiphase_threshold: float,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharex=True, sharey=True)
    versions = [
        ("v1 strict lag-gated", v1_cells),
        ("v2 anti-phase-inclusive", v2_cells),
    ]

    for ax, (title, rows) in zip(axes, versions):
        lag = _to_float(rows, "sync_lag_mean")
        anti = _to_float(rows, "sync_antiphase_mean")
        p = _to_float(rows, "p_desynchrony")
        strength = _to_float(rows, "strength")
        size = 100 + 700 * p

        scatter = ax.scatter(lag, anti, c=strength, s=size, cmap="viridis", alpha=0.9, edgecolor="black", linewidth=0.35)
        ax.axvline(lag_threshold, color="black", linestyle="--", linewidth=1.1)
        ax.axhline(antiphase_threshold, color="black", linestyle=":", linewidth=1.1)
        for l, a, s in zip(lag, anti, strength):
            ax.text(l + 0.002, a + 0.00025, f"{s:.2f}", fontsize=8)
        ax.set_title(title)
        ax.set_xlabel("Mean abs phase lag")
        ax.grid(alpha=0.2)

    axes[0].set_ylabel("Mean anti-phase fraction")
    cbar = fig.colorbar(scatter, ax=axes.ravel().tolist(), shrink=0.85)
    cbar.set_label("Strength")
    fig.suptitle("Phase 3: Lag vs Anti-Phase Plane (marker size = P(desynchrony))", y=1.02)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot Phase-3 classifier comparison figures")
    parser.add_argument(
        "--cells-v1",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "desync_cells_v1.csv",
    )
    parser.add_argument(
        "--cells-v2",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "desync_cells_v2.csv",
    )
    parser.add_argument(
        "--fig-probability",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "fig_phase3_desync_probability_v1_v2.png",
    )
    parser.add_argument(
        "--fig-plane",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "fig_phase3_lag_antiphase_plane_v1_v2.png",
    )
    parser.add_argument("--robust-threshold", type=float, default=0.8)
    parser.add_argument("--lag-threshold", type=float, default=28.20011175)
    parser.add_argument("--antiphase-threshold", type=float, default=0.93)
    args = parser.parse_args()

    v1 = _sort_cells(_read_csv(args.cells_v1))
    v2 = _sort_cells(_read_csv(args.cells_v2))
    if len(v1) != len(v2):
        raise ValueError("v1 and v2 cell tables must have same row count")

    _plot_probability_curve(
        v1_cells=v1,
        v2_cells=v2,
        output_path=args.fig_probability,
        robust_threshold=args.robust_threshold,
    )
    _plot_lag_antiphase_plane(
        v1_cells=v1,
        v2_cells=v2,
        output_path=args.fig_plane,
        lag_threshold=args.lag_threshold,
        antiphase_threshold=args.antiphase_threshold,
    )
    print(f"wrote {args.fig_probability}")
    print(f"wrote {args.fig_plane}")


if __name__ == "__main__":
    main()
