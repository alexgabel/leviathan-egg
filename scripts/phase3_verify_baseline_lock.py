#!/usr/bin/env python3
"""Verify the locked Phase-3 desync baseline input hashes."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = (
    ROOT
    / "experiments"
    / "runs"
    / "phase3"
    / "desync_refine_lag8_fine"
    / "baseline_lock.yaml"
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _read_lock(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping YAML in lock file: {path}")
    return data


def _rows(lock: Dict[str, Any]) -> List[Dict[str, str]]:
    rows = lock.get("hashes", [])
    if not isinstance(rows, list):
        raise ValueError("baseline_lock.yaml: 'hashes' must be a list")
    out: List[Dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("baseline_lock.yaml: each 'hashes' row must be a mapping")
        path = str(row.get("path", "")).strip()
        digest = str(row.get("sha256", "")).strip()
        if not path or not digest:
            raise ValueError("baseline_lock.yaml: each hash row needs 'path' and 'sha256'")
        out.append({"path": path, "sha256": digest})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify locked Phase-3 baseline inputs against baseline_lock.yaml"
    )
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=DEFAULT_LOCK,
        help="Path to baseline_lock.yaml",
    )
    args = parser.parse_args()

    lock_file = args.lock_file.resolve()
    if not lock_file.exists():
        raise SystemExit(f"Lock file not found: {lock_file}")

    lock = _read_lock(lock_file)
    rows = _rows(lock)
    if not rows:
        raise SystemExit(f"No hash rows in lock file: {lock_file}")

    status = str(lock.get("status", "")).upper()
    if status != "LOCKED":
        raise SystemExit(f"Lock status is not LOCKED: {status!r}")

    print(f"Verifying {len(rows)} locked input(s) from {lock_file}")
    failures = 0
    for row in rows:
        path = Path(row["path"])
        expected = row["sha256"]
        if not path.exists():
            print(f"MISSING  {path}")
            failures += 1
            continue
        observed = _sha256(path)
        if observed != expected:
            print(
                f"MISMATCH {path}\n"
                f"  expected={expected}\n"
                f"  observed={observed}"
            )
            failures += 1
            continue
        print(f"OK       {path}")

    if failures:
        print(f"Verification failed: {failures} file(s) differ from locked baseline")
        raise SystemExit(1)

    print("Verification passed: locked Phase-3 baseline inputs unchanged")


if __name__ == "__main__":
    main()

