#!/usr/bin/env python3
"""Generate Stage-2 confirmation configs from Stage-1 analysis artifacts.

Workflow:
1) Read Stage-1 analysis labels (typically tau=0.8 sensitivity table).
2) Derive left/right boundary pairs programmatically.
3) Write boundary table for auditability.
4) Generate replicate-seed confirmation configs + manifest from derived cells.
"""

from __future__ import annotations

import argparse
import csv
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[1]
PHASE2_DIR = ROOT / "experiments" / "configs" / "phase2"

CONFIG_BASENAME_RE = re.compile(
    r"^phase2x_sp-(?P<seasonal_profile>.+?)_v-(?P<violence>.+?)_l-(?P<lockin>.+?)_f-(?P<festival>.+?)\.yaml$"
)


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _resolve_config_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return ROOT / p


def _parse_basename(config_basename: str) -> Dict[str, str]:
    m = CONFIG_BASENAME_RE.match(config_basename)
    if not m:
        raise ValueError(f"Unrecognized exploration config basename: {config_basename}")
    return {
        "seasonal_profile": m.group("seasonal_profile"),
        "violence": m.group("violence"),
        "lockin": m.group("lockin"),
        "festival": m.group("festival"),
    }


def _parse_csv_tokens(token_str: str) -> set[str]:
    return {tok.strip() for tok in token_str.split(",") if tok.strip()}


def _load_labeled_cells(
    *,
    analysis_csv: Path,
    left_label: str,
    right_label: str,
    seasonal_profiles: set[str] | None,
    require_stage: str | None,
) -> Dict[Tuple[str, str, str, str], Dict[str, str]]:
    rows = _read_csv(analysis_csv)
    cells: Dict[Tuple[str, str, str, str], Dict[str, str]] = {}

    for row in rows:
        if row.get("status") and row["status"] != "SUCCESS":
            continue
        if require_stage and row.get("stage") != require_stage:
            continue

        label = row.get("label", "")
        if label not in {left_label, right_label}:
            continue

        config_basename = row.get("config_basename") or Path(row["config_path"]).name
        factors = _parse_basename(config_basename)
        if seasonal_profiles is not None and factors["seasonal_profile"] not in seasonal_profiles:
            continue

        key = (
            factors["seasonal_profile"],
            factors["violence"],
            factors["lockin"],
            factors["festival"],
        )
        existing = cells.get(key)
        if existing is not None and existing.get("end_time", "") >= row.get("end_time", ""):
            continue

        cells[key] = {
            "label": label,
            "config_path": str(_resolve_config_path(row["config_path"])),
            "config_basename": config_basename,
            "run_id": row.get("run_id", ""),
            "confidence": row.get("confidence", ""),
            "end_time": row.get("end_time", ""),
            "seasonal_profile": factors["seasonal_profile"],
            "violence": factors["violence"],
            "lockin": factors["lockin"],
            "festival": factors["festival"],
        }

    if not cells:
        raise ValueError(
            f"No labeled cells found in {analysis_csv} "
            f"(labels={left_label}/{right_label}, stage={require_stage or 'any'})."
        )
    return cells


def _derive_boundaries(
    *,
    cells: Dict[Tuple[str, str, str, str], Dict[str, str]],
    left_label: str,
    right_label: str,
) -> List[Dict[str, str]]:
    items = list(cells.values())
    dedup_keys: set[Tuple[str, str, str]] = set()
    boundaries: List[Dict[str, str]] = []

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a = items[i]
            b = items[j]

            if a["seasonal_profile"] != b["seasonal_profile"]:
                continue
            if a["festival"] != b["festival"]:
                continue

            diff_violence = a["violence"] != b["violence"]
            diff_lockin = a["lockin"] != b["lockin"]
            if diff_violence == diff_lockin:
                continue

            if {a["label"], b["label"]} != {left_label, right_label}:
                continue

            boundary_dim = "violence" if diff_violence else "lockin"
            left = a if a["label"] == left_label else b
            right = b if left is a else a

            dedup = (left["config_path"], right["config_path"], boundary_dim)
            if dedup in dedup_keys:
                continue
            dedup_keys.add(dedup)

            boundaries.append(
                {
                    "left_config_path": left["config_path"],
                    "right_config_path": right["config_path"],
                    "left_label": left["label"],
                    "right_label": right["label"],
                    "boundary_dim": boundary_dim,
                    "seasonal_profile": left["seasonal_profile"],
                    "violence": "mixed" if diff_violence else left["violence"],
                    "lockin": "mixed" if diff_lockin else left["lockin"],
                    "festival": left["festival"],
                    "left_config_basename": left["config_basename"],
                    "right_config_basename": right["config_basename"],
                    "left_run_id": left["run_id"],
                    "right_run_id": right["run_id"],
                    "left_confidence": left["confidence"],
                    "right_confidence": right["confidence"],
                    "left_end_time": left["end_time"],
                    "right_end_time": right["end_time"],
                }
            )

    boundaries.sort(
        key=lambda r: (
            r["seasonal_profile"],
            r["festival"],
            r["boundary_dim"],
            r["left_config_basename"],
            r["right_config_basename"],
        )
    )
    if not boundaries:
        raise ValueError(
            f"No boundaries derived for labels {left_label}/{right_label}. "
            "Try loosening seasonal profile filters."
        )
    return boundaries


