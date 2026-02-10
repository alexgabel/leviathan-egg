#!/usr/bin/env python3
"""Prepare Phase 3 analysis tables from run artifacts."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Dict, List

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _parse_kv(text: str | None) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not text:
        return out
    for token in text.split(";"):
        token = token.strip()
        if not token or "=" not in token:
            continue
        k, v = token.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def _manifest_by_basename(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for r in rows:
        base = Path(r["config_path"]).name
        out[base] = r
    return out


def _canonical_config_basename(path_str: str) -> str:
    base = Path(path_str).name
    if base.endswith("_smoke.yaml"):
        return base.replace("_smoke.yaml", ".yaml")
    return base


def _float_series(metric_rows: List[Dict[str, str]], key: str) -> np.ndarray:
    vals = []
    for r in metric_rows:
        if key not in r or r[key] == "":
            continue
        vals.append(float(r[key]))
    return np.asarray(vals, dtype=float)


def _summary_from_metrics(metric_rows: List[Dict[str, str]]) -> Dict[str, float] | None:
    order = _float_series(metric_rows, "synchrony_order_parameter")
    lock = _float_series(metric_rows, "synchrony_phase_lock_fraction")
    lag = _float_series(metric_rows, "synchrony_mean_abs_phase_lag")
    if order.size == 0 or lock.size == 0 or lag.size == 0:
        return None
    return {
        "sync_order_mean": float(np.mean(order)),
        "sync_order_std": float(np.std(order)),
        "sync_lock_mean": float(np.mean(lock)),
        "sync_lock_std": float(np.std(lock)),
        "sync_lag_mean": float(np.mean(lag)),
        "sync_lag_std": float(np.std(lag)),
    }


def _label(
    *,
    sync_order_mean: float,
    sync_lock_mean: float,
    sync_lag_mean: float,
    sync_order_hi: float,
    sync_lock_hi: float,
    sync_lag_hi: float,
    desync_order_lo: float,
    desync_lock_lo: float,
    desync_lag_lo: float,
) -> str:
    if (
        sync_order_mean >= sync_order_hi
        and sync_lock_mean >= sync_lock_hi
        and sync_lag_mean <= sync_lag_hi
    ):
        return "synchrony"
    if (
        sync_order_mean <= desync_order_lo
        and sync_lock_mean <= desync_lock_lo
        and sync_lag_mean >= desync_lag_lo
    ):
        return "desynchrony"
    return "boundary"


def _thresholds_from_quantiles(
    *,
    rows: List[Dict[str, str]],
    quantile_lo: float,
    quantile_hi: float,
) -> Dict[str, float]:
    if not rows:
        raise ValueError("No rows available for quantile thresholding")

    def q(key: str, quantile: float) -> float:
        vals = np.asarray([float(r[key]) for r in rows], dtype=float)
        return float(np.quantile(vals, quantile))

    # Higher order/lock implies more synchrony; lower lag implies more synchrony.
    return {
        "sync_order_hi": q("sync_order_mean", quantile_hi),
        "sync_lock_hi": q("sync_lock_mean", quantile_hi),
        "sync_lag_hi": q("sync_lag_mean", quantile_lo),
        "desync_order_lo": q("sync_order_mean", quantile_lo),
        "desync_lock_lo": q("sync_lock_mean", quantile_lo),
        "desync_lag_lo": q("sync_lag_mean", quantile_hi),
    }


def _join(
    *,
    run_rows: List[Dict[str, str]],
    manifest_by_base: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for run in run_rows:
        if run.get("status") != "SUCCESS":
            continue

        base = _canonical_config_basename(run["config_path"])
        manifest = manifest_by_base.get(base)
        if manifest is None:
            continue

        metrics_path = (
            Path(run["metrics_path"])
            if run.get("metrics_path")
            else Path(run["run_dir"]) / "metrics.csv"
        )
        if not metrics_path.exists():
            continue
        metric_rows = _read_csv(metrics_path)
        summary = _summary_from_metrics(metric_rows)
        if summary is None:
            continue

        kv = {}
        kv.update(_parse_kv(manifest.get("sweep_value")))
        kv.update(_parse_kv(manifest.get("notes")))
        phase_profile = kv.get("phase_profile", "")
        topology = kv.get("topology", "")
        sign = kv.get("sign", "")
        strength = kv.get("strength", "")

        out.append(
            {
                "run_id": run["run_id"],
                "config_path": run["config_path"],
                "config_basename": base,
                "seed": run["seed"],
                "start_time": run["start_time"],
                "end_time": run["end_time"],
                "status": run["status"],
                "git_commit": run["git_commit"],
                "schema_version": run["schema_version"],
                "run_dir": run["run_dir"],
                "sync_order_mean": f"{summary['sync_order_mean']:.6f}",
                "sync_order_std": f"{summary['sync_order_std']:.6f}",
                "sync_lock_mean": f"{summary['sync_lock_mean']:.6f}",
                "sync_lock_std": f"{summary['sync_lock_std']:.6f}",
                "sync_lag_mean": f"{summary['sync_lag_mean']:.6f}",
                "sync_lag_std": f"{summary['sync_lag_std']:.6f}",
                "sweep_axis": manifest.get("sweep_axis", ""),
                "sweep_value": manifest.get("sweep_value", ""),
                "hypothesis": manifest.get("hypothesis", ""),
                "stage": manifest.get("stage", ""),
                "manifest_seed": manifest.get("seed", ""),
                "manifest_notes": manifest.get("notes", ""),
                "phase_profile": phase_profile,
                "topology": topology,
                "sign": sign,
                "strength": strength,
            }
        )
    out.sort(key=lambda r: r["start_time"])
    return out


def _latest_per_config(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    latest: Dict[str, Dict[str, str]] = {}
    for r in rows:
        base = r["config_basename"]
        if base not in latest or r["end_time"] > latest[base]["end_time"]:
            latest[base] = r
    return sorted(latest.values(), key=lambda r: r["config_basename"])


def _full_grid_suffix_block(
    rows: List[Dict[str, str]], target_basenames: set[str]
) -> List[Dict[str, str]]:
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
    return rows[start_idx:]


def _apply_labels(rows: List[Dict[str, str]], *, thresholds: Dict[str, float]) -> None:
    for r in rows:
        r["label"] = _label(
            sync_order_mean=float(r["sync_order_mean"]),
            sync_lock_mean=float(r["sync_lock_mean"]),
            sync_lag_mean=float(r["sync_lag_mean"]),
            sync_order_hi=thresholds["sync_order_hi"],
            sync_lock_hi=thresholds["sync_lock_hi"],
            sync_lag_hi=thresholds["sync_lag_hi"],
            desync_order_lo=thresholds["desync_order_lo"],
            desync_lock_lo=thresholds["desync_lock_lo"],
            desync_lag_lo=thresholds["desync_lag_lo"],
        )


def _write_thresholds_csv(path: Path, thresholds: Dict[str, float], mode: str) -> None:
    rows = [{"label_mode": mode, "key": k, "value": f"{v:.9f}"} for k, v in thresholds.items()]
    _write_csv(path, rows, ["label_mode", "key", "value"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Phase 3 analysis tables")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase3" / "manifest_stage1_exploration.csv",
    )
    parser.add_argument(
        "--latest-output",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "analysis_latest_per_config.csv",
    )
    parser.add_argument(
        "--block-output",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "analysis_full_grid_block.csv",
    )
    parser.add_argument(
        "--label-mode",
        choices=("fixed", "quantile"),
        default="fixed",
        help="fixed: use explicit threshold args; quantile: derive thresholds from analysis rows",
    )
    parser.add_argument(
        "--quantile-lo",
        type=float,
        default=0.25,
        help="Low quantile for quantile mode (0<q<0.5)",
    )
    parser.add_argument(
        "--quantile-hi",
        type=float,
        default=0.75,
        help="High quantile for quantile mode (0.5<q<1)",
    )
    parser.add_argument(
        "--thresholds-output",
        type=Path,
        default=None,
        help="Optional CSV output capturing thresholds used for this analysis run",
    )
    parser.add_argument("--sync-order-hi", type=float, default=0.68)
    parser.add_argument("--sync-lock-hi", type=float, default=0.65)
    parser.add_argument("--sync-lag-hi", type=float, default=3.0)
    parser.add_argument("--desync-order-lo", type=float, default=0.58)
    parser.add_argument("--desync-lock-lo", type=float, default=0.55)
    parser.add_argument("--desync-lag-lo", type=float, default=5.0)
    args = parser.parse_args()

    run_rows = _read_csv(args.run_root / "run_index.csv")
    manifest_rows = _read_csv(args.manifest)
    manifest_by_base = _manifest_by_basename(manifest_rows)

    joined = _join(
        run_rows=run_rows,
        manifest_by_base=manifest_by_base,
    )

    if args.label_mode == "quantile":
        if not (0.0 < args.quantile_lo < 0.5 and 0.5 < args.quantile_hi < 1.0):
            raise ValueError("quantile-lo must be in (0,0.5) and quantile-hi must be in (0.5,1)")
        thresholds = _thresholds_from_quantiles(
            rows=joined,
            quantile_lo=args.quantile_lo,
            quantile_hi=args.quantile_hi,
        )
    else:
        thresholds = {
            "sync_order_hi": args.sync_order_hi,
            "sync_lock_hi": args.sync_lock_hi,
            "sync_lag_hi": args.sync_lag_hi,
            "desync_order_lo": args.desync_order_lo,
            "desync_lock_lo": args.desync_lock_lo,
            "desync_lag_lo": args.desync_lag_lo,
        }

    _apply_labels(joined, thresholds=thresholds)
    latest = _latest_per_config(joined)
    block = _full_grid_suffix_block(joined, set(manifest_by_base.keys()))

    fieldnames = [
        "run_id",
        "config_path",
        "config_basename",
        "seed",
        "start_time",
        "end_time",
        "status",
        "git_commit",
        "schema_version",
        "run_dir",
        "label",
        "sync_order_mean",
        "sync_order_std",
        "sync_lock_mean",
        "sync_lock_std",
        "sync_lag_mean",
        "sync_lag_std",
        "sweep_axis",
        "sweep_value",
        "hypothesis",
        "stage",
        "manifest_seed",
        "manifest_notes",
        "phase_profile",
        "topology",
        "sign",
        "strength",
    ]
    _write_csv(args.latest_output, latest, fieldnames)
    _write_csv(args.block_output, block, fieldnames)
    if args.thresholds_output is not None:
        _write_thresholds_csv(args.thresholds_output, thresholds, args.label_mode)

    print(
        "thresholds:"
        f" mode={args.label_mode}"
        f" sync(order>={thresholds['sync_order_hi']:.6f},"
        f" lock>={thresholds['sync_lock_hi']:.6f},"
        f" lag<={thresholds['sync_lag_hi']:.6f})"
        f" desync(order<={thresholds['desync_order_lo']:.6f},"
        f" lock<={thresholds['desync_lock_lo']:.6f},"
        f" lag>={thresholds['desync_lag_lo']:.6f})"
    )
    print(f"joined: rows={len(joined)} labels={dict(Counter(r['label'] for r in joined))}")
    print(f"latest_per_config: rows={len(latest)} labels={dict(Counter(r['label'] for r in latest))}")
    print(f"full_grid_block: rows={len(block)} labels={dict(Counter(r['label'] for r in block))}")


if __name__ == "__main__":
    main()
