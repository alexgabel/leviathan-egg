#!/usr/bin/env python3
"""Label completed Phase 2 runs using the frozen regime classifier."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from leviathan_egg.regime import classify_regime, load_regime_thresholds  # noqa: E402


def _read_metrics(metrics_path: Path) -> dict[str, list[float]]:
    with metrics_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"No rows in metrics file: {metrics_path}")

    frac_hier = [float(r["frac_hier"]) for r in rows]
    crisis = [float(r["crisis"]) for r in rows] if "crisis" in rows[0] else []
    festival = [float(r["festival"]) for r in rows] if "festival" in rows[0] else []

    return {
        "frac_hier": frac_hier,
        "crisis": crisis,
        "festival": festival,
    }


def _label_rows(run_root: Path, thresholds_path: Path) -> list[dict[str, str]]:
    run_index = run_root / "run_index.csv"
    if not run_index.exists():
        raise FileNotFoundError(f"Missing run index: {run_index}")

    thresholds = load_regime_thresholds(thresholds_path)

    with run_index.open("r", encoding="utf-8") as f:
        entries = list(csv.DictReader(f))

    out: list[dict[str, str]] = []
    for row in entries:
        if row.get("status") != "SUCCESS":
            continue

        run_dir = Path(row["run_dir"])
        metrics_path = run_dir / "metrics.csv"
        config_resolved_path = run_dir / "config_resolved.yaml"

        if not metrics_path.exists() or not config_resolved_path.exists():
            continue

        metrics = _read_metrics(metrics_path)
        resolved = yaml.safe_load(config_resolved_path.read_text(encoding="utf-8"))
        period_steps = int(resolved["seasonality"]["seasonal_period"])

        driver = metrics["crisis"] if metrics["crisis"] else (metrics["festival"] if metrics["festival"] else None)
        result = classify_regime(
            metrics["frac_hier"],
            period_steps=period_steps,
            seasonal_driver=driver,
            thresholds=thresholds,
        )

        out.append(
            {
                "run_id": row["run_id"],
                "config_path": row["config_path"],
                "run_dir": row["run_dir"],
                "label": result.label,
                "confidence": f"{result.confidence:.4f}",
                "duty": f"{result.duty:.6f}",
                "switch_count": str(result.switch_count),
                "switch_rate": f"{result.switch_rate:.6f}",
                "max_dwell_hier": str(result.max_dwell_hier),
                "max_dwell_egal": str(result.max_dwell_egal),
                "seasonal_coherence": "" if result.seasonal_coherence is None else f"{result.seasonal_coherence:.6f}",
                "seasonal_lag": "" if result.seasonal_lag is None else str(result.seasonal_lag),
                "thresholds_path": str(thresholds_path),
                "labeled_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
        )

    return out


def _write_labels(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_id",
        "config_path",
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
        "thresholds_path",
        "labeled_at",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Label Phase 2 runs")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase2",
        help="Phase 2 run root",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase2" / "regime_thresholds.yaml",
        help="Threshold YAML path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase2" / "regime_labels.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    rows = _label_rows(args.run_root, args.thresholds)
    _write_labels(args.output, rows)
    print(f"Wrote {len(rows)} label rows: {args.output}")


if __name__ == "__main__":
    main()
