#!/usr/bin/env python3
"""Generate a narrow Phase-3 desynchrony refinement manifest near zero strength."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable, List

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _parse_float_list(text: str) -> List[float]:
    return [float(x.strip()) for x in text.split(",") if x.strip()]


def _parse_int_list(text: str) -> List[int]:
    return [int(x.strip()) for x in text.split(",") if x.strip()]


def _write_csv(path: Path, rows: List[dict], fieldnames: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate narrow desynchrony-refinement manifest"
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase3" / "manifest_desync_refine.csv",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase1_reversal.yaml",
    )
    parser.add_argument("--config-prefix", type=str, default="phase3r")
    parser.add_argument("--seed-base", type=int, default=9101)
    parser.add_argument(
        "--strengths",
        type=str,
        default="0.00,0.05,0.10,0.20,0.30",
    )
    parser.add_argument(
        "--lags",
        type=str,
        default="4,8",
    )
    parser.add_argument(
        "--modes",
        type=str,
        default="mean_field",
    )
    parser.add_argument("--num-patches", type=int, default=4)
    parser.add_argument("--phase-profile", type=str, default="staggered")
    parser.add_argument("--topology", type=str, default="ring")
    parser.add_argument("--sign", type=int, default=-1)
    parser.add_argument(
        "--high-replicates",
        type=int,
        default=12,
        help="Replicates for very-low strengths",
    )
    parser.add_argument(
        "--base-replicates",
        type=int,
        default=10,
        help="Replicates for remaining strengths",
    )
    parser.add_argument(
        "--high-rep-max-strength",
        type=float,
        default=0.10,
        help="Use high-replicates for strengths <= this value",
    )
    parser.add_argument(
        "--steps-multiplier",
        type=float,
        default=2.0,
        help="Multiplier for total_steps and burn_in_period on refinement runs",
    )
    args = parser.parse_args()

    strengths = _parse_float_list(args.strengths)
    lags = _parse_int_list(args.lags)
    modes = [x.strip() for x in args.modes.split(",") if x.strip()]

    baseline = yaml.safe_load(args.baseline.read_text(encoding="utf-8"))
    rr = baseline.get("runtime_and_reproducibility", {})
    base_total = int(rr.get("total_steps", 24000))
    base_burn = int(rr.get("burn_in_period", max(1, base_total // 10)))
    scaled_total = max(1, int(round(base_total * float(args.steps_multiplier))))
    scaled_burn = max(1, int(round(base_burn * float(args.steps_multiplier))))

    rows: List[dict] = []
    seed = int(args.seed_base)
    for mode in modes:
        for lag in lags:
            for strength in strengths:
                reps = (
                    int(args.high_replicates)
                    if strength <= float(args.high_rep_max_strength)
                    else int(args.base_replicates)
                )
                strength_code = int(round(strength * 100))
                for rep in range(1, reps + 1):
                    rel_config = (
                        f"experiments/configs/phase3/{args.config_prefix}_"
                        f"np{args.num_patches}_ph-{args.phase_profile}_topo-{args.topology}"
                        f"_sign-{args.sign}_mode-{mode}_lag{lag}_k{strength_code:02d}_r{rep}.yaml"
                    )
                    sweep_value = (
                        f"phase_profile={args.phase_profile};topology={args.topology};"
                        f"sign={args.sign};mode={mode};lag_steps={lag};"
                        f"strength={strength:.4f};replicate={rep}"
                    )
                    notes = (
                        f"num_patches={args.num_patches};phase_profile={args.phase_profile};"
                        f"topology={args.topology};sign={args.sign};mode={mode};lag_steps={lag};"
                        f"strength={strength:.4f};target_metric=frac_hier;"
                        f"normalize_by_degree=true;total_steps={scaled_total};"
                        f"burn_in_period={scaled_burn}"
                    )
                    rows.append(
                        {
                            "config_path": rel_config,
                            "sweep_axis": "phase3_desync_refine_near_zero",
                            "sweep_value": sweep_value,
                            "hypothesis": "negative_coupling_near_zero_refine",
                            "seed": str(seed),
                            "stage": "confirmation",
                            "notes": notes,
                        }
                    )
                    seed += 1

    _write_csv(
        args.manifest_out,
        rows,
        [
            "config_path",
            "sweep_axis",
            "sweep_value",
            "hypothesis",
            "seed",
            "stage",
            "notes",
        ],
    )
    print(f"wrote rows={len(rows)} manifest={args.manifest_out}")
    print(
        f"runtime_override total_steps={scaled_total} burn_in_period={scaled_burn} "
        f"(x{args.steps_multiplier})"
    )


if __name__ == "__main__":
    main()
