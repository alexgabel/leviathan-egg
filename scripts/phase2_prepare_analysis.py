#!/usr/bin/env python3
"""Prepare filtered Phase 2 analysis tables for plotting/reporting.

Outputs:
- analysis_latest_per_config.csv
- analysis_full_grid_block.csv

Both outputs join run index + labels + manifest metadata and exclude rows
outside the exploration manifest.
"""

from __future__ import annotations

import argparse
import csv
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


def _manifest_by_basename(manifest_rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for r in manifest_rows:
        base = Path(r["config_path"]).name
        if base in out:
            raise ValueError(f"Duplicate config basename in manifest: {base}")
        out[base] = r
    return out


def _canonical_config_basename(path_str: str) -> str:
    base = Path(path_str).name
    if base.endswith("_smoke.yaml"):
        return base.replace("_smoke.yaml", ".yaml")
    return base


def _join_rows(
    *,
    run_rows: List[Dict[str, str]],
    labels_by_run_id: Dict[str, Dict[str, str]],
    manifest_by_base: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    joined: List[Dict[str, str]] = []

    for run in run_rows:
        if run.get("status") != "SUCCESS":
            continue

        config_base = _canonical_config_basename(run["config_path"])
        if config_base not in manifest_by_base:
            continue

        lab = labels_by_run_id.get(run["run_id"])
        if lab is None:
            continue

        manifest = manifest_by_base[config_base]

        merged = {
            "run_id": run["run_id"],
            "config_path": run["config_path"],
            "config_basename": config_base,
            "seed": run["seed"],
            "start_time": run["start_time"],
            "end_time": run["end_time"],
            "status": run["status"],
            "retry_count": run["retry_count"],
            "git_commit": run["git_commit"],
            "schema_version": run["schema_version"],
            "run_dir": run["run_dir"],
            "label": lab["label"],
            "confidence": lab["confidence"],
            "duty": lab["duty"],
            "switch_count": lab["switch_count"],
            "switch_rate": lab["switch_rate"],
            "max_dwell_hier": lab["max_dwell_hier"],
            "max_dwell_egal": lab["max_dwell_egal"],
            "seasonal_coherence": lab["seasonal_coherence"],
            "seasonal_lag": lab["seasonal_lag"],
            "labeled_at": lab["labeled_at"],
            "sweep_axis": manifest["sweep_axis"],
            "sweep_value": manifest["sweep_value"],
            "hypothesis": manifest["hypothesis"],
            "stage": manifest["stage"],
            "manifest_seed": manifest["seed"],
            "manifest_notes": manifest["notes"],
        }
        joined.append(merged)

    joined.sort(key=lambda r: r["start_time"])
    return joined


def _latest_per_config(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    latest: Dict[str, Dict[str, str]] = {}
    for r in rows:
        base = r["config_basename"]
        if base not in latest or r["end_time"] > latest[base]["end_time"]:
            latest[base] = r
    return sorted(latest.values(), key=lambda r: r["config_basename"])


def _full_grid_suffix_block(rows: List[Dict[str, str]], target_basenames: set[str]) -> List[Dict[str, str]]:
    if not rows:
        return []

    seen: set[str] = set()
    start_idx = None

    for i in range(len(rows) - 1, -1, -1):
        base = rows[i]["config_basename"]
        if base in target_basenames:
            seen.add(base)
        if seen == target_basenames:
            start_idx = i
            break

    if start_idx is None:
        return []

    block = rows[start_idx:]
    return block


def _print_summary(name: str, rows: List[Dict[str, str]]) -> None:
    labels = Counter(r["label"] for r in rows)
    print(f"{name}: rows={len(rows)} labels={dict(labels)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare filtered analysis tables")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("experiments") / "runs" / "phase2",
        help="Run root containing run_index.csv and regime_labels.csv",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=None,
        help="Optional labels CSV path (defaults to <run-root>/regime_labels.csv)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments") / "configs" / "phase2" / "manifest_exploration.csv",
        help="Exploration manifest path",
    )
    parser.add_argument(
        "--latest-output",
        type=Path,
        default=Path("experiments") / "runs" / "phase2" / "analysis_latest_per_config.csv",
        help="Output for de-duplicated latest-per-config table",
    )
    parser.add_argument(
        "--block-output",
        type=Path,
        default=Path("experiments") / "runs" / "phase2" / "analysis_full_grid_block.csv",
        help="Output for latest full-grid suffix block table",
    )
    args = parser.parse_args()

    run_index_path = args.run_root / "run_index.csv"
    labels_path = args.labels if args.labels is not None else (args.run_root / "regime_labels.csv")

    run_rows = _read_csv(run_index_path)
    label_rows = _read_csv(labels_path)
    manifest_rows = _read_csv(args.manifest)

    labels_by_run_id = {r["run_id"]: r for r in label_rows}
    manifest_by_base = _manifest_by_basename(manifest_rows)

    joined = _join_rows(
        run_rows=run_rows,
        labels_by_run_id=labels_by_run_id,
        manifest_by_base=manifest_by_base,
    )

    latest_rows = _latest_per_config(joined)
    full_block_rows = _full_grid_suffix_block(joined, set(manifest_by_base.keys()))

    fieldnames = [
        "run_id",
        "config_path",
        "config_basename",
        "seed",
        "start_time",
        "end_time",
        "status",
        "retry_count",
        "git_commit",
        "schema_version",
        "run_dir",
        "label",
        "confidence",
        "duty",
        "switch_count",
        "switch_rate",
        "max_dwell_hier",
        "max_dwell_egal",
        "seasonal_coherence",
        "seasonal_lag",
        "labeled_at",
        "sweep_axis",
        "sweep_value",
        "hypothesis",
        "stage",
        "manifest_seed",
        "manifest_notes",
    ]

    _write_csv(args.latest_output, latest_rows, fieldnames)
    _write_csv(args.block_output, full_block_rows, fieldnames)

    _print_summary("joined", joined)
    _print_summary("latest_per_config", latest_rows)
    _print_summary("full_grid_block", full_block_rows)


if __name__ == "__main__":
    main()
