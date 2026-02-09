#!/usr/bin/env python3
"""Verify the Phase 2 frozen artifact hash manifest."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "paper" / "notes" / "phase2_frozen_artifacts.sha256"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _parse_manifest(path: Path) -> list[tuple[str, Path]]:
    rows: list[tuple[str, Path]] = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"Invalid manifest row at line {i}: {raw!r}")
        expected_hash, file_path = parts
        rows.append((expected_hash.strip(), Path(file_path.strip())))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify Phase 2 frozen artifact hashes against manifest"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to phase2_frozen_artifacts.sha256",
    )
    args = parser.parse_args()

    manifest = args.manifest.resolve()
    if not manifest.exists():
        raise SystemExit(f"Manifest not found: {manifest}")

    rows = _parse_manifest(manifest)
    if not rows:
        raise SystemExit(f"No artifact rows found in: {manifest}")

    print(f"Verifying {len(rows)} artifact(s) from {manifest}")
    failures = 0
    for expected_hash, artifact_path in rows:
        if not artifact_path.exists():
            print(f"MISSING  {artifact_path}")
            failures += 1
            continue
        observed_hash = _sha256(artifact_path)
        if observed_hash != expected_hash:
            print(
                f"MISMATCH {artifact_path}\n"
                f"  expected={expected_hash}\n"
                f"  observed={observed_hash}"
            )
            failures += 1
            continue
        print(f"OK       {artifact_path}")

    if failures:
        print(f"Verification failed: {failures} artifact(s) did not match")
        raise SystemExit(1)

    print("Verification passed: all frozen Phase 2 artifacts match")


if __name__ == "__main__":
    main()
