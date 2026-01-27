"""
Command-line interface for Leviathan Egg.

Phase 1.F:
- Minimal runner to execute a config and log outputs
"""

from __future__ import annotations

import argparse
import csv
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List

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


def run_simulation(config_path: Path) -> None:
    cfg = load_config(config_path)

    # Create run directory
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path("experiments") / "runs" / f"{cfg.meta.experiment_name}_{ts}"
    run_dir.mkdir(parents=True, exist_ok=False)

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

    # Write resolved config
    with (run_dir / "config_resolved.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg.to_resolved_dict(), f, sort_keys=False)

    # Write git commit
    with (run_dir / "git_commit.txt").open("w", encoding="utf-8") as f:
        f.write(_git_commit_hash() + "\n")

    # Write seed
    with (run_dir / "seed.txt").open("w", encoding="utf-8") as f:
        f.write(str(cfg.runtime_and_reproducibility.random_seed) + "\n")

    # Print summary
    print("=== Leviathan Egg run complete ===")
    print(f"Config: {config_path}")
    print(f"Run dir: {run_dir}")
    print(f"Steps: {total_steps} (burn-in: {burn_in})")
    print(f"Logged rows: {len(rows)}")
    print("=================================")


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

    args = parser.parse_args()

    if args.command == "run":
        run_simulation(args.config)
    else:
        raise SystemExit(f"Unknown command: {args.command}")