def _boundary_id(idx_1based: int) -> str:
    return f"b{idx_1based:02d}"


def _source_cells_from_boundaries(
    boundaries: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    by_path: Dict[str, Dict[str, str]] = {}

    for idx, b in enumerate(boundaries, start=1):
        bid = _boundary_id(idx)
        for side in ("left", "right"):
            path = b[f"{side}_config_path"]
            label = b[f"{side}_label"]
            basename = b[f"{side}_config_basename"]
            row = by_path.get(path)
            if row is None:
                by_path[path] = {
                    "config_path": path,
                    "config_basename": basename,
                    "label": label,
                    "boundary_ids": bid,
                }
            else:
                seen = {x for x in row["boundary_ids"].split(";") if x}
                if bid not in seen:
                    row["boundary_ids"] = f"{row['boundary_ids']};{bid}"

    return sorted(by_path.values(), key=lambda r: r["config_basename"])


def _load_yaml(path: Path) -> Dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, cfg: Dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def _write_boundary_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    fieldnames = [
        "left_config_path",
        "right_config_path",
        "left_label",
        "right_label",
        "boundary_dim",
        "seasonal_profile",
        "violence",
        "lockin",
        "festival",
        "left_config_basename",
        "right_config_basename",
        "left_run_id",
        "right_run_id",
        "left_confidence",
        "right_confidence",
        "left_end_time",
        "right_end_time",
    ]
    _write_csv(path, rows, fieldnames)


def _generate_confirmation(
    *,
    source_cells: List[Dict[str, str]],
    manifest_out: Path,
    config_prefix: str,
    replicates: int,
    seed_base: int,
    left_label: str,
    right_label: str,
    left_hypothesis: str,
    right_hypothesis: str,
    sweep_axis: str,
    threshold_profile_note: str,
    analysis_csv: Path,
) -> int:
    for old in PHASE2_DIR.glob(f"{config_prefix}_*.yaml"):
        old.unlink()

    manifest_rows: List[Dict[str, str]] = []
    seed = seed_base

    for src in source_cells:
        source_path = Path(src["config_path"])
        source_cfg = _load_yaml(source_path)
        source_stem = source_path.stem
        cell_id = source_stem.replace("phase2x_", "")

        if src["label"] == left_label:
            hypothesis = left_hypothesis
        elif src["label"] == right_label:
            hypothesis = right_hypothesis
        else:
            hypothesis = "boundary_source"

        for rep in range(1, replicates + 1):
            run_seed = seed
            seed += 1

            cfg = deepcopy(source_cfg)
            cfg_name = f"{config_prefix}_{cell_id}_r{rep}"
            cfg["experiment_name"] = cfg_name
            cfg["description"] = (
                "Phase 2 confirmation run from artifact-derived boundary sources: "
                f"source_cell={source_stem}, source_label={src['label']}, "
                f"replicate={rep}, seed={run_seed}."
            )
            cfg["date_created"] = str(date.today())
            cfg["runtime_and_reproducibility"]["random_seed"] = int(run_seed)

            out_path = PHASE2_DIR / f"{cfg_name}.yaml"
            _write_yaml(out_path, cfg)

            manifest_rows.append(
                {
                    "config_path": f"experiments/configs/phase2/{out_path.name}",
                    "sweep_axis": sweep_axis,
                    "sweep_value": (
                        f"source_cell={source_stem};replicate={rep};"
                        f"source_label={src['label']};boundary_ids={src['boundary_ids']}"
                    ),
                    "hypothesis": hypothesis,
                    "seed": str(run_seed),
                    "stage": "confirmation",
                    "notes": (
                        "artifact_derived_boundary_selection;"
                        f"analysis_csv={analysis_csv.name};"
                        f"threshold_profile={threshold_profile_note};"
                        f"source_config={source_path.name}"
                    ),
                }
            )

    fieldnames = [
        "config_path",
        "sweep_axis",
        "sweep_value",
        "hypothesis",
        "seed",
        "stage",
        "notes",
    ]
    _write_csv(manifest_out, manifest_rows, fieldnames)
    return len(manifest_rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate confirmation manifest/configs from Stage-1 analysis artifacts."
    )
    parser.add_argument(
        "--analysis-csv",
        type=Path,
        default=ROOT
        / "experiments"
        / "runs"
        / "phase2"
        / "recenter_full"
        / "analysis_latest_per_config_tau08_sensitivity.csv",
        help="Stage-1 analysis table used for boundary derivation",
    )
    parser.add_argument(
        "--boundary-csv-out",
        type=Path,
        default=PHASE2_DIR / "boundary_cells_auto_tau08.csv",
        help="Output path for derived boundary table",
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        default=PHASE2_DIR / "manifest_confirmation.csv",
        help="Output confirmation manifest path",
    )
    parser.add_argument(
        "--config-prefix",
        type=str,
        default="phase2c_tau08",
        help="Prefix for generated confirmation config names",
    )
    parser.add_argument(
        "--seasonal-profiles",
        type=str,
        default="anti_strong",
        help="Comma-separated seasonal profiles to consider; '*' means all",
    )
    parser.add_argument(
        "--left-label",
        type=str,
        default="reversal",
        help="Label considered as left side of boundary",
    )
    parser.add_argument(
        "--right-label",
        type=str,
        default="hierarchical",
        help="Label considered as right side of boundary",
    )
    parser.add_argument(
        "--left-hypothesis",
        type=str,
        default="reversal_candidate",
        help="Manifest hypothesis for left-label source cells",
    )
    parser.add_argument(
        "--right-hypothesis",
        type=str,
        default="hierarchical_anchor",
        help="Manifest hypothesis for right-label source cells",
    )
    parser.add_argument(
        "--replicates",
        type=int,
        default=5,
        help="Replicate count per source cell",
    )
    parser.add_argument(
        "--seed-base",
        type=int,
        default=4101,
        help="Starting seed for generated confirmation configs",
    )
    parser.add_argument(
        "--sweep-axis",
        type=str,
        default="confirmation_boundary_tau08",
        help="sweep_axis value written to confirmation manifest",
    )
    parser.add_argument(
        "--threshold-profile-note",
        type=str,
        default="regime_thresholds_tau08_sensitivity.yaml",
        help="Threshold-profile note recorded in manifest metadata",
    )
    parser.add_argument(
        "--require-stage",
        type=str,
        default="exploration",
        help="If set, only rows with this stage are used",
    )
    args = parser.parse_args()

    seasonal_profiles = None
    if args.seasonal_profiles.strip() != "*":
        seasonal_profiles = _parse_csv_tokens(args.seasonal_profiles)

    cells = _load_labeled_cells(
        analysis_csv=args.analysis_csv,
        left_label=args.left_label,
        right_label=args.right_label,
        seasonal_profiles=seasonal_profiles,
        require_stage=args.require_stage if args.require_stage else None,
    )
    boundaries = _derive_boundaries(
        cells=cells,
        left_label=args.left_label,
        right_label=args.right_label,
    )
    _write_boundary_csv(args.boundary_csv_out, boundaries)

    source_cells = _source_cells_from_boundaries(boundaries)
    manifest_count = _generate_confirmation(
        source_cells=source_cells,
        manifest_out=args.manifest_out,
        config_prefix=args.config_prefix,
        replicates=args.replicates,
        seed_base=args.seed_base,
        left_label=args.left_label,
        right_label=args.right_label,
        left_hypothesis=args.left_hypothesis,
        right_hypothesis=args.right_hypothesis,
        sweep_axis=args.sweep_axis,
        threshold_profile_note=args.threshold_profile_note,
        analysis_csv=args.analysis_csv,
    )

    print(f"Analysis rows retained as labeled cells: {len(cells)}")
    print(f"Derived boundaries: {len(boundaries)}")
    for idx, b in enumerate(boundaries, start=1):
        print(
            f"  - {_boundary_id(idx)} {b['boundary_dim']} "
            f"{b['left_config_basename']} ({b['left_label']}) -> "
            f"{b['right_config_basename']} ({b['right_label']})"
        )
    print(f"Source cells selected: {len(source_cells)}")
    print(f"Wrote boundary table: {args.boundary_csv_out}")
    print(f"Wrote confirmation rows: {manifest_count}")
    print(f"Wrote confirmation manifest: {args.manifest_out}")


if __name__ == "__main__":
    main()
