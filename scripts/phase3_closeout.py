#!/usr/bin/env python3
"""One-command Phase-3 closeout pipeline (verdicts + sensitivity + figures)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _read_yaml(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping at {path}, got {type(data).__name__}")
    return data


def _require(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")


def _run(cmd: list[str], *, env: Dict[str, str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full Phase-3 closeout artifact pipeline")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine",
        help="Run directory containing analysis_latest_per_config*.csv",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase3" / "desync_v2_thresholds.yaml",
        help="Frozen v2 threshold profile",
    )
    parser.add_argument("--python", type=str, default=sys.executable)
    parser.add_argument("--target-label", type=str, default="desynchrony")
    parser.add_argument("--min-target-fraction", type=float, default=0.8)
    parser.add_argument("--min-replicates", type=int, default=16)
    parser.add_argument(
        "--v1-min-antiphase-mean",
        type=float,
        default=0.5,
        help="Explicit anti-phase gate for strict v1 verdict call",
    )
    parser.add_argument("--antiphase-min", type=float, default=0.92)
    parser.add_argument("--antiphase-max", type=float, default=0.95)
    parser.add_argument("--antiphase-step", type=float, default=0.001)
    parser.add_argument("--min-robust-cells", type=int, default=1)
    args = parser.parse_args()

    scripts_dir = ROOT / "scripts"
    run_root = args.run_root
    profile = args.profile

    analysis_v1 = run_root / "analysis_latest_per_config.csv"
    analysis_v2 = run_root / "analysis_latest_per_config_v2.csv"
    _require(scripts_dir / "phase3_desync_verdict.py", "script phase3_desync_verdict.py")
    _require(scripts_dir / "phase3_antiphase_sensitivity.py", "script phase3_antiphase_sensitivity.py")
    _require(scripts_dir / "phase3_plot_classifier_comparison.py", "script phase3_plot_classifier_comparison.py")
    _require(scripts_dir / "phase3_plot_representative_traces.py", "script phase3_plot_representative_traces.py")
    _require(profile, "threshold profile")
    _require(analysis_v1, "analysis v1 CSV")
    _require(analysis_v2, "analysis v2 CSV")

    threshold_data = _read_yaml(profile)
    lag_threshold = float(threshold_data["desync_lag_lo"])
    antiphase_threshold = float(threshold_data["desync_antiphase_lo"])

    env = os.environ.copy()
    env.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))

    outputs = {
        "cells_v1": run_root / "desync_cells_v1.csv",
        "robust_v1": run_root / "desync_robust_cells_v1.csv",
        "meta_v1": run_root / "verdict_meta_v1.yaml",
        "cells_v2": run_root / "desync_cells_v2.csv",
        "robust_v2": run_root / "desync_robust_cells_v2.csv",
        "meta_v2": run_root / "verdict_meta_v2.yaml",
        "sensitivity_csv": run_root / "sensitivity_antiphase_threshold.csv",
        "sensitivity_fig": run_root / "fig_phase3_v2_antiphase_sensitivity.png",
        "fig_prob": run_root / "fig_phase3_desync_probability_v1_v2.png",
        "fig_plane": run_root / "fig_phase3_lag_antiphase_plane_v1_v2.png",
        "selection_csv": run_root / "representative_selection_v2.csv",
        "fig_desync_core": run_root / "fig_phase3_trace_desync_core_v2.png",
        "fig_boundary_near": run_root / "fig_phase3_trace_boundary_near_v2.png",
        "fig_distributions": run_root / "fig_phase3_label_distributions_v1_v2.png",
    }

    # 1) Verdict tables (v1, v2)
    _run(
        [
            args.python,
            str(scripts_dir / "phase3_desync_verdict.py"),
            "--analysis-csv",
            str(analysis_v1),
            "--threshold-profile",
            str(profile),
            "--target-label",
            args.target_label,
            "--min-target-fraction",
            str(args.min_target_fraction),
            "--min-replicates",
            str(args.min_replicates),
            "--min-antiphase-mean",
            str(args.v1_min_antiphase_mean),
            "--cells-output",
            str(outputs["cells_v1"]),
            "--robust-output",
            str(outputs["robust_v1"]),
            "--meta-output",
            str(outputs["meta_v1"]),
        ],
        env=env,
    )
    _run(
        [
            args.python,
            str(scripts_dir / "phase3_desync_verdict.py"),
            "--analysis-csv",
            str(analysis_v2),
            "--threshold-profile",
            str(profile),
            "--target-label",
            args.target_label,
            "--min-target-fraction",
            str(args.min_target_fraction),
            "--min-replicates",
            str(args.min_replicates),
            "--cells-output",
            str(outputs["cells_v2"]),
            "--robust-output",
            str(outputs["robust_v2"]),
            "--meta-output",
            str(outputs["meta_v2"]),
        ],
        env=env,
    )

    # 2) Anti-phase sensitivity re-analysis (artifact-only)
    _run(
        [
            args.python,
            str(scripts_dir / "phase3_antiphase_sensitivity.py"),
            "--analysis-csv",
            str(analysis_v1),
            "--threshold-profile",
            str(profile),
            "--antiphase-min",
            str(args.antiphase_min),
            "--antiphase-max",
            str(args.antiphase_max),
            "--antiphase-step",
            str(args.antiphase_step),
            "--min-target-fraction",
            str(args.min_target_fraction),
            "--min-replicates",
            str(args.min_replicates),
            "--min-robust-cells",
            str(args.min_robust_cells),
            "--output-csv",
            str(outputs["sensitivity_csv"]),
            "--fig-output",
            str(outputs["sensitivity_fig"]),
        ],
        env=env,
    )

    # 3) Classifier comparison figures
    _run(
        [
            args.python,
            str(scripts_dir / "phase3_plot_classifier_comparison.py"),
            "--cells-v1",
            str(outputs["cells_v1"]),
            "--cells-v2",
            str(outputs["cells_v2"]),
            "--fig-probability",
            str(outputs["fig_prob"]),
            "--fig-plane",
            str(outputs["fig_plane"]),
            "--robust-threshold",
            str(args.min_target_fraction),
            "--lag-threshold",
            str(lag_threshold),
            "--antiphase-threshold",
            str(antiphase_threshold),
        ],
        env=env,
    )

    # 4) Representative traces + overlap distribution
    _run(
        [
            args.python,
            str(scripts_dir / "phase3_plot_representative_traces.py"),
            "--analysis-v2",
            str(analysis_v2),
            "--analysis-v1",
            str(analysis_v1),
            "--thresholds",
            str(profile),
            "--selection-output",
            str(outputs["selection_csv"]),
            "--desync-fig",
            str(outputs["fig_desync_core"]),
            "--boundary-fig",
            str(outputs["fig_boundary_near"]),
            "--distribution-fig",
            str(outputs["fig_distributions"]),
        ],
        env=env,
    )

    for label, path in outputs.items():
        _require(path, f"closeout output {label}")
    print("phase3_closeout: SUCCESS")
    print(f"run_root={run_root}")
    print(f"profile={profile}")


if __name__ == "__main__":
    main()
