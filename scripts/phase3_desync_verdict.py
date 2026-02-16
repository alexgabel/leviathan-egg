#!/usr/bin/env python3
"""Aggregate Phase-3 desync refinement analysis into cell-level verdict tables."""

from __future__ import annotations

import argparse
import csv
import hashlib
from datetime import datetime, timezone
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MIN_ANTIPHASE_MEAN = 0.5


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _parse_kv(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for token in text.split(";"):
        token = token.strip()
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _read_yaml(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping YAML at {path}, got {type(data).__name__}")
    return data


def _write_yaml(path: Path, data: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase-3 desync verdict table generator")
    parser.add_argument(
        "--analysis-csv",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine" / "analysis_latest_per_config.csv",
    )
    parser.add_argument(
        "--cells-output",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine" / "desync_cells.csv",
    )
    parser.add_argument(
        "--robust-output",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine" / "desync_robust_cells.csv",
    )
    parser.add_argument(
        "--target-label",
        type=str,
        default="desynchrony",
    )
    parser.add_argument(
        "--threshold-profile",
        type=Path,
        default=None,
        help="Optional YAML profile for classifier thresholds (reads desync_antiphase_lo)",
    )
    parser.add_argument(
        "--min-target-fraction",
        type=float,
        default=0.8,
        help="Minimum target-label fraction in a cell for robust pass",
    )
    parser.add_argument(
        "--min-replicates",
        type=int,
        default=8,
    )
    parser.add_argument(
        "--min-antiphase-mean",
        type=float,
        default=None,
        help="Additional anti-phase gate for robust pass (overrides profile/default when set)",
    )
    parser.add_argument(
        "--meta-output",
        type=Path,
        default=None,
        help="YAML metadata output with resolved gates used for this verdict",
    )
    args = parser.parse_args()

    profile_data: Dict[str, object] = {}
    if args.threshold_profile is not None:
        profile_data = _read_yaml(args.threshold_profile)

    min_antiphase_source = "default"
    if args.min_antiphase_mean is not None:
        min_antiphase_mean = float(args.min_antiphase_mean)
        min_antiphase_source = "cli_override"
    elif profile_data:
        if "desync_antiphase_lo" not in profile_data:
            raise KeyError(
                f"Missing 'desync_antiphase_lo' in threshold profile: {args.threshold_profile}"
            )
        min_antiphase_mean = float(profile_data["desync_antiphase_lo"])
        min_antiphase_source = "threshold_profile.desync_antiphase_lo"
    else:
        min_antiphase_mean = DEFAULT_MIN_ANTIPHASE_MEAN

    rows = _read_csv(args.analysis_csv)
    groups: Dict[tuple[str, str, str], List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        kv = _parse_kv(row.get("sweep_value", ""))
        mode = kv.get("mode", "")
        lag_steps = kv.get("lag_steps", "")
        strength = kv.get("strength", row.get("strength", ""))
        groups[(mode, lag_steps, strength)].append(row)

    cell_rows: List[Dict[str, str]] = []
    robust_rows: List[Dict[str, str]] = []
    for (mode, lag_steps, strength), cell in sorted(
        groups.items(), key=lambda x: (x[0][0], float(x[0][1]), float(x[0][2]))
    ):
        counts = Counter(r["label"] for r in cell)
        n = len(cell)
        p_target = counts.get(args.target_label, 0) / n if n else 0.0
        p_boundary = counts.get("boundary", 0) / n if n else 0.0
        p_sync = counts.get("synchrony", 0) / n if n else 0.0

        anti_vals = [
            float(r["sync_antiphase_mean"])
            for r in cell
            if r.get("sync_antiphase_mean", "") not in ("", "nan")
        ]
        anti_mean = sum(anti_vals) / len(anti_vals) if anti_vals else float("nan")
        lag_mean = sum(float(r["sync_lag_mean"]) for r in cell) / n if n else float("nan")
        order_mean = sum(float(r["sync_order_mean"]) for r in cell) / n if n else float("nan")
        lock_mean = sum(float(r["sync_lock_mean"]) for r in cell) / n if n else float("nan")

        pass_target = (
            n >= args.min_replicates
            and p_target >= args.min_target_fraction
            and anti_vals
            and anti_mean >= min_antiphase_mean
        )

        out = {
            "mode": mode,
            "lag_steps": lag_steps,
            "strength": strength,
            "n": str(n),
            "count_synchrony": str(counts.get("synchrony", 0)),
            "count_boundary": str(counts.get("boundary", 0)),
            "count_desynchrony": str(counts.get("desynchrony", 0)),
            "p_synchrony": f"{p_sync:.6f}",
            "p_boundary": f"{p_boundary:.6f}",
            "p_desynchrony": f"{p_target:.6f}",
            "sync_order_mean": f"{order_mean:.6f}",
            "sync_lock_mean": f"{lock_mean:.6f}",
            "sync_lag_mean": f"{lag_mean:.6f}",
            "sync_antiphase_mean": (
                f"{anti_mean:.6f}" if anti_vals else ""
            ),
            "robust_target_pass": "1" if pass_target else "0",
        }
        cell_rows.append(out)
        if pass_target:
            robust_rows.append(out)

    _write_csv(
        args.cells_output,
        cell_rows,
        [
            "mode",
            "lag_steps",
            "strength",
            "n",
            "count_synchrony",
            "count_boundary",
            "count_desynchrony",
            "p_synchrony",
            "p_boundary",
            "p_desynchrony",
            "sync_order_mean",
            "sync_lock_mean",
            "sync_lag_mean",
            "sync_antiphase_mean",
            "robust_target_pass",
        ],
    )
    _write_csv(
        args.robust_output,
        robust_rows,
        [
            "mode",
            "lag_steps",
            "strength",
            "n",
            "count_synchrony",
            "count_boundary",
            "count_desynchrony",
            "p_synchrony",
            "p_boundary",
            "p_desynchrony",
            "sync_order_mean",
            "sync_lock_mean",
            "sync_lag_mean",
            "sync_antiphase_mean",
            "robust_target_pass",
        ],
    )

    meta_output = args.meta_output or args.cells_output.with_name("verdict_meta.yaml")
    threshold_profile_path = str(args.threshold_profile) if args.threshold_profile else ""
    threshold_profile_sha256 = _sha256_file(args.threshold_profile) if args.threshold_profile else ""
    analysis_input_path = str(args.analysis_csv)
    analysis_input_sha256 = _sha256_file(args.analysis_csv)
    resolved_gates = {
        "target_label": args.target_label,
        "min_target_fraction": args.min_target_fraction,
        "min_replicates": args.min_replicates,
        "min_antiphase_mean": min_antiphase_mean,
        "min_antiphase_source": min_antiphase_source,
    }
    meta_payload: Dict[str, object] = {
        "schema_version": "1.0",
        "tool": "phase3_desync_verdict.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_input_path": analysis_input_path,
        "analysis_input_sha256": analysis_input_sha256,
        "threshold_profile_path": threshold_profile_path,
        "threshold_profile_sha256": threshold_profile_sha256,
        "resolved_gates": resolved_gates,
        "inputs": {
            "analysis_csv": analysis_input_path,
            "analysis_csv_sha256": analysis_input_sha256,
            "threshold_profile": threshold_profile_path,
            "threshold_profile_sha256": threshold_profile_sha256,
        },
        "gates": dict(resolved_gates),
        "outputs": {
            "cells_output": str(args.cells_output),
            "robust_output": str(args.robust_output),
        },
        "counts": {
            "cells": len(cell_rows),
            "robust_pass": len(robust_rows),
        },
    }
    if profile_data:
        meta_payload["threshold_profile_fields"] = {
            "schema_version": profile_data.get("schema_version", ""),
            "profile": profile_data.get("profile", ""),
            "desync_logic": profile_data.get("desync_logic", ""),
            "desync_antiphase_lo": profile_data.get("desync_antiphase_lo", ""),
        }
    _write_yaml(meta_output, meta_payload)

    print(f"cells={len(cell_rows)} robust_pass={len(robust_rows)} target={args.target_label}")
    print(f"wrote {args.cells_output}")
    print(f"wrote {args.robust_output}")
    print(f"wrote {meta_output}")


if __name__ == "__main__":
    main()
