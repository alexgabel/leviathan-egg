#!/usr/bin/env python3
"""Generate robustness verdict tables from Phase 2 analysis artifacts.

Primary use:
- quantify per-cell replication outcomes (for example reversal >=4/5)
- aggregate cell verdicts by boundary to support claim governance
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]

LABELS = ("egalitarian", "hierarchical", "reversal", "uncertain")
REPLICATE_SUFFIX_RE = re.compile(r"_r\d+$")
BOUNDARY_RE = re.compile(r"(?:^|_)(b\d{2})(?:_|$)")
ALPHA_RE = re.compile(r"(?:^|_)a(\d+)(?:_|$)")


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _cell_id_from_basename(config_basename: str) -> str:
    stem = Path(config_basename).stem
    if stem.endswith("_smoke"):
        stem = stem[:-6]
    return REPLICATE_SUFFIX_RE.sub("", stem)


def _majority_label(counts: Dict[str, int]) -> tuple[str, int]:
    ranked = sorted(
        counts.items(),
        key=lambda kv: (-kv[1], kv[0]),
    )
    return ranked[0]


def _boundary_id(cell_id: str) -> str:
    m = BOUNDARY_RE.search(cell_id)
    return m.group(1) if m else ""


def _alpha_from_cell(cell_id: str) -> str:
    m = ALPHA_RE.search(cell_id)
    if not m:
        return ""
    v = int(m.group(1))
    if v >= 100:
        return f"{v/1000.0:.3f}".rstrip("0").rstrip(".")
    return f"{v/100.0:.2f}".rstrip("0").rstrip(".")


def _build_cell_rows(
    *,
    analysis_rows: List[Dict[str, str]],
    target_label: str,
    min_successes: int,
    min_replicates: int,
    require_stage: str | None,
) -> List[Dict[str, str]]:
    grouped: Dict[str, Dict[str, object]] = {}

    for row in analysis_rows:
        if row.get("status") and row["status"] != "SUCCESS":
            continue
        if require_stage and row.get("stage") != require_stage:
            continue
        label = row.get("label", "")
        if label not in LABELS:
            continue

        config_basename = row.get("config_basename") or Path(row["config_path"]).name
        cell_id = _cell_id_from_basename(config_basename)
        group = grouped.setdefault(
            cell_id,
            {
                "cell_id": cell_id,
                "boundary_id": _boundary_id(cell_id),
                "alpha": _alpha_from_cell(cell_id),
                "counts": {k: 0 for k in LABELS},
                "config_examples": [],
            },
        )
        group["counts"][label] += 1  # type: ignore[index]
        if len(group["config_examples"]) < 3:  # type: ignore[index]
            group["config_examples"].append(config_basename)  # type: ignore[index]

    out: List[Dict[str, str]] = []
    for cell_id, g in grouped.items():
        counts: Dict[str, int] = g["counts"]  # type: ignore[assignment]
        n = sum(counts.values())
        maj_label, maj_count = _majority_label(counts)
        target_count = counts.get(target_label, 0)
        pass_target = int(n >= min_replicates and target_count >= min_successes)

        row = {
            "cell_id": cell_id,
            "boundary_id": str(g["boundary_id"]),
            "alpha": str(g["alpha"]),
            "n_replicates": str(n),
            "count_egalitarian": str(counts["egalitarian"]),
            "count_hierarchical": str(counts["hierarchical"]),
            "count_reversal": str(counts["reversal"]),
            "count_uncertain": str(counts["uncertain"]),
            "p_egalitarian": f"{(counts['egalitarian'] / n) if n else 0.0:.6f}",
            "p_hierarchical": f"{(counts['hierarchical'] / n) if n else 0.0:.6f}",
            "p_reversal": f"{(counts['reversal'] / n) if n else 0.0:.6f}",
            "p_uncertain": f"{(counts['uncertain'] / n) if n else 0.0:.6f}",
            "majority_label": maj_label,
            "majority_count": str(maj_count),
            "majority_fraction": f"{(maj_count / n) if n else 0.0:.6f}",
            "target_label": target_label,
            "target_count": str(target_count),
            "min_successes": str(min_successes),
            "min_replicates": str(min_replicates),
            "pass_target": str(pass_target),
            "example_configs": ";".join(g["config_examples"]),  # type: ignore[index]
        }
        out.append(row)

    out.sort(key=lambda r: (r["boundary_id"], r["alpha"], r["cell_id"]))
    return out


def _build_boundary_rows(
    *,
    cell_rows: List[Dict[str, str]],
    min_cells_passing_boundary: int,
) -> List[Dict[str, str]]:
    by_boundary: Dict[str, List[Dict[str, str]]] = {}
    for row in cell_rows:
        by_boundary.setdefault(row.get("boundary_id", ""), []).append(row)

    out: List[Dict[str, str]] = []
    for boundary_id, rows in sorted(by_boundary.items(), key=lambda kv: kv[0]):
        n_cells = len(rows)
        n_pass = sum(int(r["pass_target"]) for r in rows)
        alphas = sorted({r["alpha"] for r in rows if r["alpha"]})
        out.append(
            {
                "boundary_id": boundary_id,
                "n_cells": str(n_cells),
                "n_cells_passing_target": str(n_pass),
                "pass_fraction": f"{(n_pass / n_cells) if n_cells else 0.0:.6f}",
                "min_cells_passing_boundary": str(min_cells_passing_boundary),
                "boundary_pass": str(int(n_pass >= min_cells_passing_boundary)),
                "alphas": ";".join(alphas),
            }
        )

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 2 robustness verdict tables")
    parser.add_argument(
        "--analysis-csv",
        type=Path,
        required=True,
        help="Analysis table (for example analysis_latest_per_config_tau08.csv)",
    )
    parser.add_argument(
        "--cells-output",
        type=Path,
        default=None,
        help="Output CSV for per-cell verdicts",
    )
    parser.add_argument(
        "--boundaries-output",
        type=Path,
        default=None,
        help="Output CSV for boundary-level verdicts",
    )
    parser.add_argument(
        "--target-label",
        type=str,
        default="reversal",
        choices=LABELS,
        help="Label counted for robustness gating",
    )
    parser.add_argument(
        "--min-successes",
        type=int,
        default=4,
        help="Minimum target-label count to pass a cell",
    )
    parser.add_argument(
        "--min-replicates",
        type=int,
        default=5,
        help="Minimum replicate count required to evaluate a cell",
    )
    parser.add_argument(
        "--min-cells-passing-boundary",
        type=int,
        default=1,
        help="Boundary-level pass threshold on number of passing cells",
    )
    parser.add_argument(
        "--require-stage",
        type=str,
        default="confirmation",
        help="If set, only rows with this stage are used",
    )
    args = parser.parse_args()

    cells_output = (
        args.cells_output
        if args.cells_output is not None
        else args.analysis_csv.with_name("robustness_cells.csv")
    )
    boundaries_output = (
        args.boundaries_output
        if args.boundaries_output is not None
        else args.analysis_csv.with_name("robustness_boundaries.csv")
    )

    analysis_rows = _read_csv(args.analysis_csv)
    cell_rows = _build_cell_rows(
        analysis_rows=analysis_rows,
        target_label=args.target_label,
        min_successes=args.min_successes,
        min_replicates=args.min_replicates,
        require_stage=args.require_stage if args.require_stage else None,
    )
    if not cell_rows:
        raise ValueError("No evaluable cells found; check input analysis CSV and stage filter.")

    boundary_rows = _build_boundary_rows(
        cell_rows=cell_rows,
        min_cells_passing_boundary=args.min_cells_passing_boundary,
    )

    _write_csv(
        cells_output,
        cell_rows,
        [
            "cell_id",
            "boundary_id",
            "alpha",
            "n_replicates",
            "count_egalitarian",
            "count_hierarchical",
            "count_reversal",
            "count_uncertain",
            "p_egalitarian",
            "p_hierarchical",
            "p_reversal",
            "p_uncertain",
            "majority_label",
            "majority_count",
            "majority_fraction",
            "target_label",
            "target_count",
            "min_successes",
            "min_replicates",
            "pass_target",
            "example_configs",
        ],
    )
    _write_csv(
        boundaries_output,
        boundary_rows,
        [
            "boundary_id",
            "n_cells",
            "n_cells_passing_target",
            "pass_fraction",
            "min_cells_passing_boundary",
            "boundary_pass",
            "alphas",
        ],
    )

    n_cells = len(cell_rows)
    n_cell_pass = sum(int(r["pass_target"]) for r in cell_rows)
    n_boundaries = len(boundary_rows)
    n_boundary_pass = sum(int(r["boundary_pass"]) for r in boundary_rows)
    print(f"Cells: {n_cells}, pass_target={n_cell_pass}")
    print(f"Boundaries: {n_boundaries}, boundary_pass={n_boundary_pass}")
    print(f"Wrote cell verdicts: {cells_output}")
    print(f"Wrote boundary verdicts: {boundaries_output}")


if __name__ == "__main__":
    main()
