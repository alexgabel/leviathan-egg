#!/usr/bin/env python3
"""Backfill legacy Phase 2 run_index.csv files to the latest schema.

This script upgrades old run-index files to include:
- metrics_path
- config_resolved_path
- seed_path
- git_commit_path
- failed_marker_path
- artifact_paths
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from leviathan_egg.cli import RUN_INDEX_FIELDS, backfill_run_index  # noqa: E402


def _discover_indices(run_root: Path) -> list[Path]:
    found = {p.resolve() for p in run_root.rglob("run_index.csv")}
    direct = (run_root / "run_index.csv").resolve()
    if direct.exists():
        found.add(direct)
    return sorted(found)


def _would_change(index_path: Path) -> bool:
    with tempfile.TemporaryDirectory(prefix="phase2_run_index_backfill_") as tmpdir:
        tmp = Path(tmpdir) / "run_index.csv"
        shutil.copy2(index_path, tmp)
        return backfill_run_index(tmp)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Phase 2 run_index.csv files")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase2",
        help="Root directory under which run_index.csv files are discovered",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=None,
        help="Optional single run_index.csv path to backfill",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report files that would be changed without writing",
    )
    args = parser.parse_args()

    if args.index is not None:
        index_paths = [args.index.resolve()]
    else:
        index_paths = _discover_indices(args.run_root.resolve())

    if not index_paths:
        print("No run_index.csv files found.")
        return

    print(f"Target schema fields ({len(RUN_INDEX_FIELDS)}): {','.join(RUN_INDEX_FIELDS)}")
    print(f"Discovered {len(index_paths)} run_index.csv file(s)")

    changed = 0
    unchanged = 0
    for path in index_paths:
        if args.dry_run:
            did_change = _would_change(path)
        else:
            did_change = backfill_run_index(path)

        if did_change:
            changed += 1
            action = "would update" if args.dry_run else "updated"
            print(f"{action}: {path}")
        else:
            unchanged += 1
            print(f"unchanged: {path}")

    mode = "dry-run" if args.dry_run else "apply"
    print(f"Done ({mode}). changed={changed} unchanged={unchanged}")


if __name__ == "__main__":
    main()
