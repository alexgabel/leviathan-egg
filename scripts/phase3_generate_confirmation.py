#!/usr/bin/env python3
"""Generate Phase 3 Stage-2 confirmation manifest near synchrony boundaries."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

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


def _to_float(v: str) -> float:
    return float(v.strip())


def _boundary_intervals(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    # Group by all axes except strength.
    grouped: Dict[Tuple[str, str, str], List[Dict[str, str]]] = defaultdict(list)
    for r in rows:
        key = (r.get("phase_profile", ""), r.get("topology", ""), r.get("sign", ""))
        grouped[key].append(r)

    boundaries: List[Dict[str, str]] = []
    for (phase_profile, topology, sign), grp in grouped.items():
        grp = sorted(grp, key=lambda x: _to_float(x["strength"]))
        for i in range(len(grp) - 1):
            left = grp[i]
            right = grp[i + 1]
            if left["label"] == right["label"]:
                continue
            s0 = _to_float(left["strength"])
            s1 = _to_float(right["strength"])
            boundaries.append(
                {
                    "phase_profile": phase_profile,
                    "topology": topology,
                    "sign": sign,
                    "left_strength": f"{s0:.6f}",
                    "right_strength": f"{s1:.6f}",
                    "left_label": left["label"],
                    "right_label": right["label"],
                    "left_config": left["config_basename"],
                    "right_config": right["config_basename"],
                }
            )
    return boundaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 3 confirmation manifest")
    parser.add_argument(
        "--analysis-csv",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "analysis_latest_per_config.csv",
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase3" / "manifest_confirmation.csv",
    )
    parser.add_argument(
        "--boundary-out",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase3" / "boundary_cells_auto.csv",
    )
    parser.add_argument(
        "--alphas",
        type=str,
        default="0.2,0.4,0.6,0.8",
        help="Interpolation fractions between left/right boundary strengths",
    )
    parser.add_argument("--replicates", type=int, default=5)
    parser.add_argument("--seed-base", type=int, default=6101)
    parser.add_argument("--config-prefix", type=str, default="phase3c")
    args = parser.parse_args()

    rows = _read_csv(args.analysis_csv)
    rows = [r for r in rows if r.get("label")]
    boundaries = _boundary_intervals(rows)

    boundary_rows: List[Dict[str, str]] = []
    manifest_rows: List[Dict[str, str]] = []
    seed = args.seed_base
    alphas = [_to_float(x) for x in args.alphas.split(",") if x.strip()]

    for b_idx, b in enumerate(boundaries, start=1):
        left_s = _to_float(b["left_strength"])
        right_s = _to_float(b["right_strength"])
        boundary_id = f"b{b_idx:02d}"

        boundary_rows.append({"boundary_id": boundary_id, **b})

        for alpha in alphas:
            strength = left_s + alpha * (right_s - left_s)
            strength_code = int(round(strength * 100))
            for rep in range(1, args.replicates + 1):
                rel_config = (
                    f"experiments/configs/phase3/"
                    f"{args.config_prefix}_{boundary_id}_ph-{b['phase_profile']}"
                    f"_topo-{b['topology']}_sign-{b['sign']}_k{strength_code:02d}_r{rep}.yaml"
                )
                sweep_value = (
                    f"boundary_id={boundary_id};phase_profile={b['phase_profile']};"
                    f"topology={b['topology']};sign={b['sign']};strength={strength:.4f};"
                    f"alpha={alpha:.3f};replicate={rep}"
                )
                notes = (
                    f"num_patches=4;mode=mean_field;lag_steps=0;"
                    f"phase_profile={b['phase_profile']};topology={b['topology']};"
                    f"sign={b['sign']};strength={strength:.4f};"
                    f"source_left={b['left_config']}:{b['left_label']};"
                    f"source_right={b['right_config']}:{b['right_label']}"
                )
                manifest_rows.append(
                    {
                        "config_path": rel_config,
                        "sweep_axis": "phase3_stage2_boundary_refine",
                        "sweep_value": sweep_value,
                        "hypothesis": "boundary_refinement",
                        "seed": str(seed),
                        "stage": "confirmation",
                        "notes": notes,
                    }
                )
                seed += 1

    _write_csv(
        args.boundary_out,
        boundary_rows,
        [
            "boundary_id",
            "phase_profile",
            "topology",
            "sign",
            "left_strength",
            "right_strength",
            "left_label",
            "right_label",
            "left_config",
            "right_config",
        ],
    )
    _write_csv(
        args.manifest_out,
        manifest_rows,
        ["config_path", "sweep_axis", "sweep_value", "hypothesis", "seed", "stage", "notes"],
    )

    label_counts = dict(Counter(r["label"] for r in rows))
    print(f"analysis rows={len(rows)} boundaries={len(boundaries)}")
    print(f"label_counts={label_counts}")
    if not boundaries:
        print(
            "warning: no boundary intervals found from labels; "
            "consider rerunning phase3_prepare_analysis.py with --label-mode quantile"
        )
    print(f"wrote boundary table: {args.boundary_out}")
    print(f"wrote confirmation manifest rows={len(manifest_rows)}: {args.manifest_out}")


if __name__ == "__main__":
    main()
