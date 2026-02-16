#!/usr/bin/env python3
"""Select representative Phase-3 runs and plot patch-level + distribution figures."""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))

import matplotlib.pyplot as plt
import numpy as np
import yaml


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _parse_thresholds(path: Path) -> Dict[str, float]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        "desync_order_lo": float(data["desync_order_lo"]),
        "desync_lock_lo": float(data["desync_lock_lo"]),
        "desync_lag_lo": float(data["desync_lag_lo"]),
        "desync_antiphase_lo": float(data["desync_antiphase_lo"]),
    }


def _as_float(row: Dict[str, str], key: str) -> float:
    raw = row.get(key, "")
    if raw in ("", "nan", "NaN"):
        return float("nan")
    return float(raw)


def _desync_score(row: Dict[str, str], thr: Dict[str, float]) -> float:
    # Higher means deeper inside v2 desync region (max-separation core exemplar).
    order_margin = thr["desync_order_lo"] - float(row["sync_order_mean"])
    lock_margin = thr["desync_lock_lo"] - float(row["sync_lock_mean"])
    lag_margin = float(row["sync_lag_mean"]) - thr["desync_lag_lo"]
    anti = _as_float(row, "sync_antiphase_mean")
    anti_margin = anti - thr["desync_antiphase_lo"] if not np.isnan(anti) else -1e6
    # v2 requires order+lock and (lag OR anti-phase); min margin approximates distance to boundary.
    return min(order_margin, lock_margin, max(lag_margin, anti_margin))


def _boundary_distance(row: Dict[str, str], thr: Dict[str, float]) -> float:
    # Lower means closer to crossing into v2 desync classification (near-boundary exemplar).
    order_fail = max(0.0, float(row["sync_order_mean"]) - thr["desync_order_lo"])
    lock_fail = max(0.0, float(row["sync_lock_mean"]) - thr["desync_lock_lo"])
    lag_fail = max(0.0, thr["desync_lag_lo"] - float(row["sync_lag_mean"]))
    anti = _as_float(row, "sync_antiphase_mean")
    anti_fail = max(0.0, thr["desync_antiphase_lo"] - anti) if not np.isnan(anti) else 1.0
    or_fail = min(lag_fail, anti_fail)
    return order_fail + lock_fail + or_fail


def _select_representatives(
    rows: List[Dict[str, str]],
    *,
    thr: Dict[str, float],
) -> Dict[str, Dict[str, str]]:
    desync_rows = [r for r in rows if r.get("label") == "desynchrony"]
    boundary_rows = [r for r in rows if r.get("label") == "boundary"]
    if not desync_rows:
        raise ValueError("No desynchrony rows available in analysis table")
    if not boundary_rows:
        raise ValueError("No boundary rows available in analysis table")

    core_desync = max(desync_rows, key=lambda r: _desync_score(r, thr))
    near_boundary = min(boundary_rows, key=lambda r: _boundary_distance(r, thr))
    return {"desync_core_v2": core_desync, "boundary_near_v2": near_boundary}


