#!/usr/bin/env python3
"""Run Phase 2 configs listed in a manifest via the project CLI runner."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from leviathan_egg.cli import run_simulation  # noqa: E402


def _rows(manifest_path: Path, *, stage: str | None = None):
    with manifest_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("config_path"):
                continue
            if stage and row.get("stage") != stage:
                continue
            yield row


def _write_override_config(
    *,
    source_config: Path,
    output_dir: Path,
    total_steps: int,
    burn_in: int,
) -> Path:
    cfg = yaml.safe_load(source_config.read_text(encoding="utf-8"))
    rr = cfg["runtime_and_reproducibility"]
    rr["total_steps"] = int(total_steps)
    rr["burn_in_period"] = int(burn_in)

    out_path = output_dir / f"{source_config.stem}_smoke.yaml"
    out_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run configs from manifest")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase2" / "manifest_exploration.csv",
        help="CSV manifest path",
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase2",
        help="Run root directory",
    )
    parser.add_argument(
        "--stage",
        type=str,
        default="exploration",
        help="Optional stage filter",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max number of rows to run (0 means all)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Retry budget per run",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue running remaining rows after a failure",
    )
    parser.add_argument(
        "--override-total-steps",
        type=int,
        default=0,
        help="If >0, run using temporary config copies with this total_steps value",
    )
    parser.add_argument(
        "--override-burn-in",
        type=int,
        default=-1,
        help="Burn-in for override mode (default: max(1, total_steps//10))",
    )
    args = parser.parse_args()

    run_rows = list(_rows(args.manifest, stage=args.stage if args.stage else None))
    if args.limit > 0:
        run_rows = run_rows[: args.limit]

    print(f"Selected {len(run_rows)} row(s) from manifest: {args.manifest}", flush=True)
    failures = 0
    override_dir = args.run_root / "_tmp_overrides"
    if args.override_total_steps > 0:
        override_dir.mkdir(parents=True, exist_ok=True)

    for idx, row in enumerate(run_rows, start=1):
        config_path = ROOT / row["config_path"]
        run_config_path = config_path
        if args.override_total_steps > 0:
            burn_in = (
                args.override_burn_in
                if args.override_burn_in >= 0
                else max(1, args.override_total_steps // 10)
            )
            run_config_path = _write_override_config(
                source_config=config_path,
                output_dir=override_dir,
                total_steps=args.override_total_steps,
                burn_in=burn_in,
            )
            print(
                f"[{idx}/{len(run_rows)}] Running smoke override {run_config_path} (source {config_path})",
                flush=True,
            )
        else:
            print(f"[{idx}/{len(run_rows)}] Running {config_path}", flush=True)
        try:
            run_dir = run_simulation(
                run_config_path,
                run_root=args.run_root,
                max_retries=args.max_retries,
            )
            print(f"Completed: {run_dir}", flush=True)
        except Exception as exc:
            failures += 1
            print(f"FAILED: {config_path}: {exc}", flush=True)
            if not args.continue_on_error:
                raise

    print(f"Done. failures={failures}", flush=True)


if __name__ == "__main__":
    main()
