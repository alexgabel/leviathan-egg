#!/usr/bin/env python3
"""Select objective representative runs and plot required Phase 2 series.

Outputs:
- representative_cases.csv (selected runs, one per requested regime label)
- fig_representative_<label>.png (frac_hier, festival, crisis)
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Dict, List, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

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


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (ROOT / p).resolve()


def _parse_float(row: Dict[str, str], key: str, *, default: float = 0.0) -> float:
    raw = row.get(key, "")
    if raw == "":
        return default
    return float(raw)


def _parse_int(row: Dict[str, str], key: str, *, default: int = 0) -> int:
    raw = row.get(key, "")
    if raw == "":
        return default
    return int(float(raw))


def _load_allowed_run_ids(analysis_csv: Path | None) -> set[str]:
    if analysis_csv is None:
        return set()
    rows = _read_csv(analysis_csv)
    return {r["run_id"] for r in rows if r.get("run_id")}


def _join_candidates(
    *,
    run_rows: Sequence[Dict[str, str]],
    label_rows: Sequence[Dict[str, str]],
    allowed_run_ids: set[str],
    include_labels: set[str],
) -> List[Dict[str, str]]:
    run_by_id = {r["run_id"]: r for r in run_rows if r.get("status") == "SUCCESS"}

    out: List[Dict[str, str]] = []
    for lab in label_rows:
        run_id = lab.get("run_id", "")
        if not run_id:
            continue
        if allowed_run_ids and run_id not in allowed_run_ids:
            continue

        label = lab.get("label", "")
        if label not in include_labels:
            continue

        run = run_by_id.get(run_id)
        if run is None:
            continue

        merged = {
            "run_id": run_id,
            "label": label,
            "config_path": run.get("config_path", lab.get("config_path", "")),
            "run_dir": run.get("run_dir", lab.get("run_dir", "")),
            "metrics_path": run.get("metrics_path", ""),
            "confidence": f"{_parse_float(lab, 'confidence', default=0.0):.6f}",
            "duty": f"{_parse_float(lab, 'duty', default=0.0):.6f}",
            "switch_rate": f"{_parse_float(lab, 'switch_rate', default=0.0):.6f}",
            "max_dwell_hier": str(_parse_int(lab, "max_dwell_hier", default=0)),
            "max_dwell_egal": str(_parse_int(lab, "max_dwell_egal", default=0)),
            "seasonal_coherence": f"{_parse_float(lab, 'seasonal_coherence', default=0.0):.6f}",
            "seasonal_lag": lab.get("seasonal_lag", ""),
            "end_time": run.get("end_time", ""),
        }
        out.append(merged)

    return out


def _feature_vector(row: Dict[str, str]) -> List[float]:
    return [
        _parse_float(row, "duty"),
        _parse_float(row, "switch_rate"),
        _parse_float(row, "max_dwell_hier"),
        _parse_float(row, "max_dwell_egal"),
        _parse_float(row, "seasonal_coherence"),
    ]


def _pick_highest_confidence(rows: Sequence[Dict[str, str]]) -> tuple[Dict[str, str], float]:
    chosen = sorted(
        rows,
        key=lambda r: (
            -_parse_float(r, "confidence"),
            r.get("end_time", ""),
            r.get("run_id", ""),
        ),
    )[0]
    return chosen, _parse_float(chosen, "confidence")


def _pick_centroid(rows: Sequence[Dict[str, str]]) -> tuple[Dict[str, str], float]:
    vectors = [_feature_vector(r) for r in rows]
    dims = len(vectors[0])

    means = []
    stdevs = []
    for j in range(dims):
        col = [v[j] for v in vectors]
        mu = sum(col) / len(col)
        var = sum((x - mu) ** 2 for x in col) / len(col)
        sd = math.sqrt(var)
        means.append(mu)
        stdevs.append(sd if sd > 1e-9 else 1.0)

    scored: List[tuple[float, float, Dict[str, str]]] = []
    for row, vec in zip(rows, vectors):
        distance_sq = 0.0
        for j in range(dims):
            z = (vec[j] - means[j]) / stdevs[j]
            distance_sq += z * z
        distance = math.sqrt(distance_sq)
        confidence = _parse_float(row, "confidence", default=0.0)
        scored.append((distance, -confidence, row))

    scored.sort(key=lambda x: (x[0], x[1], x[2].get("run_id", "")))
    best_distance, _, best_row = scored[0]
    return best_row, best_distance


def _select_representatives(
    rows: Sequence[Dict[str, str]],
    *,
    labels_in_order: Sequence[str],
    method: str,
) -> List[Dict[str, str]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["label"], []).append(row)

    selected: List[Dict[str, str]] = []
    for label in labels_in_order:
        candidates = grouped.get(label, [])
        if not candidates:
            continue

        if method == "highest_confidence":
            chosen, score = _pick_highest_confidence(candidates)
            score_name = "confidence"
        elif method == "centroid":
            chosen, score = _pick_centroid(candidates)
            score_name = "distance_to_centroid"
        else:
            raise ValueError(f"Unsupported method: {method}")

        out_row = dict(chosen)
        out_row["selection_method"] = method
        out_row["selection_score_name"] = score_name
        out_row["selection_score"] = f"{score:.6f}"
        selected.append(out_row)

    return selected


def _read_series(metrics_path: Path) -> tuple[List[float], List[float], List[float], List[float]]:
    with metrics_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"Empty metrics file: {metrics_path}")

    required = ("frac_hier", "festival", "crisis")
    for key in required:
        if key not in rows[0]:
            raise ValueError(f"Missing required series '{key}' in metrics: {metrics_path}")

    t: List[float] = []
    frac_hier: List[float] = []
    festival: List[float] = []
    crisis: List[float] = []
    for i, row in enumerate(rows):
        t.append(float(row.get("t", i)))
        frac_hier.append(float(row["frac_hier"]))
        festival.append(float(row["festival"]))
        crisis.append(float(row["crisis"]))

    return t, frac_hier, festival, crisis


def _plot_representative(
    row: Dict[str, str],
    *,
    plot_dir: Path,
    tau: float,
    dpi: int,
) -> Path:
    metrics_path = row.get("metrics_path", "")
    if metrics_path:
        mpath = _resolve_path(metrics_path)
    else:
        mpath = _resolve_path(row["run_dir"]) / "metrics.csv"
    if not mpath.exists():
        raise FileNotFoundError(f"Missing metrics file for representative run: {mpath}")

    t, frac_hier, festival, crisis = _read_series(mpath)

    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True, constrained_layout=True)

    axes[0].plot(t, frac_hier, color="#1f77b4", linewidth=1.5)
    axes[0].axhline(y=tau, color="#444444", linestyle="--", linewidth=1.2)
    axes[0].set_ylabel("frac_hier")
    axes[0].set_ylim(-0.02, 1.02)
    axes[0].grid(alpha=0.25)

    axes[1].plot(t, festival, color="#ff7f0e", linewidth=1.2)
    axes[1].set_ylabel("festival")
    axes[1].grid(alpha=0.25)

    axes[2].plot(t, crisis, color="#2ca02c", linewidth=1.2)
    axes[2].set_ylabel("crisis")
    axes[2].set_xlabel("t")
    axes[2].grid(alpha=0.25)

    fig.suptitle(
        (
            f"Representative {row['label']} run | {row['run_id']}\n"
            f"method={row['selection_method']} {row['selection_score_name']}={row['selection_score']}, "
            f"confidence={row['confidence']}"
        ),
        fontsize=12,
    )

    plot_dir.mkdir(parents=True, exist_ok=True)
    out_path = plot_dir / f"fig_representative_{row['label']}.png"
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    return out_path


def _split_csv_tokens(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select representative Phase 2 runs objectively and plot required series."
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase2",
        help="Run root containing run_index.csv",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=None,
        help="Labels CSV path (defaults to <run-root>/regime_labels.csv)",
    )
    parser.add_argument(
        "--analysis-csv",
        type=Path,
        default=None,
        help="Optional pre-filtered analysis table with run_id column",
    )
    parser.add_argument(
        "--method",
        choices=["highest_confidence", "centroid"],
        default="highest_confidence",
        help="Objective selection rule",
    )
    parser.add_argument(
        "--include-labels",
        type=str,
        default="reversal,hierarchical,egalitarian,uncertain",
        help="Comma-separated labels to select (order preserved)",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Output CSV for selected representatives",
    )
    parser.add_argument(
        "--plot-dir",
        type=Path,
        default=None,
        help="Directory for representative plots",
    )
    parser.add_argument(
        "--tau",
        type=float,
        default=0.5,
        help="Threshold line for frac_hier panel",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=160,
        help="PNG output DPI",
    )
    args = parser.parse_args()

    labels_path = args.labels if args.labels is not None else (args.run_root / "regime_labels.csv")
    output_csv = (
        args.output_csv
        if args.output_csv is not None
        else (args.run_root / "representative_cases.csv")
    )
    plot_dir = (
        args.plot_dir
        if args.plot_dir is not None
        else (args.run_root / "representative_plots")
    )

    run_rows = _read_csv(args.run_root / "run_index.csv")
    label_rows = _read_csv(labels_path)
    include_labels_list = _split_csv_tokens(args.include_labels)
    include_labels = set(include_labels_list)
    allowed_run_ids = _load_allowed_run_ids(args.analysis_csv)

    candidates = _join_candidates(
        run_rows=run_rows,
        label_rows=label_rows,
        allowed_run_ids=allowed_run_ids,
        include_labels=include_labels,
    )
    if not candidates:
        raise ValueError("No candidate runs found after filtering.")

    selected = _select_representatives(
        candidates,
        labels_in_order=include_labels_list,
        method=args.method,
    )
    if not selected:
        raise ValueError("No representative runs selected; verify labels and filtering.")

    for row in selected:
        plot_path = _plot_representative(row, plot_dir=plot_dir, tau=args.tau, dpi=args.dpi)
        row["plot_path"] = str(plot_path)

    fieldnames = [
        "run_id",
        "label",
        "selection_method",
        "selection_score_name",
        "selection_score",
        "confidence",
        "duty",
        "switch_rate",
        "max_dwell_hier",
        "max_dwell_egal",
        "seasonal_coherence",
        "seasonal_lag",
        "config_path",
        "run_dir",
        "metrics_path",
        "plot_path",
        "end_time",
    ]
    _write_csv(output_csv, selected, fieldnames)

    print(f"Candidates considered: {len(candidates)}")
    print(f"Selected representatives: {len(selected)} ({args.method})")
    for row in selected:
        print(
            f"  - {row['label']}: run_id={row['run_id']} "
            f"{row['selection_score_name']}={row['selection_score']} "
            f"plot={row['plot_path']}"
        )
    print(f"Wrote representative table: {output_csv}")


if __name__ == "__main__":
    main()
