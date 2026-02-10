"""
Command-line interface for Leviathan Egg.

Phase 1.F baseline runner extended with Phase 2 reproducibility scaffolding:
- run index logging
- explicit failure marker
- retry policy
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from leviathan_egg.config import load_config
from leviathan_egg.metrics import collect_metrics
from leviathan_egg.seasons import seasonal_terms
from leviathan_egg.world import World

RUN_INDEX_FIELDS = [
    "run_id",
    "config_path",
    "seed",
    "status",
    "retry_count",
    "start_time",
    "end_time",
    "git_commit",
    "schema_version",
    "run_dir",
    "metrics_path",
    "config_resolved_path",
    "seed_path",
    "git_commit_path",
    "failed_marker_path",
    "artifact_paths",
    "error",
]


def _artifact_paths_from_run_dir(
    run_dir: Path, *, include_failed_marker: bool
) -> Dict[str, str]:
    metrics_path = run_dir / "metrics.csv"
    config_resolved_path = run_dir / "config_resolved.yaml"
    seed_path = run_dir / "seed.txt"
    git_commit_path = run_dir / "git_commit.txt"
    failed_marker_path = run_dir / "FAILED.txt"

    artifact_entries = [
        f"metrics:{metrics_path}",
        f"config_resolved:{config_resolved_path}",
        f"seed:{seed_path}",
        f"git_commit:{git_commit_path}",
    ]
    failed_marker_path_str = ""
    if include_failed_marker:
        failed_marker_path_str = str(failed_marker_path)
        artifact_entries.append(f"failed_marker:{failed_marker_path}")

    artifact_paths = "|".join(artifact_entries)
    return {
        "metrics_path": str(metrics_path),
        "config_resolved_path": str(config_resolved_path),
        "seed_path": str(seed_path),
        "git_commit_path": str(git_commit_path),
        "failed_marker_path": failed_marker_path_str,
        "artifact_paths": artifact_paths,
    }


def _derive_artifact_backfill_values(run_dir_str: str, *, status: str) -> Dict[str, str]:
    if not run_dir_str:
        return {
            "metrics_path": "",
            "config_resolved_path": "",
            "seed_path": "",
            "git_commit_path": "",
            "failed_marker_path": "",
            "artifact_paths": "",
        }
    return _artifact_paths_from_run_dir(
        Path(run_dir_str),
        include_failed_marker=status == "FAILED",
    )


def _git_commit_hash() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "UNKNOWN"


def _write_failed_marker(run_dir: Path, *, attempt: int, error_text: str) -> None:
    failed_path = run_dir / "FAILED.txt"
    with failed_path.open("w", encoding="utf-8") as f:
        f.write(f"attempt={attempt}\n")
        f.write(error_text)


def _append_run_index(
    index_path: Path,
    *,
    run_id: str,
    config_path: Path,
    seed: int,
    status: str,
    retry_count: int,
    start_time: str,
    end_time: str,
    git_commit: str,
    schema_version: str,
    run_dir: Path,
    metrics_path: Path,
    config_resolved_path: Path,
    seed_path: Path,
    git_commit_path: Path,
    failed_marker_path: str,
    artifact_paths: str,
    error: str,
) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)

    if index_path.exists() and index_path.stat().st_size > 0:
        _migrate_run_index_schema(index_path)

    write_header = not index_path.exists() or index_path.stat().st_size == 0
    with index_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_INDEX_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(
            {
                "run_id": run_id,
                "config_path": str(config_path),
                "seed": seed,
                "status": status,
                "retry_count": retry_count,
                "start_time": start_time,
                "end_time": end_time,
                "git_commit": git_commit,
                "schema_version": schema_version,
                "run_dir": str(run_dir),
                "metrics_path": str(metrics_path),
                "config_resolved_path": str(config_resolved_path),
                "seed_path": str(seed_path),
                "git_commit_path": str(git_commit_path),
                "failed_marker_path": failed_marker_path,
                "artifact_paths": artifact_paths,
                "error": error.strip().replace("\n", " | "),
            }
        )


def backfill_run_index(index_path: Path) -> bool:
    if not index_path.exists() or index_path.stat().st_size == 0:
        return False

    with index_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        existing_rows = list(reader)
        existing_fields = reader.fieldnames or []

    changed = existing_fields != RUN_INDEX_FIELDS

    migrated_rows = []
    for row in existing_rows:
        migrated = {field: row.get(field, "") for field in RUN_INDEX_FIELDS}
        run_dir_str = (migrated.get("run_dir", "") or "").strip()
        if run_dir_str:
            derived = _derive_artifact_backfill_values(
                run_dir_str,
                status=(migrated.get("status", "") or "").strip().upper(),
            )
            for key, value in derived.items():
                if migrated.get(key, "") != value:
                    migrated[key] = value
                    changed = True
        migrated_rows.append(migrated)

    if not changed:
        return False

    with index_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RUN_INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(migrated_rows)
    return True


def _migrate_run_index_schema(index_path: Path) -> None:
    backfill_run_index(index_path)


def _run_single_simulation(config_path: Path, run_dir: Path) -> int:
    cfg = load_config(config_path)

    # Initialize world
    world = World(cfg)

    total_steps = cfg.runtime_and_reproducibility.total_steps
    burn_in = cfg.runtime_and_reproducibility.burn_in_period
    # Emit Phase 3 per-patch/synchrony outputs for any multi-patch run.
    # Single-patch runs retain historical metric schema.
    include_phase3_metrics = bool(cfg.world_structure.num_patches > 1)

    rows: List[Dict[str, float]] = []

    for t in range(total_steps):
        season = seasonal_terms(t, cfg)
        world.step(t)

        if t >= burn_in:
            metrics = collect_metrics(
                world,
                season=season,
                include_phase3_scaffolding=include_phase3_metrics,
            )
            metrics["t"] = float(t)
            rows.append(metrics)

    # Write metrics.csv
    metrics_path = run_dir / "metrics.csv"
    if rows:
        fieldnames = list(rows[0].keys())
        with metrics_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    else:
        with metrics_path.open("w", encoding="utf-8") as f:
            f.write("\n")

    # Write resolved config
    with (run_dir / "config_resolved.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg.to_resolved_dict(), f, sort_keys=False)

    # Write git commit
    with (run_dir / "git_commit.txt").open("w", encoding="utf-8") as f:
        f.write(_git_commit_hash() + "\n")

    # Write seed
    with (run_dir / "seed.txt").open("w", encoding="utf-8") as f:
        f.write(str(cfg.runtime_and_reproducibility.random_seed) + "\n")

    return len(rows)


def run_simulation(
    config_path: Path,
    *,
    run_root: Optional[Path] = None,
    max_retries: int = 1,
) -> Path:
    cfg = load_config(config_path)

    run_root = run_root or (Path("experiments") / "runs")
    run_root.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_id = f"{cfg.meta.experiment_name}_{ts}"
    run_dir = run_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    start_time = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    retry_budget = max(0, int(max_retries))
    status = "FAILED"
    rows_logged = 0
    error_text = ""
    attempts_used = 0

    for attempt in range(retry_budget + 1):
        attempts_used = attempt
        try:
            rows_logged = _run_single_simulation(config_path, run_dir)
            failed_path = run_dir / "FAILED.txt"
            if failed_path.exists():
                failed_path.unlink()
            status = "SUCCESS"
            error_text = ""
            break
        except Exception:
            error_text = traceback.format_exc()
            _write_failed_marker(run_dir, attempt=attempt, error_text=error_text)

    end_time = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    artifact_fields = _artifact_paths_from_run_dir(
        run_dir,
        include_failed_marker=status == "FAILED",
    )
    _append_run_index(
        run_root / "run_index.csv",
        run_id=run_id,
        config_path=config_path,
        seed=cfg.runtime_and_reproducibility.random_seed,
        status=status,
        retry_count=attempts_used,
        start_time=start_time,
        end_time=end_time,
        git_commit=_git_commit_hash(),
        schema_version=cfg.schema_version,
        run_dir=run_dir,
        metrics_path=Path(artifact_fields["metrics_path"]),
        config_resolved_path=Path(artifact_fields["config_resolved_path"]),
        seed_path=Path(artifact_fields["seed_path"]),
        git_commit_path=Path(artifact_fields["git_commit_path"]),
        failed_marker_path=artifact_fields["failed_marker_path"],
        artifact_paths=artifact_fields["artifact_paths"],
        error=error_text,
    )

    # Print summary
    print("=== Leviathan Egg run complete ===")
    print(f"Config: {config_path}")
    print(f"Run dir: {run_dir}")
    print(f"Steps: {cfg.runtime_and_reproducibility.total_steps} (burn-in: {cfg.runtime_and_reproducibility.burn_in_period})")
    print(f"Logged rows: {rows_logged}")
    print(f"Status: {status}")
    print("=================================")

    if status != "SUCCESS":
        raise RuntimeError(f"Run failed after {retry_budget + 1} attempt(s): {run_dir}")

    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(prog="leviathan-egg")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run a Leviathan Egg simulation")
    run_p.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to YAML configuration file",
    )
    run_p.add_argument(
        "--run-root",
        type=Path,
        default=Path("experiments") / "runs",
        help="Directory under which run folders and run_index.csv are created",
    )
    run_p.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Retry budget after initial attempt",
    )

    args = parser.parse_args()

    if args.command == "run":
        run_simulation(args.config, run_root=args.run_root, max_retries=args.max_retries)
    else:
        raise SystemExit(f"Unknown command: {args.command}")
