#!/usr/bin/env python3
"""Run a Phase-3 manifest in conservative parallel shards and merge run indices."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from leviathan_egg.cli import RUN_INDEX_FIELDS  # noqa: E402


def _read_rows(manifest_path: Path, *, stage: str | None) -> tuple[List[Dict[str, str]], List[str]]:
    with manifest_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or [
            "config_path",
            "sweep_axis",
            "sweep_value",
            "hypothesis",
            "seed",
            "stage",
            "notes",
        ]
        rows = []
        for row in reader:
            if not row.get("config_path"):
                continue
            if stage and row.get("stage") != stage:
                continue
            rows.append(row)
    return rows, fieldnames


def _split_rows(rows: List[Dict[str, str]], shards: int) -> List[List[Dict[str, str]]]:
    out = [[] for _ in range(shards)]
    for idx, row in enumerate(rows):
        out[idx % shards].append(row)
    return out


def _write_manifest(path: Path, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _merge_run_index(*, shard_roots: List[Path], output_path: Path) -> int:
    rows: List[Dict[str, str]] = []
    for shard_root in shard_roots:
        index_path = shard_root / "run_index.csv"
        if not index_path.exists():
            continue
        with index_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({field: row.get(field, "") for field in RUN_INDEX_FIELDS})

    rows.sort(key=lambda r: (r.get("start_time", ""), r.get("run_id", "")))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase-3 manifest in shards")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase3" / "manifest_desync_refine.csv",
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine",
    )
    parser.add_argument("--stage", type=str, default="confirmation")
    parser.add_argument(
        "--shards",
        type=int,
        default=2,
        help="Conservative default for laptop memory/thermals",
    )
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--override-total-steps", type=int, default=0)
    parser.add_argument("--override-burn-in", type=int, default=-1)
    parser.add_argument("--python", type=str, default=sys.executable)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-merge-index", action="store_true")
    args = parser.parse_args()

    if args.shards < 1:
        raise ValueError("--shards must be >= 1")

    rows, fieldnames = _read_rows(args.manifest, stage=args.stage if args.stage else None)
    if args.limit > 0:
        rows = rows[: args.limit]

    groups = _split_rows(rows, args.shards)
    shard_dir = args.run_root / "_shards"
    manifest_dir = shard_dir / "manifests"
    shard_roots: List[Path] = []
    commands: List[List[str]] = []

    for shard_idx, shard_rows in enumerate(groups):
        if not shard_rows:
            continue
        shard_manifest = manifest_dir / f"manifest_shard_{shard_idx:02d}.csv"
        _write_manifest(shard_manifest, fieldnames, shard_rows)
        shard_run_root = args.run_root / f"shard_{shard_idx:02d}"
        shard_roots.append(shard_run_root)

        cmd = [
            args.python,
            str(ROOT / "scripts" / "phase3_run_manifest.py"),
            "--manifest",
            str(shard_manifest),
            "--run-root",
            str(shard_run_root),
            "--max-retries",
            str(args.max_retries),
        ]
        if args.stage:
            cmd.extend(["--stage", args.stage])
        if args.continue_on_error:
            cmd.append("--continue-on-error")
        if args.override_total_steps > 0:
            cmd.extend(["--override-total-steps", str(args.override_total_steps)])
        if args.override_burn_in >= 0:
            cmd.extend(["--override-burn-in", str(args.override_burn_in)])
        commands.append(cmd)

    print(f"selected_rows={len(rows)} shards={len(commands)} run_root={args.run_root}")
    for idx, cmd in enumerate(commands, start=1):
        print(f"shard[{idx}] cmd: {' '.join(cmd)}")

    if args.dry_run:
        return

    procs = [subprocess.Popen(cmd) for cmd in commands]
    return_codes = []
    for i, proc in enumerate(procs, start=1):
        rc = proc.wait()
        return_codes.append(rc)
        print(f"shard[{i}] return_code={rc}")

    merged_rows = 0
    if not args.no_merge_index:
        merged_rows = _merge_run_index(
            shard_roots=shard_roots,
            output_path=args.run_root / "run_index.csv",
        )
        print(f"merged_run_index_rows={merged_rows} -> {args.run_root / 'run_index.csv'}")

    failed = sum(1 for rc in return_codes if rc != 0)
    print(f"done failed_shards={failed} merged_rows={merged_rows}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
