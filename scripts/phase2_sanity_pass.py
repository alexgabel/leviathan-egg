#!/usr/bin/env python3
"""Run strict sanity checks for Phase 2 regime labeling robustness.

This script addresses three concerns:
1) threshold sensitivity across a tau ensemble
2) brittleness to near-threshold chatter via hysteresis binarization
3) permissive boundary claims via stricter boundary pass criteria

Outputs:
- run-level labels across settings
- cell-level probabilities/pass flags across settings
- cell-level stability summary
- boundary-level strict verdicts per setting
- boundary-level stability summary
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from leviathan_egg.regime import (  # noqa: E402
    RegimeThresholds,
    classify_regime,
    classify_regime_hysteresis,
    load_regime_thresholds,
)

LABELS = ("egalitarian", "hierarchical", "reversal", "uncertain")
REPLICATE_SUFFIX_RE = re.compile(r"_r\d+$")
BOUNDARY_RE = re.compile(r"(?:^|_)(b\d{2})(?:_|$)")
ALPHA_RE = re.compile(r"(?:^|_)a(\d+)(?:_|$)")


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _parse_csv_floats(value: str) -> List[float]:
    vals: List[float] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        vals.append(float(token))
    if not vals:
        raise ValueError("No numeric values parsed")
    return sorted(set(vals))


def _cell_id_from_basename(config_basename: str) -> str:
    stem = Path(config_basename).stem
    if stem.endswith("_smoke"):
        stem = stem[:-6]
    return REPLICATE_SUFFIX_RE.sub("", stem)


def _boundary_id(cell_id: str) -> str:
    m = BOUNDARY_RE.search(cell_id)
    return m.group(1) if m else ""


def _alpha_from_cell(cell_id: str) -> str:
    m = ALPHA_RE.search(cell_id)
    if not m:
        return ""
    v = int(m.group(1))
    if v >= 100:
        return f"{v/1000.0:.3f}".rstrip("0").rstrip(".")
    return f"{v/100.0:.2f}".rstrip("0").rstrip(".")


def _resolve_run_path(row: Dict[str, str], key: str, fallback_name: str) -> Path:
    raw = (row.get(key, "") or "").strip()
    if raw:
        return Path(raw)
    return Path(row["run_dir"]) / fallback_name


def _load_metrics(metrics_path: Path) -> Dict[str, Sequence[float]]:
    rows = _read_csv(metrics_path)
    if not rows:
        raise ValueError(f"Empty metrics CSV: {metrics_path}")
    frac_hier = [float(r["frac_hier"]) for r in rows]
    crisis = [float(r["crisis"]) for r in rows] if "crisis" in rows[0] else []
    festival = [float(r["festival"]) for r in rows] if "festival" in rows[0] else []
    return {
        "frac_hier": frac_hier,
        "crisis": crisis,
        "festival": festival,
    }


def _allowed_run_ids(analysis_csv: Optional[Path]) -> set[str]:
    if analysis_csv is None:
        return set()
    rows = _read_csv(analysis_csv)
    return {r["run_id"] for r in rows if r.get("run_id")}


def _load_run_payloads(run_root: Path, *, analysis_csv: Optional[Path]) -> List[Dict[str, object]]:
    run_index = run_root / "run_index.csv"
    if not run_index.exists():
        raise FileNotFoundError(f"Missing run index: {run_index}")

    allow = _allowed_run_ids(analysis_csv)
    rows = _read_csv(run_index)
    payloads: List[Dict[str, object]] = []

    for row in rows:
        if row.get("status") != "SUCCESS":
            continue
        run_id = row.get("run_id", "")
        if allow and run_id not in allow:
            continue

        config_path = row.get("config_path", "")
        config_basename = Path(config_path).name
        cell_id = _cell_id_from_basename(config_basename)

        metrics_path = _resolve_run_path(row, "metrics_path", "metrics.csv")
        cfg_path = _resolve_run_path(row, "config_resolved_path", "config_resolved.yaml")
        if not metrics_path.exists() or not cfg_path.exists():
            continue

        metrics = _load_metrics(metrics_path)
        frac_hier = [float(v) for v in metrics["frac_hier"]]
        frac_sorted = sorted(frac_hier)
        idx05 = int(0.05 * (len(frac_sorted) - 1))
        idx95 = int(0.95 * (len(frac_sorted) - 1))
        p05 = float(frac_sorted[idx05])
        p95 = float(frac_sorted[idx95])
        resolved = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        period_steps = int(resolved["seasonality"]["seasonal_period"])

        driver_name = ""
        seasonal_driver: Optional[Sequence[float]] = None
        if metrics["crisis"]:
            driver_name = "crisis"
            seasonal_driver = metrics["crisis"]
        elif metrics["festival"]:
            driver_name = "festival"
            seasonal_driver = metrics["festival"]

        payloads.append(
            {
                "run_id": run_id,
                "config_path": config_path,
                "config_basename": config_basename,
                "cell_id": cell_id,
                "boundary_id": _boundary_id(cell_id),
                "alpha": _alpha_from_cell(cell_id),
                "period_steps": period_steps,
                "driver_name": driver_name,
                "frac_hier": frac_hier,
                "mean_frac_hier": float(sum(frac_hier) / len(frac_hier)),
                "span_p95_p05_frac_hier": float(p95 - p05),
                "seasonal_driver": seasonal_driver,
            }
        )

    if not payloads:
        raise ValueError("No successful runs loaded for sanity pass")
    return payloads


def _classify_settings(
    *,
    payloads: List[Dict[str, object]],
    tau_grid: Sequence[float],
    hysteresis_width: float,
    base_thresholds: RegimeThresholds,
) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []

    for tau in tau_grid:
        th = replace(base_thresholds, tau=float(tau))
        for run in payloads:
            result = classify_regime(
                run["frac_hier"],  # type: ignore[arg-type]
                period_steps=int(run["period_steps"]),  # type: ignore[arg-type]
                seasonal_driver=run["seasonal_driver"],  # type: ignore[arg-type]
                thresholds=th,
            )
            rows.append(
                _run_row(
                    run=run,
                    variant="single_threshold",
                    tau_center=float(tau),
                    tau_low=None,
                    tau_high=None,
                    result=result,
                )
            )

    for tau in tau_grid:
        tau = float(tau)
        low = max(0.0, tau - hysteresis_width)
        high = min(1.0, tau + hysteresis_width)
        if low >= high:
            continue
        th = replace(base_thresholds, tau=tau)
        for run in payloads:
            result = classify_regime_hysteresis(
                run["frac_hier"],  # type: ignore[arg-type]
                period_steps=int(run["period_steps"]),  # type: ignore[arg-type]
                lower_tau=low,
                upper_tau=high,
                seasonal_driver=run["seasonal_driver"],  # type: ignore[arg-type]
                thresholds=th,
            )
            rows.append(
                _run_row(
                    run=run,
                    variant="hysteresis",
                    tau_center=tau,
                    tau_low=low,
                    tau_high=high,
                    result=result,
                )
            )

    rows.sort(
        key=lambda r: (
            r["variant"],
            float(r["tau_center"]),
            r["boundary_id"],
            float(r["alpha"]) if r["alpha"] else -1.0,
            r["run_id"],
        )
    )
    return rows


def _run_row(
    *,
    run: Dict[str, object],
    variant: str,
    tau_center: float,
    tau_low: Optional[float],
    tau_high: Optional[float],
    result: object,
) -> Dict[str, str]:
    return {
        "run_id": str(run["run_id"]),
        "config_path": str(run["config_path"]),
        "config_basename": str(run["config_basename"]),
        "cell_id": str(run["cell_id"]),
        "boundary_id": str(run["boundary_id"]),
        "alpha": str(run["alpha"]),
        "variant": variant,
        "tau_center": f"{tau_center:.4f}",
        "tau_low": "" if tau_low is None else f"{tau_low:.4f}",
        "tau_high": "" if tau_high is None else f"{tau_high:.4f}",
        "label": str(result.label),  # type: ignore[attr-defined]
        "confidence": f"{float(result.confidence):.6f}",  # type: ignore[attr-defined]
        "duty": f"{float(result.duty):.6f}",  # type: ignore[attr-defined]
        "switch_count": str(int(result.switch_count)),  # type: ignore[attr-defined]
        "switch_rate": f"{float(result.switch_rate):.6f}",  # type: ignore[attr-defined]
        "max_dwell_hier": str(int(result.max_dwell_hier)),  # type: ignore[attr-defined]
        "max_dwell_egal": str(int(result.max_dwell_egal)),  # type: ignore[attr-defined]
        "seasonal_coherence": (
            ""
            if result.seasonal_coherence is None  # type: ignore[attr-defined]
            else f"{float(result.seasonal_coherence):.6f}"  # type: ignore[attr-defined]
        ),
        "seasonal_lag": (
            ""
            if result.seasonal_lag is None  # type: ignore[attr-defined]
            else str(int(result.seasonal_lag))  # type: ignore[attr-defined]
        ),
        "period_steps": str(int(run["period_steps"])),
        "driver_name": str(run["driver_name"]),
        "mean_frac_hier": f"{float(run['mean_frac_hier']):.6f}",
        "span_p95_p05_frac_hier": f"{float(run['span_p95_p05_frac_hier']):.6f}",
    }


def _cell_rows(
    *,
    run_rows: Sequence[Dict[str, str]],
    target_label: str,
    min_successes: int,
    min_replicates: int,
) -> List[Dict[str, str]]:
    grouped: Dict[Tuple[str, str, str, str, str, str, str], Dict[str, object]] = {}

    for row in run_rows:
        label = row.get("label", "")
        if label not in LABELS:
            continue
        key = (
            row["variant"],
            row["tau_center"],
            row["tau_low"],
            row["tau_high"],
            row["cell_id"],
            row["boundary_id"],
            row["alpha"],
        )
        g = grouped.setdefault(
            key,
            {
                "variant": row["variant"],
                "tau_center": row["tau_center"],
                "tau_low": row["tau_low"],
                "tau_high": row["tau_high"],
                "cell_id": row["cell_id"],
                "boundary_id": row["boundary_id"],
                "alpha": row["alpha"],
                "counts": {k: 0 for k in LABELS},
                "mean_frac_hier_values": [],
                "span_values": [],
            },
        )
        g["counts"][label] += 1  # type: ignore[index]
        g["mean_frac_hier_values"].append(float(row["mean_frac_hier"]))  # type: ignore[index]
        g["span_values"].append(float(row["span_p95_p05_frac_hier"]))  # type: ignore[index]

    out: List[Dict[str, str]] = []
    for key, g in grouped.items():
        counts: Dict[str, int] = g["counts"]  # type: ignore[assignment]
        n = sum(counts.values())
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        maj_label, maj_count = ranked[0]
        target_count = counts.get(target_label, 0)
        pass_target = int(n >= min_replicates and target_count >= min_successes)
        mean_frac_vals: List[float] = g["mean_frac_hier_values"]  # type: ignore[assignment]
        span_vals: List[float] = g["span_values"]  # type: ignore[assignment]
        out.append(
            {
                "variant": str(g["variant"]),
                "tau_center": str(g["tau_center"]),
                "tau_low": str(g["tau_low"]),
                "tau_high": str(g["tau_high"]),
                "cell_id": str(g["cell_id"]),
                "boundary_id": str(g["boundary_id"]),
                "alpha": str(g["alpha"]),
                "n_replicates": str(n),
                "count_egalitarian": str(counts["egalitarian"]),
                "count_hierarchical": str(counts["hierarchical"]),
                "count_reversal": str(counts["reversal"]),
                "count_uncertain": str(counts["uncertain"]),
                "p_egalitarian": f"{(counts['egalitarian'] / n) if n else 0.0:.6f}",
                "p_hierarchical": f"{(counts['hierarchical'] / n) if n else 0.0:.6f}",
                "p_reversal": f"{(counts['reversal'] / n) if n else 0.0:.6f}",
                "p_uncertain": f"{(counts['uncertain'] / n) if n else 0.0:.6f}",
                "majority_label": maj_label,
                "majority_count": str(maj_count),
                "majority_fraction": f"{(maj_count / n) if n else 0.0:.6f}",
                "mean_frac_hier_avg": f"{(sum(mean_frac_vals) / len(mean_frac_vals)) if mean_frac_vals else 0.0:.6f}",
                "span_p95_p05_frac_hier_avg": f"{(sum(span_vals) / len(span_vals)) if span_vals else 0.0:.6f}",
                "target_label": target_label,
                "target_count": str(target_count),
                "min_successes": str(min_successes),
                "min_replicates": str(min_replicates),
                "pass_target": str(pass_target),
            }
        )

    out.sort(
        key=lambda r: (
            r["variant"],
            float(r["tau_center"]),
            r["boundary_id"],
            float(r["alpha"]) if r["alpha"] else -1.0,
        )
    )
    return out


def _cell_stability_rows(cell_rows: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    grouped: Dict[Tuple[str, str, str, str], List[Dict[str, str]]] = defaultdict(list)
    for row in cell_rows:
        grouped[(row["variant"], row["cell_id"], row["boundary_id"], row["alpha"])].append(row)

    out: List[Dict[str, str]] = []
    for (variant, cell_id, boundary_id, alpha), rows in sorted(grouped.items()):
        target_label = rows[0]["target_label"]
        p_target = [float(r[f"p_{target_label}"]) for r in rows]
        pass_flags = [int(r["pass_target"]) for r in rows]
        majorities = Counter(r["majority_label"] for r in rows)
        mode_label, mode_count = sorted(majorities.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        n = len(rows)
        out.append(
            {
                "variant": variant,
                "cell_id": cell_id,
                "boundary_id": boundary_id,
                "alpha": alpha,
                "target_label": target_label,
                "n_settings": str(n),
                "p_target_min": f"{min(p_target):.6f}",
                "p_target_max": f"{max(p_target):.6f}",
                "p_target_span": f"{(max(p_target) - min(p_target)):.6f}",
                "p_target_mean": f"{(sum(p_target) / n):.6f}",
                "n_settings_pass": str(sum(pass_flags)),
                "pass_any": str(int(any(pass_flags))),
                "pass_all": str(int(all(pass_flags))),
                "majority_mode_label": mode_label,
                "majority_mode_count": str(mode_count),
            }
        )
    return out


def _boundary_setting_rows(
    *,
    cell_rows: Sequence[Dict[str, str]],
    min_cells_passing_boundary: int,
) -> List[Dict[str, str]]:
    grouped: Dict[Tuple[str, str, str, str, str], List[Dict[str, str]]] = defaultdict(list)
    for row in cell_rows:
        grouped[
            (
                row["variant"],
                row["tau_center"],
                row["tau_low"],
                row["tau_high"],
                row["boundary_id"],
            )
        ].append(row)

    out: List[Dict[str, str]] = []
    for (variant, tau_center, tau_low, tau_high, boundary_id), rows in sorted(grouped.items()):
        n_cells = len(rows)
        n_pass = sum(int(r["pass_target"]) for r in rows)
        out.append(
            {
                "variant": variant,
                "tau_center": tau_center,
                "tau_low": tau_low,
                "tau_high": tau_high,
                "boundary_id": boundary_id,
                "n_cells": str(n_cells),
                "n_cells_passing_target": str(n_pass),
                "pass_fraction": f"{(n_pass / n_cells) if n_cells else 0.0:.6f}",
                "min_cells_passing_boundary": str(min_cells_passing_boundary),
                "boundary_pass": str(int(n_pass >= min_cells_passing_boundary)),
            }
        )
    return out


def _boundary_stability_rows(
    boundary_setting_rows: Sequence[Dict[str, str]],
) -> List[Dict[str, str]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, str]]] = defaultdict(list)
    for row in boundary_setting_rows:
        grouped[(row["variant"], row["boundary_id"])].append(row)

    out: List[Dict[str, str]] = []
    for (variant, boundary_id), rows in sorted(grouped.items()):
        n_settings = len(rows)
        pass_flags = [int(r["boundary_pass"]) for r in rows]
        n_pass = sum(pass_flags)
        n_cells_pass = [int(r["n_cells_passing_target"]) for r in rows]
        out.append(
            {
                "variant": variant,
                "boundary_id": boundary_id,
                "n_settings": str(n_settings),
                "n_settings_boundary_pass": str(n_pass),
                "boundary_pass_fraction": f"{(n_pass / n_settings) if n_settings else 0.0:.6f}",
                "boundary_pass_any": str(int(any(pass_flags))),
                "boundary_pass_all": str(int(all(pass_flags))),
                "min_n_cells_passing": str(min(n_cells_pass)),
                "max_n_cells_passing": str(max(n_cells_pass)),
            }
        )
    return out


def _default_path(base_dir: Path, filename: str, override: Optional[Path]) -> Path:
    return override if override is not None else (base_dir / filename)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2 strict sanity pass")
    parser.add_argument(
        "--run-root",
        type=Path,
        required=True,
        help="Run root containing run_index.csv",
    )
    parser.add_argument(
        "--analysis-csv",
        type=Path,
        default=None,
        help="Optional analysis table to filter run_id scope",
    )
    parser.add_argument(
        "--base-thresholds",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase2" / "regime_thresholds_tau08_sensitivity.yaml",
        help="Base threshold YAML (tau will be overridden by tau-grid values)",
    )
    parser.add_argument(
        "--tau-grid",
        type=str,
        default="0.76,0.78,0.80,0.82,0.84",
        help="Comma-separated tau ensemble values",
    )
    parser.add_argument(
        "--hysteresis-width",
        type=float,
        default=0.02,
        help="Half-width for hysteresis (lower=tau-width, upper=tau+width)",
    )
    parser.add_argument(
        "--target-label",
        type=str,
        default="reversal",
        choices=LABELS,
        help="Label used for pass/fail counts",
    )
    parser.add_argument(
        "--min-successes",
        type=int,
        default=4,
        help="Minimum target-label successes required per cell",
    )
    parser.add_argument(
        "--min-replicates",
        type=int,
        default=5,
        help="Minimum replicates required per cell",
    )
    parser.add_argument(
        "--min-cells-passing-boundary",
        type=int,
        default=3,
        help="Strict boundary pass threshold",
    )
    parser.add_argument("--runs-output", type=Path, default=None)
    parser.add_argument("--cells-output", type=Path, default=None)
    parser.add_argument("--cell-stability-output", type=Path, default=None)
    parser.add_argument("--boundary-settings-output", type=Path, default=None)
    parser.add_argument("--boundary-stability-output", type=Path, default=None)
    args = parser.parse_args()

    base_dir = args.run_root
    runs_output = _default_path(base_dir, "sanity_threshold_ensemble_runs.csv", args.runs_output)
    cells_output = _default_path(base_dir, "sanity_threshold_ensemble_cells.csv", args.cells_output)
    cell_stability_output = _default_path(
        base_dir, "sanity_threshold_stability_cells.csv", args.cell_stability_output
    )
    boundary_settings_output = _default_path(
        base_dir, "sanity_threshold_boundary_settings.csv", args.boundary_settings_output
    )
    boundary_stability_output = _default_path(
        base_dir, "sanity_threshold_boundary_stability.csv", args.boundary_stability_output
    )

    tau_grid = _parse_csv_floats(args.tau_grid)
    base_thresholds = load_regime_thresholds(args.base_thresholds)
    payloads = _load_run_payloads(args.run_root, analysis_csv=args.analysis_csv)

    run_rows = _classify_settings(
        payloads=payloads,
        tau_grid=tau_grid,
        hysteresis_width=float(args.hysteresis_width),
        base_thresholds=base_thresholds,
    )
    cell_rows = _cell_rows(
        run_rows=run_rows,
        target_label=args.target_label,
        min_successes=int(args.min_successes),
        min_replicates=int(args.min_replicates),
    )
    cell_stability_rows = _cell_stability_rows(cell_rows)
    boundary_setting_rows = _boundary_setting_rows(
        cell_rows=cell_rows,
        min_cells_passing_boundary=int(args.min_cells_passing_boundary),
    )
    boundary_stability_rows = _boundary_stability_rows(boundary_setting_rows)

    _write_csv(
        runs_output,
        run_rows,
        [
            "run_id",
            "config_path",
            "config_basename",
            "cell_id",
            "boundary_id",
            "alpha",
            "variant",
            "tau_center",
            "tau_low",
            "tau_high",
            "label",
            "confidence",
            "duty",
            "switch_count",
            "switch_rate",
            "max_dwell_hier",
            "max_dwell_egal",
            "seasonal_coherence",
            "seasonal_lag",
            "period_steps",
            "driver_name",
            "mean_frac_hier",
            "span_p95_p05_frac_hier",
        ],
    )
    _write_csv(
        cells_output,
        cell_rows,
        [
            "variant",
            "tau_center",
            "tau_low",
            "tau_high",
            "cell_id",
            "boundary_id",
            "alpha",
            "n_replicates",
            "count_egalitarian",
            "count_hierarchical",
            "count_reversal",
            "count_uncertain",
            "p_egalitarian",
            "p_hierarchical",
            "p_reversal",
            "p_uncertain",
            "majority_label",
            "majority_count",
            "majority_fraction",
            "mean_frac_hier_avg",
            "span_p95_p05_frac_hier_avg",
            "target_label",
            "target_count",
            "min_successes",
            "min_replicates",
            "pass_target",
        ],
    )
    _write_csv(
        cell_stability_output,
        cell_stability_rows,
        [
            "variant",
            "cell_id",
            "boundary_id",
            "alpha",
            "target_label",
            "n_settings",
            "p_target_min",
            "p_target_max",
            "p_target_span",
            "p_target_mean",
            "n_settings_pass",
            "pass_any",
            "pass_all",
            "majority_mode_label",
            "majority_mode_count",
        ],
    )
    _write_csv(
        boundary_settings_output,
        boundary_setting_rows,
        [
            "variant",
            "tau_center",
            "tau_low",
            "tau_high",
            "boundary_id",
            "n_cells",
            "n_cells_passing_target",
            "pass_fraction",
            "min_cells_passing_boundary",
            "boundary_pass",
        ],
    )
    _write_csv(
        boundary_stability_output,
        boundary_stability_rows,
        [
            "variant",
            "boundary_id",
            "n_settings",
            "n_settings_boundary_pass",
            "boundary_pass_fraction",
            "boundary_pass_any",
            "boundary_pass_all",
            "min_n_cells_passing",
            "max_n_cells_passing",
        ],
    )

    by_variant = Counter(r["variant"] for r in run_rows)
    print(f"Loaded runs: {len(payloads)}")
    print(f"Tau grid: {tau_grid}")
    print(f"Run-level rows: {len(run_rows)} by_variant={dict(by_variant)}")
    print(f"Cell-level rows: {len(cell_rows)}")
    print(f"Cell stability rows: {len(cell_stability_rows)}")
    print(f"Boundary setting rows: {len(boundary_setting_rows)}")
    print(f"Boundary stability rows: {len(boundary_stability_rows)}")
    print(f"Wrote: {runs_output}")
    print(f"Wrote: {cells_output}")
    print(f"Wrote: {cell_stability_output}")
    print(f"Wrote: {boundary_settings_output}")
    print(f"Wrote: {boundary_stability_output}")


if __name__ == "__main__":
    main()
