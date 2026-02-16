#!/usr/bin/env python3
"""Artifact-only anti-phase threshold sensitivity for the Phase-3 v2 classifier."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import matplotlib
import numpy as np
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RunSummary:
    mode: str
    lag_steps: str
    strength: str
    sync_order_mean: float
    sync_lock_mean: float
    sync_lag_mean: float
    sync_antiphase_mean: float


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_yaml(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping YAML at {path}, got {type(data).__name__}")
    return data


def _parse_kv(text: str | None) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not text:
        return out
    for token in text.split(";"):
        token = token.strip()
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def _thresholds_from_profile(profile: Dict[str, object]) -> Dict[str, float]:
    required = [
        "sync_order_hi",
        "sync_lock_hi",
        "sync_lag_hi",
        "desync_order_lo",
        "desync_lock_lo",
        "desync_lag_lo",
    ]
    missing = [k for k in required if k not in profile]
    if missing:
        raise KeyError(f"Threshold profile missing required keys: {', '.join(missing)}")
    return {k: float(profile[k]) for k in required}


def _load_runs(path: Path) -> List[RunSummary]:
    rows = _read_csv(path)
    runs: List[RunSummary] = []
    for row in rows:
        kv = _parse_kv(row.get("sweep_value", ""))
        mode = kv.get("mode", "")
        lag_steps = kv.get("lag_steps", "")
        strength = kv.get("strength", row.get("strength", ""))
        if not mode or not lag_steps or not strength:
            continue
        runs.append(
            RunSummary(
                mode=mode,
                lag_steps=lag_steps,
                strength=strength,
                sync_order_mean=float(row["sync_order_mean"]),
                sync_lock_mean=float(row["sync_lock_mean"]),
                sync_lag_mean=float(row["sync_lag_mean"]),
                sync_antiphase_mean=float(row["sync_antiphase_mean"]),
            )
        )
    if not runs:
        raise ValueError(f"No parseable run summaries found in {path}")
    return runs


def _threshold_grid(min_value: float, max_value: float, step: float) -> List[float]:
    if step <= 0:
        raise ValueError("step must be > 0")
    if max_value < min_value:
        raise ValueError("max_value must be >= min_value")
    n = int(round((max_value - min_value) / step))
    return [round(min_value + i * step, 6) for i in range(n + 1)]


def _classify_v2(
    run: RunSummary,
    *,
    sync_order_hi: float,
    sync_lock_hi: float,
    sync_lag_hi: float,
    desync_order_lo: float,
    desync_lock_lo: float,
    desync_lag_lo: float,
    desync_antiphase_lo: float,
) -> str:
    if (
        run.sync_order_mean >= sync_order_hi
        and run.sync_lock_mean >= sync_lock_hi
        and run.sync_lag_mean <= sync_lag_hi
    ):
        return "synchrony"
    if (
        run.sync_order_mean <= desync_order_lo
        and run.sync_lock_mean <= desync_lock_lo
        and (
            run.sync_lag_mean >= desync_lag_lo
            or run.sync_antiphase_mean >= desync_antiphase_lo
        )
    ):
        return "desynchrony"
    return "boundary"


def _window_indices(mask: Sequence[bool]) -> List[Tuple[int, int]]:
    windows: List[Tuple[int, int]] = []
    start = -1
    for i, flag in enumerate(mask):
        if flag and start < 0:
            start = i
        elif not flag and start >= 0:
            windows.append((start, i - 1))
            start = -1
    if start >= 0:
        windows.append((start, len(mask) - 1))
    return windows


def _plot(
    *,
    rows: List[Dict[str, str]],
    output: Path,
    min_robust_cells: int,
) -> None:
    x = np.asarray([float(r["antiphase_threshold"]) for r in rows], dtype=float)
    robust_cells = np.asarray([int(r["robust_cells"]) for r in rows], dtype=float)
    p_desync_runs = np.asarray([float(r["p_desync_runs"]) for r in rows], dtype=float)
    claim_holds = [r["claim_holds"] == "1" for r in rows]

    fig, ax1 = plt.subplots(figsize=(10, 5))
    line1 = ax1.plot(x, robust_cells, marker="o", linewidth=2, label="Robust desync cells")[0]
    ax1.axhline(
        min_robust_cells,
        linestyle="--",
        linewidth=1.2,
        color="black",
        label=f"Claim gate (robust_cells >= {min_robust_cells})",
    )
    ax1.set_xlabel("Anti-phase threshold")
    ax1.set_ylabel("Robust desync cells")
    ax1.grid(alpha=0.25)

    windows = _window_indices(claim_holds)
    for start_idx, end_idx in windows:
        ax1.axvspan(x[start_idx], x[end_idx], color="tab:green", alpha=0.12)

    ax2 = ax1.twinx()
    line2 = ax2.plot(
        x,
        p_desync_runs,
        marker="s",
        linewidth=1.7,
        color="tab:orange",
        label="Run-level P(desynchrony)",
    )[0]
    ax2.set_ylabel("Run-level P(desynchrony)")
    ax2.set_ylim(-0.02, 1.02)

    lines = [line1, line2]
    labels = [line.get_label() for line in lines]
    ax1.legend(lines, labels, loc="lower left", frameon=False)

    title = "Phase 3 v2 Anti-Phase Threshold Sensitivity"
    if windows:
        lo = x[windows[0][0]]
        hi = x[windows[-1][1]]
        title += f" (claim window approx [{lo:.3f}, {hi:.3f}])"
    else:
        title += " (no robust-claim window)"
    plt.title(title)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output, dpi=220)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase-3 anti-phase threshold sensitivity (artifact-only)")
    parser.add_argument(
        "--analysis-csv",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "analysis_latest_per_config.csv",
    )
    parser.add_argument(
        "--threshold-profile",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase3" / "desync_v2_thresholds.yaml",
        help="Base v2 threshold profile (all gates except anti-phase threshold grid)",
    )
    parser.add_argument("--antiphase-min", type=float, default=0.92)
    parser.add_argument("--antiphase-max", type=float, default=0.95)
    parser.add_argument("--antiphase-step", type=float, default=0.001)
    parser.add_argument("--min-target-fraction", type=float, default=0.8)
    parser.add_argument("--min-replicates", type=int, default=8)
    parser.add_argument(
        "--min-robust-cells",
        type=int,
        default=1,
        help="Claim gate: minimum robust desync cells needed for robust-v2 claim to hold",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "sensitivity_antiphase_threshold.csv",
    )
    parser.add_argument(
        "--fig-output",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine" / "fig_phase3_v2_antiphase_sensitivity.png",
    )
    args = parser.parse_args()

    profile = _read_yaml(args.threshold_profile)
    thresholds = _thresholds_from_profile(profile)
    runs = _load_runs(args.analysis_csv)
    thresholds_grid = _threshold_grid(args.antiphase_min, args.antiphase_max, args.antiphase_step)

    sensitivity_rows: List[Dict[str, str]] = []
    for anti_thr in thresholds_grid:
        labels = []
        cell_groups: Dict[tuple[str, str, str], List[Tuple[str, float]]] = defaultdict(list)
        for run in runs:
            label = _classify_v2(
                run,
                sync_order_hi=thresholds["sync_order_hi"],
                sync_lock_hi=thresholds["sync_lock_hi"],
                sync_lag_hi=thresholds["sync_lag_hi"],
                desync_order_lo=thresholds["desync_order_lo"],
                desync_lock_lo=thresholds["desync_lock_lo"],
                desync_lag_lo=thresholds["desync_lag_lo"],
                desync_antiphase_lo=anti_thr,
            )
            labels.append(label)
            key = (run.mode, run.lag_steps, run.strength)
            cell_groups[key].append((label, run.sync_antiphase_mean))

        run_counts = Counter(labels)
        run_total = len(labels)
        p_desync_runs = run_counts.get("desynchrony", 0) / run_total if run_total else 0.0

        robust_cells = 0
        cell_desync_ps: List[float] = []
        cell_antis: List[float] = []
        for values in cell_groups.values():
            n = len(values)
            if n == 0:
                continue
            desync_n = sum(1 for label, _ in values if label == "desynchrony")
            p_desync = desync_n / n
            anti_mean = sum(a for _, a in values) / n
            cell_desync_ps.append(p_desync)
            cell_antis.append(anti_mean)

            robust = (
                n >= args.min_replicates
                and p_desync >= args.min_target_fraction
                and anti_mean >= anti_thr
            )
            if robust:
                robust_cells += 1

        cell_count = len(cell_groups)
        robust_fraction = robust_cells / cell_count if cell_count else 0.0
        claim_holds = robust_cells >= args.min_robust_cells

        sensitivity_rows.append(
            {
                "antiphase_threshold": f"{anti_thr:.6f}",
                "runs_total": str(run_total),
                "count_synchrony_runs": str(run_counts.get("synchrony", 0)),
                "count_boundary_runs": str(run_counts.get("boundary", 0)),
                "count_desynchrony_runs": str(run_counts.get("desynchrony", 0)),
                "p_desync_runs": f"{p_desync_runs:.6f}",
                "cells_total": str(cell_count),
                "robust_cells": str(robust_cells),
                "robust_cell_fraction": f"{robust_fraction:.6f}",
                "cell_p_desync_mean": (
                    f"{(sum(cell_desync_ps) / len(cell_desync_ps)):.6f}" if cell_desync_ps else ""
                ),
                "cell_p_desync_min": f"{min(cell_desync_ps):.6f}" if cell_desync_ps else "",
                "cell_p_desync_max": f"{max(cell_desync_ps):.6f}" if cell_desync_ps else "",
                "cell_antiphase_mean_min": f"{min(cell_antis):.6f}" if cell_antis else "",
                "cell_antiphase_mean_max": f"{max(cell_antis):.6f}" if cell_antis else "",
                "claim_holds": "1" if claim_holds else "0",
                "min_robust_cells_gate": str(args.min_robust_cells),
                "stability_window_id": "",
                "stability_window_start": "",
                "stability_window_end": "",
            }
        )

    hold_mask = [row["claim_holds"] == "1" for row in sensitivity_rows]
    windows = _window_indices(hold_mask)
    for window_id, (start_idx, end_idx) in enumerate(windows, start=1):
        start_val = sensitivity_rows[start_idx]["antiphase_threshold"]
        end_val = sensitivity_rows[end_idx]["antiphase_threshold"]
        for idx in range(start_idx, end_idx + 1):
            sensitivity_rows[idx]["stability_window_id"] = str(window_id)
            sensitivity_rows[idx]["stability_window_start"] = start_val
            sensitivity_rows[idx]["stability_window_end"] = end_val

    fieldnames = [
        "antiphase_threshold",
        "runs_total",
        "count_synchrony_runs",
        "count_boundary_runs",
        "count_desynchrony_runs",
        "p_desync_runs",
        "cells_total",
        "robust_cells",
        "robust_cell_fraction",
        "cell_p_desync_mean",
        "cell_p_desync_min",
        "cell_p_desync_max",
        "cell_antiphase_mean_min",
        "cell_antiphase_mean_max",
        "claim_holds",
        "min_robust_cells_gate",
        "stability_window_id",
        "stability_window_start",
        "stability_window_end",
    ]
    _write_csv(args.output_csv, sensitivity_rows, fieldnames)
    _plot(rows=sensitivity_rows, output=args.fig_output, min_robust_cells=args.min_robust_cells)

    if windows:
        segments = []
        for start_idx, end_idx in windows:
            segments.append(
                f"[{sensitivity_rows[start_idx]['antiphase_threshold']}, {sensitivity_rows[end_idx]['antiphase_threshold']}]"
            )
        print(f"robust_v2_claim_stability_windows={'; '.join(segments)}")
    else:
        print("robust_v2_claim_stability_windows=<none>")
    print(f"rows={len(sensitivity_rows)}")
    print(f"wrote {args.output_csv}")
    print(f"wrote {args.fig_output}")


if __name__ == "__main__":
    main()
