#!/usr/bin/env python3
"""Build Stage-2 phase-diagram figure inputs from robustness verdict tables.

Inputs:
- robustness_cells_*.csv
- robustness_boundaries_*.csv (optional)

Outputs:
- stage2_probability_map_*.csv
- stage2_uncertainty_overlay_*.csv
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from pathlib import Path
from typing import Dict, List


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _to_float(value: str) -> float:
    if value == "":
        return 0.0
    return float(value)


def _entropy_bits(probs: List[float]) -> float:
    ent = 0.0
    for p in probs:
        if p > 0.0:
            ent -= p * math.log2(p)
    return ent


def _sort_key(row: Dict[str, str]) -> tuple[str, float, str]:
    alpha = row.get("alpha", "")
    alpha_num = float(alpha) if alpha else -1.0
    return (row.get("boundary_id", ""), alpha_num, row.get("cell_id", ""))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Stage-2 probability/uncertainty figure input CSVs."
    )
    parser.add_argument(
        "--cells-csv",
        type=Path,
        required=True,
        help="Per-cell robustness verdict table",
    )
    parser.add_argument(
        "--boundaries-csv",
        type=Path,
        default=None,
        help="Boundary verdict table (optional; used to attach boundary_pass)",
    )
    parser.add_argument(
        "--probability-output",
        type=Path,
        default=None,
        help="Output CSV for probability map input",
    )
    parser.add_argument(
        "--uncertainty-output",
        type=Path,
        default=None,
        help="Output CSV for uncertainty overlay input",
    )
    args = parser.parse_args()

    cells_rows = _read_csv(args.cells_csv)
    if not cells_rows:
        raise ValueError(f"No rows found in cells table: {args.cells_csv}")

    boundaries_rows = _read_csv(args.boundaries_csv) if args.boundaries_csv else []
    boundary_pass_by_id = {r["boundary_id"]: r.get("boundary_pass", "") for r in boundaries_rows}

    probability_output = (
        args.probability_output
        if args.probability_output is not None
        else args.cells_csv.with_name("stage2_probability_map.csv")
    )
    uncertainty_output = (
        args.uncertainty_output
        if args.uncertainty_output is not None
        else args.cells_csv.with_name("stage2_uncertainty_overlay.csv")
    )

    probability_rows: List[Dict[str, str]] = []
    uncertainty_rows: List[Dict[str, str]] = []

    for row in cells_rows:
        boundary_id = row.get("boundary_id", "")
        p_egalitarian = _to_float(row.get("p_egalitarian", ""))
        p_hierarchical = _to_float(row.get("p_hierarchical", ""))
        p_reversal = _to_float(row.get("p_reversal", ""))
        p_uncertain = _to_float(row.get("p_uncertain", ""))
        probs = [p_egalitarian, p_hierarchical, p_reversal, p_uncertain]

        entropy_bits = _entropy_bits(probs)
        entropy_norm = entropy_bits / math.log2(4.0)
        discord = 1.0 - max(probs)

        base = {
            "cell_id": row.get("cell_id", ""),
            "boundary_id": boundary_id,
            "alpha": row.get("alpha", ""),
            "n_replicates": row.get("n_replicates", ""),
            "majority_label": row.get("majority_label", ""),
            "majority_fraction": row.get("majority_fraction", ""),
            "target_label": row.get("target_label", ""),
            "target_count": row.get("target_count", ""),
            "pass_target": row.get("pass_target", ""),
            "boundary_pass": boundary_pass_by_id.get(boundary_id, ""),
            "p_egalitarian": f"{p_egalitarian:.6f}",
            "p_hierarchical": f"{p_hierarchical:.6f}",
            "p_reversal": f"{p_reversal:.6f}",
            "p_uncertain": f"{p_uncertain:.6f}",
        }
        probability_rows.append(base)

        uncertainty_row = dict(base)
        uncertainty_row["entropy_bits"] = f"{entropy_bits:.6f}"
        uncertainty_row["entropy_normalized"] = f"{entropy_norm:.6f}"
        uncertainty_row["discord"] = f"{discord:.6f}"
        uncertainty_rows.append(uncertainty_row)

    probability_rows.sort(key=_sort_key)
    uncertainty_rows.sort(key=_sort_key)

    _write_csv(
        probability_output,
        probability_rows,
        [
            "cell_id",
            "boundary_id",
            "alpha",
            "n_replicates",
            "majority_label",
            "majority_fraction",
            "target_label",
            "target_count",
            "pass_target",
            "boundary_pass",
            "p_egalitarian",
            "p_hierarchical",
            "p_reversal",
            "p_uncertain",
        ],
    )

    _write_csv(
        uncertainty_output,
        uncertainty_rows,
        [
            "cell_id",
            "boundary_id",
            "alpha",
            "n_replicates",
            "majority_label",
            "majority_fraction",
            "target_label",
            "target_count",
            "pass_target",
            "boundary_pass",
            "p_egalitarian",
            "p_hierarchical",
            "p_reversal",
            "p_uncertain",
            "entropy_bits",
            "entropy_normalized",
            "discord",
        ],
    )

    print(f"Input cells: {len(cells_rows)}")
    print(
        "Majority labels:",
        dict(Counter(r.get("majority_label", "") for r in probability_rows)),
    )
    print(f"Wrote probability input: {probability_output}")
    print(f"Wrote uncertainty input: {uncertainty_output}")


if __name__ == "__main__":
    main()
