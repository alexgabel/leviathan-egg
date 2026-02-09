#!/usr/bin/env python3
"""Generate near-crossing refinement confirmation configs for Phase 2.

This script creates a reusable "final robustness" refinement batch:
- selects boundary rows (optionally auto-filtered from transition summary)
- interpolates between boundary endpoint configs at chosen alphas
- emits replicate-seed configs and a runnable manifest
"""

from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[1]
PHASE2_DIR = ROOT / "experiments" / "configs" / "phase2"


def _parse_alphas(alpha_str: str) -> List[float]:
    values: List[float] = []
    for token in alpha_str.split(","):
        token = token.strip()
        if not token:
            continue
        value = float(token)
        if value < 0.0 or value > 1.0:
            raise ValueError(f"alpha must be in [0,1], got: {value}")
        values.append(value)
    if not values:
        raise ValueError("No alpha values provided")
    return sorted(set(round(v, 6) for v in values))


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _resolve_config(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return ROOT / p


def _load_yaml(path: Path) -> Dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, data: Dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _boundary_id(index_1based: int) -> str:
    return f"b{index_1based:02d}"


def _crossing_boundaries_from_summary(
    summary_rows: List[Dict[str, str]],
) -> Dict[str, Dict[str, float]]:
    """Return boundary_id -> crossing stats if summary straddles 0.5."""
    by_boundary: Dict[str, List[Dict[str, str]]] = {}
    for row in summary_rows:
        by_boundary.setdefault(row["boundary_id"], []).append(row)

    selected: Dict[str, Dict[str, float]] = {}
    for bid, rows in by_boundary.items():
        pts = sorted(
            ((float(r["alpha"]), float(r["p_reversal"])) for r in rows),
            key=lambda t: t[0],
        )
        rev_side = [a for a, p in pts if p > 0.5]
        hier_side = [a for a, p in pts if p < 0.5]
        if not rev_side or not hier_side:
            continue
        low = max(rev_side)
        high = min(hier_side)
        if low >= high:
            continue
        selected[bid] = {
            "low": low,
            "high": high,
            "mid": round((low + high) / 2.0, 6),
        }
    return selected


def _format_alpha_tag(alpha: float) -> str:
    return f"a{int(round(alpha * 100)):02d}"


def _interp(left_value: float, right_value: float, alpha: float) -> float:
    return (1.0 - alpha) * left_value + alpha * right_value


def _build_refined(
    *,
    boundary_rows: List[Dict[str, str]],
    selected_boundary_ids: set[str],
    alphas: List[float],
    replicate_count: int,
    seed_base: int,
    out_manifest: Path,
    config_prefix: str,
    threshold_profile_note: str,
) -> int:
    manifest_rows: List[Dict[str, str]] = []
    seed = seed_base
    generated = 0

    for old in PHASE2_DIR.glob(f"{config_prefix}_*.yaml"):
        old.unlink()

    for idx, boundary in enumerate(boundary_rows, start=1):
        bid = _boundary_id(idx)
        if bid not in selected_boundary_ids:
            continue

        left_path = _resolve_config(boundary["left_config_path"])
        right_path = _resolve_config(boundary["right_config_path"])
        left = _load_yaml(left_path)
        right = _load_yaml(right_path)

        for alpha in alphas:
            base = deepcopy(left)

            for key in ("violence_factor", "information_spread_rate", "memory_decay"):
                lv = float(left["authority_and_power"][key])
                rv = float(right["authority_and_power"][key])
                if abs(lv - rv) > 1e-12:
                    base["authority_and_power"][key] = round(_interp(lv, rv, alpha), 6)

            for key in (
                "aggregation_benefit",
                "coordination_cost",
                "hierarchy_rent",
                "crisis",
                "festival",
            ):
                lv = float(left["seasonality"]["forcing_amplitudes"][key])
                rv = float(right["seasonality"]["forcing_amplitudes"][key])
                if abs(lv - rv) > 1e-12:
                    base["seasonality"]["forcing_amplitudes"][key] = round(
                        _interp(lv, rv, alpha), 6
                    )

            lv_sign = int(left["seasonality"]["forcing_sign"]["authority_coupling"])
            rv_sign = int(right["seasonality"]["forcing_sign"]["authority_coupling"])
            if lv_sign != rv_sign:
                base["seasonality"]["forcing_sign"]["authority_coupling"] = (
                    rv_sign if alpha >= 0.5 else lv_sign
                )

            alpha_tag = _format_alpha_tag(alpha)

            for rep in range(1, replicate_count + 1):
                run_seed = seed
                seed += 1

                name = (
                    f"{config_prefix}_{bid}_sp-{boundary['seasonal_profile']}"
                    f"_f-{boundary['festival']}_bd-{boundary['boundary_dim']}"
                    f"_{alpha_tag}_r{rep}"
                )
                cfg = deepcopy(base)
                cfg["experiment_name"] = name
                cfg["description"] = (
                    "Phase 2 confirmation near-crossing refinement: "
                    f"boundary={bid}, dim={boundary['boundary_dim']}, alpha={alpha:.2f}, rep={rep}."
                )
                cfg["date_created"] = str(date.today())
                cfg["runtime_and_reproducibility"]["random_seed"] = int(run_seed)

                out_cfg = PHASE2_DIR / f"{name}.yaml"
                _write_yaml(out_cfg, cfg)

                manifest_rows.append(
                    {
                        "config_path": f"experiments/configs/phase2/{out_cfg.name}",
                        "sweep_axis": "confirmation_refine_near_crossing",
                        "sweep_value": (
                            f"boundary_id={bid};dim={boundary['boundary_dim']};alpha={alpha:.2f};"
                            f"source_left={left_path.name};source_right={right_path.name}"
                        ),
                        "hypothesis": "transition_refinement",
                        "seed": str(run_seed),
                        "stage": "confirmation",
                        "notes": (
                            "near_crossing_refinement;"
                            f"threshold_profile={threshold_profile_note};"
                            f"left_label={boundary['left_label']};right_label={boundary['right_label']}"
                        ),
                    }
                )
                generated += 1

    fieldnames = [
        "config_path",
        "sweep_axis",
        "sweep_value",
        "hypothesis",
        "seed",
        "stage",
        "notes",
    ]
    _write_csv(out_manifest, manifest_rows, fieldnames)
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate near-crossing refinement configs + manifest for Phase 2"
    )
    parser.add_argument(
        "--boundary-csv",
        type=Path,
        default=PHASE2_DIR / "boundary_cells_auto_tau08.csv",
        help="Boundary cell table (left/right config pairs)",
    )
    parser.add_argument(
        "--transition-summary",
        type=Path,
        default=ROOT
        / "experiments"
        / "runs"
        / "phase2"
        / "confirmation_dense_tau08"
        / "transition_summary_tau08.csv",
        help="Optional summary CSV to auto-select crossing boundaries",
    )
    parser.add_argument(
        "--alphas",
        type=str,
        default="0.45,0.50,0.55",
        help="Comma-separated interpolation alphas for refinement",
    )
    parser.add_argument(
        "--replicates",
        type=int,
        default=5,
        help="Replicates per refined alpha per boundary",
    )
    parser.add_argument(
        "--seed-base",
        type=int,
        default=6101,
        help="Starting seed for generated refinement configs",
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=PHASE2_DIR / "manifest_confirmation_refine.csv",
        help="Output confirmation manifest",
    )
    parser.add_argument(
        "--config-prefix",
        type=str,
        default="phase2r_tau08",
        help="Generated config filename prefix",
    )
    parser.add_argument(
        "--threshold-profile-note",
        type=str,
        default="regime_thresholds_tau08_sensitivity.yaml",
        help="Manifest note metadata for threshold profile",
    )
    args = parser.parse_args()

    boundary_rows = _read_csv(args.boundary_csv)
    if not boundary_rows:
        raise ValueError(f"No boundary rows found: {args.boundary_csv}")

    selected_ids: set[str]
    if args.transition_summary.exists():
        summary_rows = _read_csv(args.transition_summary)
        selected = _crossing_boundaries_from_summary(summary_rows)
        selected_ids = set(selected.keys())
        if not selected_ids:
            raise ValueError(
                "No crossing boundaries detected in transition summary. "
                "Provide a valid summary or edit alphas/boundaries."
            )
    else:
        selected_ids = {_boundary_id(i) for i in range(1, len(boundary_rows) + 1)}

    alphas = _parse_alphas(args.alphas)
    generated = _build_refined(
        boundary_rows=boundary_rows,
        selected_boundary_ids=selected_ids,
        alphas=alphas,
        replicate_count=args.replicates,
        seed_base=args.seed_base,
        out_manifest=args.manifest_out,
        config_prefix=args.config_prefix,
        threshold_profile_note=args.threshold_profile_note,
    )

    print(f"Selected boundary ids: {sorted(selected_ids)}")
    print(f"Alphas: {alphas}")
    print(f"Wrote {generated} refinement configs to: {PHASE2_DIR}")
    print(f"Wrote refinement manifest: {args.manifest_out}")


if __name__ == "__main__":
    main()