def _plot_trace(
    *,
    run_row: Dict[str, str],
    title_prefix: str,
    output_path: Path,
    thresholds: Dict[str, float],
) -> None:
    metrics_path = Path(run_row["run_dir"]) / "metrics.csv"
    rows = _read_csv(metrics_path)
    if not rows:
        raise ValueError(f"No metric rows found: {metrics_path}")

    t = np.asarray([float(r["t"]) for r in rows], dtype=float)
    patches = []
    patch_keys = []
    for i in range(8):
        key = f"frac_hier_patch_{i}"
        if key in rows[0]:
            patch_keys.append(key)
    for key in patch_keys:
        patches.append(np.asarray([float(r[key]) for r in rows], dtype=float))

    order = np.asarray([float(r["synchrony_order_parameter"]) for r in rows], dtype=float)
    lock = np.asarray([float(r["synchrony_phase_lock_fraction"]) for r in rows], dtype=float)
    lag = np.asarray([float(r["synchrony_mean_abs_phase_lag"]) for r in rows], dtype=float)
    anti = np.asarray([float(r["synchrony_antiphase_fraction"]) for r in rows], dtype=float)

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)

    for i, series in enumerate(patches):
        axes[0].plot(t, series, linewidth=1.1, label=f"patch_{i}")
    axes[0].set_ylabel("frac_hier_patch_i")
    axes[0].set_ylim(-0.02, 1.02)
    axes[0].set_title(
        f"{title_prefix}: {Path(run_row['config_path']).name}\n"
        f"label={run_row['label']} order={run_row['sync_order_mean']} "
        f"lock={run_row['sync_lock_mean']} lag={run_row['sync_lag_mean']} "
        f"anti={run_row.get('sync_antiphase_mean','')}"
    )
    axes[0].legend(loc="upper right", ncol=min(4, max(1, len(patches))), frameon=False)
    axes[0].grid(alpha=0.2)

    axes[1].plot(t, order, label="order", linewidth=1.2)
    axes[1].plot(t, lock, label="lock", linewidth=1.2)
    axes[1].plot(t, anti, label="anti-phase", linewidth=1.2)
    axes[1].axhline(thresholds["desync_order_lo"], color="black", linestyle="--", linewidth=1.0)
    axes[1].axhline(thresholds["desync_lock_lo"], color="black", linestyle="--", linewidth=1.0)
    axes[1].axhline(thresholds["desync_antiphase_lo"], color="black", linestyle=":", linewidth=1.0)
    axes[1].set_ylabel("order/lock/anti")
    axes[1].set_ylim(-0.02, 1.02)
    axes[1].grid(alpha=0.2)

    ax2 = axes[1].twinx()
    ax2.plot(t, lag, color="tab:red", alpha=0.7, linewidth=1.0, label="lag")
    ax2.axhline(thresholds["desync_lag_lo"], color="tab:red", linestyle="--", linewidth=1.0)
    ax2.set_ylabel("mean abs lag")

    axes[1].set_xlabel("t")
    handles, labels = axes[1].get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    axes[1].legend(handles + h2, labels + l2, loc="upper right", frameon=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _write_selection(path: Path, picked: Dict[str, Dict[str, str]]) -> None:
    rows = []
    for kind, row in picked.items():
        rows.append(
            {
                "kind": kind,
                "run_id": row["run_id"],
                "config_path": row["config_path"],
                "run_dir": row["run_dir"],
                "label": row["label"],
                "sync_order_mean": row["sync_order_mean"],
                "sync_lock_mean": row["sync_lock_mean"],
                "sync_lag_mean": row["sync_lag_mean"],
                "sync_antiphase_mean": row.get("sync_antiphase_mean", ""),
                "selection_note": (
                    "highest_v2_confidence_max_separation"
                    if kind == "desync_core_v2"
                    else "closest_boundary_to_v2_desync_crossing"
                ),
            }
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "kind",
                "run_id",
                "config_path",
                "run_dir",
                "label",
                "sync_order_mean",
                "sync_lock_mean",
                "sync_lag_mean",
                "sync_antiphase_mean",
                "selection_note",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _distribution_panel(
    *,
    ax: plt.Axes,
    rows: List[Dict[str, str]],
    title: str,
) -> None:
    style = {
        "desynchrony": ("tab:red", "o"),
        "boundary": ("tab:orange", "s"),
        "synchrony": ("tab:blue", "^"),
    }
    labels = ["desynchrony", "boundary", "synchrony"]
    for label in labels:
        subset = [r for r in rows if r.get("label") == label]
        if not subset:
            continue
        lag = np.asarray([float(r["sync_lag_mean"]) for r in subset], dtype=float)
        anti = np.asarray([_as_float(r, "sync_antiphase_mean") for r in subset], dtype=float)
        mask = ~np.isnan(anti)
        lag = lag[mask]
        anti = anti[mask]
        if lag.size == 0:
            continue
        color, marker = style[label]
        ax.scatter(
            lag,
            anti,
            c=color,
            marker=marker,
            alpha=0.75,
            edgecolors="black",
            linewidths=0.35,
            label=f"{label} (n={lag.size})",
        )
    ax.set_title(title)
    ax.set_xlabel("Mean abs phase lag")
    ax.grid(alpha=0.2)


def _plot_label_distributions(
    *,
    rows_v1: List[Dict[str, str]],
    rows_v2: List[Dict[str, str]],
    thresholds: Dict[str, float],
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharex=True, sharey=True)
    _distribution_panel(ax=axes[0], rows=rows_v1, title="v1 strict lag-gated")
    _distribution_panel(ax=axes[1], rows=rows_v2, title="v2 anti-phase-inclusive")

    for ax in axes:
        ax.axvline(thresholds["desync_lag_lo"], color="black", linestyle="--", linewidth=1.0)
        ax.axhline(thresholds["desync_antiphase_lo"], color="black", linestyle=":", linewidth=1.0)

    axes[0].set_ylabel("Mean anti-phase fraction")
    handles, labels = axes[1].get_legend_handles_labels()
    axes[1].legend(handles, labels, loc="lower left", frameon=False)
    fig.suptitle(
        "Phase 3: Lag/Anti-Phase by Label (near-boundary regime; overlap may remain high)",
        y=1.02,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot representative Phase-3 traces")
    parser.add_argument(
        "--analysis-csv",
        type=Path,
        default=None,
        help="Backward-compatible alias for --analysis-v2",
    )
    parser.add_argument(
        "--analysis-v2",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "analysis_latest_per_config_v2.csv",
    )
    parser.add_argument(
        "--analysis-v1",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "analysis_latest_per_config.csv",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase3" / "desync_v2_thresholds.yaml",
    )
    parser.add_argument(
        "--selection-output",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "representative_selection_v2.csv",
    )
    parser.add_argument(
        "--desync-fig",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "fig_phase3_trace_desync_core_v2.png",
    )
    parser.add_argument(
        "--boundary-fig",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "fig_phase3_trace_boundary_near_v2.png",
    )
    parser.add_argument(
        "--distribution-fig",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "fig_phase3_label_distributions_v1_v2.png",
    )
    args = parser.parse_args()

    analysis_v2 = args.analysis_csv if args.analysis_csv is not None else args.analysis_v2
    rows_v2 = _read_csv(analysis_v2)
    rows_v1 = _read_csv(args.analysis_v1)
    thr = _parse_thresholds(args.thresholds)
    picked = _select_representatives(rows_v2, thr=thr)
    _write_selection(args.selection_output, picked)

    _plot_trace(
        run_row=picked["desync_core_v2"],
        title_prefix="Max-separation desynchrony core run (v2)",
        output_path=args.desync_fig,
        thresholds=thr,
    )
    _plot_trace(
        run_row=picked["boundary_near_v2"],
        title_prefix="Near-boundary run (closest to v2 crossing)",
        output_path=args.boundary_fig,
        thresholds=thr,
    )
    _plot_label_distributions(
        rows_v1=rows_v1,
        rows_v2=rows_v2,
        thresholds=thr,
        output_path=args.distribution_fig,
    )

    print(f"wrote {args.selection_output}")
    print(f"wrote {args.desync_fig}")
    print(f"wrote {args.boundary_fig}")
    print(f"wrote {args.distribution_fig}")


if __name__ == "__main__":
    main()
