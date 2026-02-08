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
    error: str,
) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
        "error",
    ]

    write_header = not index_path.exists() or index_path.stat().st_size == 0
    with index_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
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
                "error": error.strip().replace("\n", " | "),
            }
        )


def _run_single_simulation(config_path: Path, run_dir: Path) -> int:
    cfg = load_config(config_path)

    # Initialize world
    world = World(cfg)

    total_steps = cfg.runtime_and_reproducibility.total_steps
    burn_in = cfg.runtime_and_reproducibility.burn_in_period

    rows: List[Dict[str, float]] = []

    for t in range(total_steps):
        season = seasonal_terms(t, cfg)
        world.step(t)

        if t >= burn_in:
            metrics = collect_metrics(world, season=season)
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
