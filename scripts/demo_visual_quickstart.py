#!/usr/bin/env python3
"""Run visual demo scenario packs and generate shareable galleries."""

from __future__ import annotations

import argparse
import csv
import os
from itertools import combinations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".mplconfig"))

import matplotlib.pyplot as plt
import numpy as np
import yaml

from leviathan_egg.cli import run_simulation


@dataclass(frozen=True)
class DemoScenario:
    scenario_id: str
    title: str
    config_file: str


SCENARIO_PACKS: Dict[str, List[DemoScenario]] = {
    "demo": [
        DemoScenario(
            scenario_id="single_patch_reversal",
            title="Single-Patch Seasonal Reversal",
            config_file="demo_single_patch_reversal.yaml",
        ),
        DemoScenario(
            scenario_id="multipatch_uncoupled",
            title="Multi-Patch Uncoupled Baseline",
            config_file="demo_multipatch_uncoupled.yaml",
        ),
        DemoScenario(
            scenario_id="multipatch_sync_positive",
            title="Multi-Patch Positive Coupling (Synchrony Tendency)",
            config_file="demo_multipatch_sync_positive.yaml",
        ),
        DemoScenario(
            scenario_id="multipatch_desync_negative",
            title="Multi-Patch Negative Coupling (Desync Tendency)",
            config_file="demo_multipatch_desync_negative.yaml",
        ),
    ],
    "demo_v2": [
        DemoScenario(
            scenario_id="v2_single_patch_reversal",
            title="V2 Single-Patch Seasonal Reversal",
            config_file="demo_v2_single_patch_reversal.yaml",
        ),
        DemoScenario(
            scenario_id="v2_multipatch_uncoupled",
            title="V2 Multi-Patch Uncoupled Baseline",
            config_file="demo_v2_multipatch_uncoupled.yaml",
        ),
        DemoScenario(
            scenario_id="v2_multipatch_sync_positive",
            title="V2 Multi-Patch Strong Positive Coupling",
            config_file="demo_v2_multipatch_sync_positive.yaml",
        ),
        DemoScenario(
            scenario_id="v2_multipatch_desync_negative",
            title="V2 Multi-Patch Strong Negative Coupling",
            config_file="demo_v2_multipatch_desync_negative.yaml",
        ),
    ],
}

DEFAULT_V2_SEEDS = [111, 222, 333]

SYNC_COLORS: Dict[str, str] = {
    "order": "tab:blue",
    "lock": "tab:orange",
    "anti-phase": "tab:green",
    "lag": "tab:red",
}

SCENARIO_COLORS: Dict[str, str] = {
    "uncoupled": "#4C78A8",
    "sync_positive": "#F58518",
    "desync_negative": "#54A24B",
}


def _read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _series(rows: List[Dict[str, str]], key: str) -> np.ndarray:
    if not rows or key not in rows[0]:
        return np.asarray([], dtype=float)
    return np.asarray([float(r[key]) for r in rows], dtype=float)


def _patch_keys(rows: List[Dict[str, str]]) -> List[str]:
    if not rows:
        return []
    keys: List[str] = []
    i = 0
    while True:
        k = f"frac_hier_patch_{i}"
        if k not in rows[0]:
            break
        keys.append(k)
        i += 1
    return keys


def _rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or values.size < window:
        return values
    kernel = np.ones(window, dtype=float) / float(window)
    return np.convolve(values, kernel, mode="same")


def _load_yaml(path: Path) -> Dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping YAML at {path}")
    return data


def _coupling_from_config(config_path: Path) -> Dict[str, str]:
    cfg = _load_yaml(config_path)
    coupling = cfg.get("inter_patch_coupling", {}) or {}
    return {
        "coupling_enabled": str(bool(coupling.get("enabled", False))).lower(),
        "coupling_mode": str(coupling.get("mode", "")),
        "coupling_sign": str(coupling.get("sign", "")),
        "coupling_strength": str(coupling.get("strength", "")),
        "coupling_lag_steps": str(coupling.get("lag_steps", "")),
    }


def _coupling_note(coupling: Dict[str, str]) -> str:
    if coupling.get("coupling_enabled", "false") != "true":
        return "coupling=off"
    return (
        "coupling=on "
        f"mode={coupling.get('coupling_mode','')} "
        f"sign={coupling.get('coupling_sign','')} "
        f"k={coupling.get('coupling_strength','')} "
        f"lag={coupling.get('coupling_lag_steps','')}"
    )


def _config_seed(config_path: Path) -> int:
    cfg = _load_yaml(config_path)
    runtime = cfg.get("runtime_and_reproducibility", {}) or {}
    return int(runtime.get("random_seed", 1))


def _burn_in_from_config(config_path: Path) -> int:
    cfg = _load_yaml(config_path)
    runtime = cfg.get("runtime_and_reproducibility", {}) or {}
    return int(runtime.get("burn_in_period", 0))


def _phase3_thresholds() -> Dict[str, float]:
    path = ROOT / "experiments" / "configs" / "phase3" / "desync_v2_thresholds.yaml"
    if not path.exists():
        return {}
    raw = _load_yaml(path)
    required = (
        "sync_order_hi",
        "sync_lock_hi",
        "sync_lag_hi",
        "desync_order_lo",
        "desync_lock_lo",
        "desync_lag_lo",
        "desync_antiphase_lo",
    )
    out: Dict[str, float] = {}
    for key in required:
        if key in raw:
            out[key] = float(raw[key])
    return out


def _scenario_color(scenario_id: str) -> str:
    for key, color in SCENARIO_COLORS.items():
        if key in scenario_id:
            return color
    return "#7f7f7f"


def _pairwise_best_lags(series_by_patch: List[np.ndarray], max_lag: int) -> Tuple[List[float], List[float]]:
    best_lags: List[float] = []
    zero_lag_corrs: List[float] = []
    for i, j in combinations(range(len(series_by_patch)), 2):
        xi = np.asarray(series_by_patch[i], dtype=float)
        xj = np.asarray(series_by_patch[j], dtype=float)
        m = min(xi.size, xj.size)
        if m < 8:
            continue
        xi = xi[-m:] - np.mean(xi[-m:])
        xj = xj[-m:] - np.mean(xj[-m:])
        denom = float(np.linalg.norm(xi) * np.linalg.norm(xj))
        if denom <= 1e-12:
            continue
        corr0 = float(np.dot(xi, xj) / denom)
        zero_lag_corrs.append(corr0)
        corr = np.correlate(xi, xj, mode="full")
        lags = np.arange(-m + 1, m)
        mask = np.abs(lags) <= max_lag
        if not np.any(mask):
            continue
        best = int(lags[mask][int(np.argmax(corr[mask]))])
        best_lags.append(float(best))
    return best_lags, zero_lag_corrs


def _burnin_span(t: np.ndarray, burn_in: int) -> Tuple[float, float] | None:
    if t.size == 0:
        return None
    t_min = float(t[0])
    t_max = float(t[-1])
    if not (t_min < float(burn_in) < t_max):
        return None
    # Show only if informative in displayed window (avoids tiny slivers in tail-only views).
    frac = (float(burn_in) - t_min) / max(1e-12, (t_max - t_min))
    if frac < 0.05:
        return None
    return t_min, float(burn_in)


def _seed_override_config_path(
    *,
    base_config_path: Path,
    scenario_id: str,
    seed: int,
    temp_dir: Path,
) -> Path:
    cfg = _load_yaml(base_config_path)
    meta = cfg.setdefault("meta", {})
    runtime = cfg.setdefault("runtime_and_reproducibility", {})
    if not isinstance(meta, dict) or not isinstance(runtime, dict):
        raise ValueError(f"Invalid config sections in {base_config_path}")

    base_name = str(meta.get("experiment_name", scenario_id))
    meta["experiment_name"] = f"{base_name}_s{seed}"
    runtime["random_seed"] = int(seed)

    temp_dir.mkdir(parents=True, exist_ok=True)
    out_path = temp_dir / f"{scenario_id}_seed{seed}.yaml"
    out_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return out_path


def _aggregate_metric(
    runs: List[List[Dict[str, str]]],
    key: str,
    *,
    tail_rows: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    arrays: List[np.ndarray] = []
    t_arrays: List[np.ndarray] = []

    for rows in runs:
        if not rows or key not in rows[0] or "t" not in rows[0]:
            continue
        vals = _series(rows, key)
        t = _series(rows, "t")
        if tail_rows > 0 and vals.size > tail_rows:
            vals = vals[-tail_rows:]
            t = t[-tail_rows:]
        arrays.append(vals)
        t_arrays.append(t)

    if not arrays:
        return np.asarray([]), np.asarray([]), np.asarray([])

    m = min(len(a) for a in arrays)
    aligned = np.vstack([a[-m:] for a in arrays])
    t = t_arrays[0][-m:]
    return t, np.mean(aligned, axis=0), np.std(aligned, axis=0)


def _plot_demo_ribbon(
    *,
    runs: List[List[Dict[str, str]]],
    scenario: DemoScenario,
    output_path: Path,
    tail_rows: int,
    smoothing_window: int,
    coupling: Dict[str, str],
    seeds: List[int],
    burn_in: int,
    thresholds: Dict[str, float],
) -> None:
    if not runs:
        raise ValueError("No runs available to plot")

    has_sync = "synchrony_order_parameter" in runs[0][0]
    nrows = 3 if has_sync else 2
    fig, axes = plt.subplots(nrows, 1, figsize=(11, 8), sharex=True)
    if nrows == 2:
        ax_hier, ax_driver = axes
        ax_sync = None
    else:
        ax_hier, ax_driver, ax_sync = axes

    t_h, frac_mean, frac_std = _aggregate_metric(runs, "frac_hier", tail_rows=tail_rows)
    if t_h.size == 0:
        raise ValueError("Missing frac_hier series")

    frac_mean_s = _rolling_mean(frac_mean, smoothing_window)
    frac_lo_s = _rolling_mean(frac_mean - frac_std, smoothing_window)
    frac_hi_s = _rolling_mean(frac_mean + frac_std, smoothing_window)
    ax_hier.plot(t_h, frac_mean_s, color=SYNC_COLORS["order"], linewidth=1.8, label="frac_hier mean")
    ax_hier.fill_between(
        t_h, frac_lo_s, frac_hi_s, color=SYNC_COLORS["order"], alpha=0.20, label="±1σ (seeds)"
    )
    ax_hier.set_ylabel("frac_hier")
    ax_hier.set_ylim(-0.02, 1.02)
    ax_hier.grid(alpha=0.25)
    ax_hier.legend(loc="upper right", frameon=False)

    driver_rows = runs[0]
    if tail_rows > 0 and len(driver_rows) > tail_rows:
        driver_rows = driver_rows[-tail_rows:]
    t_d = _series(driver_rows, "t")
    festival = _series(driver_rows, "festival")
    crisis = _series(driver_rows, "crisis")
    if festival.size:
        ax_driver.plot(t_d, festival, label="festival", linewidth=1.1)
    if crisis.size:
        ax_driver.plot(t_d, crisis, label="crisis", linewidth=1.1)
    ax_driver.set_ylabel("seasonal drivers")
    ax_driver.grid(alpha=0.25)
    h_drv, _ = ax_driver.get_legend_handles_labels()
    if h_drv:
        ax_driver.legend(loc="upper right", frameon=False)

    if ax_sync is not None:
        sync_defs = [
            ("synchrony_order_parameter", "order", SYNC_COLORS["order"]),
            ("synchrony_phase_lock_fraction", "lock", SYNC_COLORS["lock"]),
            ("synchrony_antiphase_fraction", "anti-phase", SYNC_COLORS["anti-phase"]),
        ]
        for key, label, color in sync_defs:
            t, m, s = _aggregate_metric(runs, key, tail_rows=tail_rows)
            if t.size == 0:
                continue
            m_s = _rolling_mean(m, smoothing_window)
            lo_s = _rolling_mean(m - s, smoothing_window)
            hi_s = _rolling_mean(m + s, smoothing_window)
            ax_sync.plot(t, m_s, color=color, linewidth=1.3, label=f"{label} mean")
            ax_sync.fill_between(t, lo_s, hi_s, color=color, alpha=0.12)

        ax_sync.set_ylabel("sync metrics")
        ax_sync.set_ylim(-0.02, 1.02)
        ax_sync.grid(alpha=0.25)

        t_lag, lag_m, lag_s = _aggregate_metric(runs, "synchrony_mean_abs_phase_lag", tail_rows=tail_rows)
        ax_sync_lag = ax_sync.twinx()
        if t_lag.size:
            lag_m_s = _rolling_mean(lag_m, smoothing_window)
            lag_lo_s = _rolling_mean(lag_m - lag_s, smoothing_window)
            lag_hi_s = _rolling_mean(lag_m + lag_s, smoothing_window)
            ax_sync_lag.plot(
                t_lag, lag_m_s, color=SYNC_COLORS["lag"], linewidth=1.2, alpha=0.85, label="lag mean"
            )
            ax_sync_lag.fill_between(t_lag, lag_lo_s, lag_hi_s, color=SYNC_COLORS["lag"], alpha=0.10)
        ax_sync_lag.set_ylabel("mean abs lag")

        # Threshold diagnostics: draw guides without dense inline text labels.
        if thresholds and t_h.size:
            if "desync_order_lo" in thresholds:
                y = thresholds["desync_order_lo"]
                ax_sync.axhline(
                    y,
                    color=SYNC_COLORS["order"],
                    linestyle="--",
                    linewidth=0.9,
                    alpha=0.7,
                    label="order threshold",
                )
            if "desync_lock_lo" in thresholds:
                y = thresholds["desync_lock_lo"]
                ax_sync.axhline(
                    y,
                    color=SYNC_COLORS["lock"],
                    linestyle="--",
                    linewidth=0.9,
                    alpha=0.7,
                    label="lock threshold",
                )
            if "desync_antiphase_lo" in thresholds:
                y = thresholds["desync_antiphase_lo"]
                ax_sync.axhline(
                    y,
                    color=SYNC_COLORS["anti-phase"],
                    linestyle="--",
                    linewidth=0.9,
                    alpha=0.7,
                    label="anti-phase threshold",
                )
            if "desync_lag_lo" in thresholds:
                y = thresholds["desync_lag_lo"]
                ax_sync_lag.axhline(
                    y,
                    color=SYNC_COLORS["lag"],
                    linestyle="--",
                    linewidth=0.9,
                    alpha=0.7,
                    label="lag threshold",
                )

        h1, l1 = ax_sync.get_legend_handles_labels()
        h2, l2 = ax_sync_lag.get_legend_handles_labels()
        if h1 or h2:
            ax_sync.legend(h1 + h2, l1 + l2, loc="upper right", frameon=False)

    # Burn-in diagnostics: shaded region where transients are expected.
    span = _burnin_span(t_h, burn_in=burn_in)
    if span is not None:
        x0, x1 = span
        for ax in axes:
            ax.axvspan(x0, x1, color="gray", alpha=0.10, zorder=0)
        ax_hier.text(
            x0 + 0.01 * (float(t_h[-1]) - float(t_h[0])),
            0.05,
            "burn-in",
            color="gray",
            fontsize=8,
            va="bottom",
        )

    axes[-1].set_xlabel("t")

    seed_note = ",".join(str(s) for s in seeds)
    fig.suptitle(
        f"{scenario.title}\n"
        f"{scenario.config_file} | {_coupling_note(coupling)} | seeds=[{seed_note}]",
        y=0.99,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _replicate_summary(rows: List[Dict[str, str]]) -> Dict[str, float]:
    def mean_of(key: str) -> float:
        vals = _series(rows, key)
        return float(np.mean(vals)) if vals.size else float("nan")

    return {
        "frac_hier_mean": mean_of("frac_hier"),
        "frac_hier_std": float(np.std(_series(rows, "frac_hier"))) if _series(rows, "frac_hier").size else float("nan"),
        "sync_order_mean": mean_of("synchrony_order_parameter"),
        "sync_lock_mean": mean_of("synchrony_phase_lock_fraction"),
        "sync_lag_mean": mean_of("synchrony_mean_abs_phase_lag"),
        "sync_antiphase_mean": mean_of("synchrony_antiphase_fraction"),
    }


def _nanmean_std(values: List[float]) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return float("nan"), float("nan")
    return float(np.mean(arr)), float(np.std(arr))


def _scenario_summary_row(
    *,
    scenario: DemoScenario,
    config_path: Path,
    figure_path: Path,
    run_dirs: List[Path],
    replicate_seeds: List[int],
    replicate_summaries: List[Dict[str, float]],
    coupling: Dict[str, str],
) -> Dict[str, str]:
    out: Dict[str, str] = {
        "scenario_id": scenario.scenario_id,
        "title": scenario.title,
        "config_path": str(config_path),
        "run_dir_first": str(run_dirs[0]) if run_dirs else "",
        "figure_path": str(figure_path),
        "n_replicates": str(len(replicate_summaries)),
        "replicate_seeds": ",".join(str(s) for s in replicate_seeds),
        "coupling_enabled": coupling.get("coupling_enabled", ""),
        "coupling_mode": coupling.get("coupling_mode", ""),
        "coupling_sign": coupling.get("coupling_sign", ""),
        "coupling_strength": coupling.get("coupling_strength", ""),
        "coupling_lag_steps": coupling.get("coupling_lag_steps", ""),
    }

    for key in [
        "frac_hier_mean",
        "frac_hier_std",
        "sync_order_mean",
        "sync_lock_mean",
        "sync_lag_mean",
        "sync_antiphase_mean",
    ]:
        m, s = _nanmean_std([r.get(key, float("nan")) for r in replicate_summaries])
        out[key] = f"{m:.6f}" if not np.isnan(m) else ""
        out[f"{key}_seed_std"] = f"{s:.6f}" if not np.isnan(s) else ""

    return out


def _write_gallery_index(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scenario_id",
        "title",
        "config_path",
        "run_dir_first",
        "figure_path",
        "n_replicates",
        "replicate_seeds",
        "frac_hier_mean",
        "frac_hier_mean_seed_std",
        "frac_hier_std",
        "frac_hier_std_seed_std",
        "sync_order_mean",
        "sync_order_mean_seed_std",
        "sync_lock_mean",
        "sync_lock_mean_seed_std",
        "sync_lag_mean",
        "sync_lag_mean_seed_std",
        "sync_antiphase_mean",
        "sync_antiphase_mean_seed_std",
        "coupling_enabled",
        "coupling_mode",
        "coupling_sign",
        "coupling_strength",
        "coupling_lag_steps",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_replicate_index(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scenario_id",
        "title",
        "seed",
        "config_path",
        "effective_config_path",
        "run_dir",
        "metrics_path",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_gallery_markdown(path: Path, rows: List[Dict[str, str]], *, pack: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append(f"# Demo Visual Gallery ({pack})")
    lines.append("")
    lines.append("Visual-first scenarios with replicate ribbons (mean ± 1σ across seeds).")
    lines.append("")
    lines.append("## Executive Result Card (Read First)")
    lines.append("")
    lines.append("Compact table of deltas vs uncoupled, uncertainty-scaled magnitude, and directional call.")
    lines.append("")
    lines.append("![executive_card](demo_executive_result_card.png)")
    lines.append("")

    def fmt(mean_key: str, std_key: str, row: Dict[str, str]) -> str:
        mean_v = row.get(mean_key, "")
        std_v = row.get(std_key, "")
        if not mean_v:
            return "N/A"
        return f"{mean_v} ± {std_v if std_v else '0.000000'}"

    lines.append("## Cross-Scenario Story Views (Read First)")
    lines.append("")
    lines.append("These figures should be read before raw trajectories.")
    lines.append("")
    lines.append("1. Effect sizes with uncertainty (delta vs uncoupled)")
    lines.append("2. Smoothed synchrony overlays with ribbons")
    lines.append("3. Mechanistic sanity checks and boundary ambiguity panel")
    lines.append("")
    lines.append("![effect_deltas](demo_effect_deltas_vs_uncoupled.png)")
    lines.append("")
    lines.append("![sync_overlay](demo_sync_overlay_smoothed.png)")
    lines.append("")
    lines.append("![crosscorr_hist](demo_crosscorr_hist_by_scenario.png)")
    lines.append("")
    lines.append("![phase_offsets](demo_phase_offset_small_multiples.png)")
    lines.append("")
    lines.append("![failure_mode](demo_failure_mode_boundary.png)")
    lines.append("")

    lines.append("## Scenario-Level Raw and Ribbon Views (Then Drill Down)")
    lines.append("")
    for row in rows:
        fig_name = Path(row["figure_path"]).name
        lines.append(f"## {row['title']} (`{row['scenario_id']}`)")
        lines.append("")
        lines.append(f"- Config: `{row['config_path']}`")
        lines.append(f"- First run dir: `{row['run_dir_first']}`")
        lines.append(f"- Replicates: `{row['n_replicates']}` (seeds: `{row['replicate_seeds']}`)")
        lines.append(
            f"- Coupling: enabled={row['coupling_enabled']}, mode={row['coupling_mode']}, "
            f"sign={row['coupling_sign']}, strength={row['coupling_strength']}, lag={row['coupling_lag_steps']}"
        )
        lines.append(
            "- Summary (mean across seeds): "
            f"frac_hier={fmt('frac_hier_mean', 'frac_hier_mean_seed_std', row)}, "
            f"order={fmt('sync_order_mean', 'sync_order_mean_seed_std', row)}, "
            f"lock={fmt('sync_lock_mean', 'sync_lock_mean_seed_std', row)}, "
            f"lag={fmt('sync_lag_mean', 'sync_lag_mean_seed_std', row)}, "
            f"anti={fmt('sync_antiphase_mean', 'sync_antiphase_mean_seed_std', row)}"
        )
        lines.append("")
        lines.append(f"![{row['scenario_id']}]({fig_name})")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _as_float(row: Dict[str, str], key: str) -> float:
    raw = row.get(key, "")
    if raw in ("", "nan", "NaN"):
        return float("nan")
    return float(raw)


def _short_label(scenario_id: str) -> str:
    label = scenario_id
    label = label.replace("v2_", "")
    label = label.replace("multipatch_", "")
    return label


def _plot_effect_deltas(rows: List[Dict[str, str]], output_path: Path) -> None:
    multi = [r for r in rows if "multipatch_" in r.get("scenario_id", "")]
    base = next((r for r in multi if "multipatch_uncoupled" in r.get("scenario_id", "")), None)
    if base is None or len(multi) < 2:
        return

    compare = [r for r in multi if "multipatch_uncoupled" not in r.get("scenario_id", "")]
    metrics = [
        ("sync_order_mean", "sync_order_mean_seed_std", "order"),
        ("sync_lock_mean", "sync_lock_mean_seed_std", "lock"),
        ("sync_antiphase_mean", "sync_antiphase_mean_seed_std", "anti-phase"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))

    x = np.arange(len(compare))
    width = 0.22
    signal_to_noise: Dict[str, List[float]] = {"order": [], "lock": [], "anti-phase": [], "lag": []}
    for i, (mean_key, std_key, label) in enumerate(metrics):
        deltas = []
        errs = []
        for row in compare:
            d = _as_float(row, mean_key) - _as_float(base, mean_key)
            s = np.sqrt(_as_float(row, std_key) ** 2 + _as_float(base, std_key) ** 2)
            deltas.append(d)
            errs.append(s if not np.isnan(s) else 0.0)
            signal_to_noise[label].append(abs(d) / max(1e-9, s))
        axes[0].bar(
            x + (i - 1) * width,
            deltas,
            width=width,
            yerr=errs,
            capsize=3,
            label=f"Δ {label}",
            color=SYNC_COLORS[label],
        )
    axes[0].axhline(0.0, color="black", linewidth=1.0)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([_short_label(r["scenario_id"]) for r in compare], rotation=10)
    axes[0].set_ylabel("Delta vs uncoupled")
    axes[0].set_title("Synchrony deltas")
    axes[0].legend(frameon=False, fontsize=9)
    axes[0].grid(axis="y", alpha=0.25)

    lag_deltas = []
    lag_errs = []
    for row in compare:
        d = _as_float(row, "sync_lag_mean") - _as_float(base, "sync_lag_mean")
        s = np.sqrt(
            _as_float(row, "sync_lag_mean_seed_std") ** 2
            + _as_float(base, "sync_lag_mean_seed_std") ** 2
        )
        lag_deltas.append(d)
        lag_errs.append(s if not np.isnan(s) else 0.0)

    axes[1].bar(x, lag_deltas, width=0.5, color="tab:red", yerr=lag_errs, capsize=3)
    axes[1].axhline(0.0, color="black", linewidth=1.0)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([_short_label(r["scenario_id"]) for r in compare], rotation=10)
    axes[1].set_ylabel("Delta lag vs uncoupled")
    axes[1].set_title("Lag delta")
    axes[1].grid(axis="y", alpha=0.25)
    signal_to_noise["lag"] = [abs(d) / max(1e-9, e) for d, e in zip(lag_deltas, lag_errs)]

    # Foreground practical magnitude via signal-to-noise ratio |Δ|/SE.
    metric_order = ["order", "lock", "anti-phase", "lag"]
    for j, metric in enumerate(metric_order):
        vals = signal_to_noise[metric]
        if len(vals) < len(compare):
            continue
        offset = (j - 1.5) * 0.18
        axes[2].bar(
            x + offset,
            vals,
            width=0.16,
            label=metric,
            color=SYNC_COLORS[metric],
            alpha=0.9,
        )
    axes[2].axhline(1.0, color="black", linewidth=1.0, linestyle="--")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels([_short_label(r["scenario_id"]) for r in compare], rotation=10)
    axes[2].set_ylabel("|Δ| / SE")
    axes[2].set_title("Effect magnitude (signal-to-noise)")
    axes[2].legend(frameon=False, fontsize=8, ncol=2)
    axes[2].grid(axis="y", alpha=0.25)

    fig.suptitle("Demo Story Figure: Effect Sizes Relative to Uncoupled Baseline", y=1.03)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _write_executive_result_card(
    rows: List[Dict[str, str]],
    *,
    csv_path: Path,
    fig_path: Path,
) -> None:
    multi = [r for r in rows if "multipatch_" in r.get("scenario_id", "")]
    base = next((r for r in multi if "multipatch_uncoupled" in r.get("scenario_id", "")), None)
    if base is None:
        return

    compare = [r for r in multi if "multipatch_uncoupled" not in r.get("scenario_id", "")]
    if not compare:
        return

    fieldnames = [
        "scenario_id",
        "delta_order",
        "delta_lock",
        "delta_lag",
        "delta_antiphase",
        "snr_order",
        "snr_lock",
        "snr_lag",
        "snr_antiphase",
        "summary_call",
    ]
    out_rows: List[Dict[str, str]] = []
    for row in compare:
        d_order = _as_float(row, "sync_order_mean") - _as_float(base, "sync_order_mean")
        d_lock = _as_float(row, "sync_lock_mean") - _as_float(base, "sync_lock_mean")
        d_lag = _as_float(row, "sync_lag_mean") - _as_float(base, "sync_lag_mean")
        d_anti = _as_float(row, "sync_antiphase_mean") - _as_float(base, "sync_antiphase_mean")

        se_order = np.sqrt(_as_float(row, "sync_order_mean_seed_std") ** 2 + _as_float(base, "sync_order_mean_seed_std") ** 2)
        se_lock = np.sqrt(_as_float(row, "sync_lock_mean_seed_std") ** 2 + _as_float(base, "sync_lock_mean_seed_std") ** 2)
        se_lag = np.sqrt(_as_float(row, "sync_lag_mean_seed_std") ** 2 + _as_float(base, "sync_lag_mean_seed_std") ** 2)
        se_anti = np.sqrt(_as_float(row, "sync_antiphase_mean_seed_std") ** 2 + _as_float(base, "sync_antiphase_mean_seed_std") ** 2)

        snr_order = abs(d_order) / max(1e-9, se_order)
        snr_lock = abs(d_lock) / max(1e-9, se_lock)
        snr_lag = abs(d_lag) / max(1e-9, se_lag)
        snr_anti = abs(d_anti) / max(1e-9, se_anti)

        sid = row["scenario_id"]
        if "sync_positive" in sid:
            directional_support = (d_order > 0) and (d_lock > 0) and (d_lag < 0)
        elif "desync_negative" in sid:
            directional_support = (d_order < 0) and (d_lock < 0) and (d_lag > 0)
        else:
            directional_support = False

        strength = np.mean([snr_order, snr_lock, snr_lag, snr_anti])
        call = "directionally_supported" if directional_support else "mixed_or_weak"
        if strength < 1.0:
            call = f"{call}_low_signal"

        out_rows.append(
            {
                "scenario_id": sid,
                "delta_order": f"{d_order:.6f}",
                "delta_lock": f"{d_lock:.6f}",
                "delta_lag": f"{d_lag:.6f}",
                "delta_antiphase": f"{d_anti:.6f}",
                "snr_order": f"{snr_order:.3f}",
                "snr_lock": f"{snr_lock:.3f}",
                "snr_lag": f"{snr_lag:.3f}",
                "snr_antiphase": f"{snr_anti:.3f}",
                "summary_call": call,
            }
        )

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    fig, ax = plt.subplots(figsize=(11, 2.4 + 0.8 * len(out_rows)))
    ax.axis("off")
    title = (
        "Executive Result Card (vs uncoupled baseline)\n"
        "Read this first: deltas + signal-to-noise + directional support call"
    )
    ax.set_title(title, fontsize=11, pad=12)

    table_data = []
    for r in out_rows:
        table_data.append(
            [
                _short_label(r["scenario_id"]),
                r["delta_order"],
                r["delta_lock"],
                r["delta_lag"],
                r["delta_antiphase"],
                r["snr_order"],
                r["snr_lock"],
                r["snr_lag"],
                r["snr_antiphase"],
                r["summary_call"],
            ]
        )
    col_labels = [
        "scenario",
        "Δorder",
        "Δlock",
        "Δlag",
        "Δanti",
        "|Δ|/SE order",
        "|Δ|/SE lock",
        "|Δ|/SE lag",
        "|Δ|/SE anti",
        "call",
    ]
    tbl = ax.table(cellText=table_data, colLabels=col_labels, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1.0, 1.25)
    fig.tight_layout()
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_sync_overlay(
    scenario_runs: Dict[str, List[List[Dict[str, str]]]],
    *,
    output_path: Path,
    smoothing_window: int,
    tail_rows: int,
    burn_in: int,
    thresholds: Dict[str, float],
) -> None:
    multi_ids = [sid for sid in scenario_runs if "multipatch_" in sid]
    if not multi_ids:
        return

    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True)
    panels = [
        ("synchrony_order_parameter", "order", axes[0, 0]),
        ("synchrony_phase_lock_fraction", "lock", axes[0, 1]),
        ("synchrony_antiphase_fraction", "anti-phase", axes[1, 0]),
        ("synchrony_mean_abs_phase_lag", "lag", axes[1, 1]),
    ]

    t_any: np.ndarray = np.asarray([], dtype=float)
    for sid in sorted(multi_ids):
        runs = scenario_runs[sid]
        label = _short_label(sid)
        color = _scenario_color(sid)
        for key, title, ax in panels:
            t, m, s = _aggregate_metric(runs, key, tail_rows=tail_rows)
            if t.size == 0:
                continue
            t_any = t
            m_s = _rolling_mean(m, smoothing_window)
            lo_s = _rolling_mean(m - s, smoothing_window)
            hi_s = _rolling_mean(m + s, smoothing_window)
            ax.plot(t, m_s, linewidth=1.5, label=label, color=color)
            ax.fill_between(t, lo_s, hi_s, alpha=0.12, color=color)

    for key, title, ax in panels:
        ax.set_title(title)
        ax.grid(alpha=0.25)
        if key != "synchrony_mean_abs_phase_lag":
            ax.set_ylim(-0.02, 1.02)
    if thresholds:
        if "desync_order_lo" in thresholds:
            axes[0, 0].axhline(
                thresholds["desync_order_lo"],
                color=SYNC_COLORS["order"],
                linestyle="--",
                linewidth=1.0,
                alpha=0.7,
            )
        if "desync_lock_lo" in thresholds:
            axes[0, 1].axhline(
                thresholds["desync_lock_lo"],
                color=SYNC_COLORS["lock"],
                linestyle="--",
                linewidth=1.0,
                alpha=0.7,
            )
        if "desync_antiphase_lo" in thresholds:
            axes[1, 0].axhline(
                thresholds["desync_antiphase_lo"],
                color=SYNC_COLORS["anti-phase"],
                linestyle="--",
                linewidth=1.0,
                alpha=0.7,
            )
        if "desync_lag_lo" in thresholds:
            axes[1, 1].axhline(
                thresholds["desync_lag_lo"],
                color=SYNC_COLORS["lag"],
                linestyle="--",
                linewidth=1.0,
                alpha=0.7,
            )

    if t_any.size:
        span = _burnin_span(t_any, burn_in=burn_in)
        if span is not None:
            x0, x1 = span
            for _, _, ax in panels:
                ax.axvspan(x0, x1, color="gray", alpha=0.10, zorder=0)

    axes[1, 0].set_xlabel("t")
    axes[1, 1].set_xlabel("t")
    axes[0, 0].set_ylabel("value")
    axes[1, 0].set_ylabel("value")
    axes[0, 1].legend(frameon=False, fontsize=9)
    fig.suptitle("Demo Story Figure: Smoothed Synchrony Signals (Ribbon = ±1σ across seeds)", y=1.02)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _trim_tail(rows: List[Dict[str, str]], tail_rows: int) -> List[Dict[str, str]]:
    if tail_rows > 0 and len(rows) > tail_rows:
        return rows[-tail_rows:]
    return rows


def _plot_phase_offset_small_multiples(
    scenario_runs: Dict[str, List[List[Dict[str, str]]]],
    *,
    output_path: Path,
    tail_rows: int,
    max_lag: int = 32,
) -> None:
    multi_ids = [sid for sid in sorted(scenario_runs.keys()) if "multipatch_" in sid]
    if not multi_ids:
        return

    fig, axes = plt.subplots(len(multi_ids), 1, figsize=(10, 2.8 * len(multi_ids)), sharex=True)
    if len(multi_ids) == 1:
        axes = [axes]

    for ax, sid in zip(axes, multi_ids):
        per_patch_lags: Dict[int, List[float]] = {}
        for rows in scenario_runs[sid]:
            r = _trim_tail(rows, tail_rows)
            keys = _patch_keys(r)
            if len(keys) < 2:
                continue
            base = _series(r, keys[0])
            for idx, key in enumerate(keys[1:], start=1):
                other = _series(r, key)
                m = min(base.size, other.size)
                if m < 8:
                    continue
                x = base[-m:] - np.mean(base[-m:])
                y = other[-m:] - np.mean(other[-m:])
                corr = np.correlate(x, y, mode="full")
                lags = np.arange(-m + 1, m)
                mask = np.abs(lags) <= max_lag
                if not np.any(mask):
                    continue
                lag = float(lags[mask][int(np.argmax(corr[mask]))])
                per_patch_lags.setdefault(idx, []).append(lag)

        if not per_patch_lags:
            ax.text(0.5, 0.5, "No patch lag data", ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            continue

        patch_ids = sorted(per_patch_lags.keys())
        means = np.asarray([float(np.mean(per_patch_lags[i])) for i in patch_ids], dtype=float)
        stds = np.asarray([float(np.std(per_patch_lags[i])) for i in patch_ids], dtype=float)
        color = _scenario_color(sid)
        ax.errorbar(
            patch_ids,
            means,
            yerr=stds,
            fmt="o-",
            color=color,
            ecolor=color,
            capsize=3,
            linewidth=1.5,
            markersize=4,
        )
        ax.axhline(0.0, color="black", linewidth=1.0)
        ax.set_ylabel("lag vs patch_0")
        ax.set_title(f"{_short_label(sid)}: patch offsets (+ lag behind patch_0, - lead ahead)")
        ax.grid(axis="y", alpha=0.25)
        ax.set_xticks(patch_ids)
        ax.set_xticklabels([f"patch_{i}" for i in patch_ids])

    axes[-1].set_xlabel("patch compared to patch_0 baseline")
    fig.suptitle("Demo Diagnostic: Per-Patch Phase Offsets (reference = patch_0)", y=1.01)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_crosscorr_hist_by_scenario(
    scenario_runs: Dict[str, List[List[Dict[str, str]]]],
    *,
    output_path: Path,
    tail_rows: int,
    max_lag: int = 32,
) -> None:
    multi_ids = [sid for sid in sorted(scenario_runs.keys()) if "multipatch_" in sid]
    if not multi_ids:
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    corr_ax, lag_ax = axes
    rng = np.random.default_rng(7)

    corr_data: List[np.ndarray] = []
    lag_data: List[np.ndarray] = []
    labels: List[str] = []
    colors: List[str] = []

    for sid in sorted(multi_ids):
        lags_all: List[float] = []
        corr_all: List[float] = []
        for rows in scenario_runs[sid]:
            r = _trim_tail(rows, tail_rows)
            keys = _patch_keys(r)
            if len(keys) < 2:
                continue
            patch_series = [_series(r, key) for key in keys]
            lags, corr = _pairwise_best_lags(patch_series, max_lag=max_lag)
            lags_all.extend([abs(v) for v in lags])
            corr_all.extend(corr)
        if not corr_all and not lags_all:
            continue
        color = _scenario_color(sid)
        label = _short_label(sid)
        labels.append(label)
        colors.append(color)
        corr_data.append(np.asarray(corr_all, dtype=float))
        lag_data.append(np.asarray(lags_all, dtype=float))

    x = np.arange(len(labels))
    for i, vals in enumerate(corr_data):
        if vals.size == 0:
            continue
        jitter = rng.uniform(-0.08, 0.08, size=vals.size)
        corr_ax.scatter(
            np.full(vals.size, x[i]) + jitter,
            vals,
            s=16,
            alpha=0.55,
            color=colors[i],
            edgecolors="none",
        )
        corr_ax.errorbar(
            x[i],
            float(np.mean(vals)),
            yerr=float(np.std(vals)),
            fmt="o",
            color="black",
            capsize=3,
            markersize=4,
        )

    for i, vals in enumerate(lag_data):
        if vals.size == 0:
            continue
        jitter = rng.uniform(-0.08, 0.08, size=vals.size)
        lag_ax.scatter(
            np.full(vals.size, x[i]) + jitter,
            vals,
            s=16,
            alpha=0.55,
            color=colors[i],
            edgecolors="none",
        )
        lag_ax.errorbar(
            x[i],
            float(np.mean(vals)),
            yerr=float(np.std(vals)),
            fmt="o",
            color="black",
            capsize=3,
            markersize=4,
        )

    corr_ax.set_title("Pairwise zero-lag correlation (points + mean±sd)")
    corr_ax.set_xlabel("scenario")
    corr_ax.set_xticks(x)
    corr_ax.set_xticklabels(labels, rotation=12)
    corr_ax.set_ylabel("corr(x_i, x_j)")
    corr_ax.grid(alpha=0.25)
    lag_ax.set_title("Pairwise |best lag| (points + mean±sd)")
    lag_ax.set_xlabel("scenario")
    lag_ax.set_xticks(x)
    lag_ax.set_xticklabels(labels, rotation=12)
    lag_ax.set_ylabel("|best lag| (steps)")
    lag_ax.grid(alpha=0.25)
    fig.suptitle("Mechanistic Sanity: Pairwise Relations by Scenario (low-count robust view)", y=1.02)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_failure_mode_boundary(
    rows: List[Dict[str, str]],
    *,
    output_path: Path,
    thresholds: Dict[str, float],
) -> None:
    multi = [r for r in rows if "multipatch_" in r.get("scenario_id", "")]
    if len(multi) < 2:
        return

    lag_thr = float(thresholds.get("desync_lag_lo", np.nan))
    anti_thr = float(thresholds.get("desync_antiphase_lo", np.nan))
    if np.isnan(lag_thr):
        lag_thr = float(np.nanmedian([_as_float(r, "sync_lag_mean") for r in multi]))
    if np.isnan(anti_thr):
        anti_thr = float(np.nanmedian([_as_float(r, "sync_antiphase_mean") for r in multi]))

    names = [_short_label(r["scenario_id"]) for r in multi]
    lag = np.asarray([_as_float(r, "sync_lag_mean") for r in multi], dtype=float)
    lag_sd = np.asarray([_as_float(r, "sync_lag_mean_seed_std") for r in multi], dtype=float)
    anti = np.asarray([_as_float(r, "sync_antiphase_mean") for r in multi], dtype=float)
    anti_sd = np.asarray([_as_float(r, "sync_antiphase_mean_seed_std") for r in multi], dtype=float)

    # Closest to decision boundary in normalized distance (teaching classifier sensitivity).
    z_lag = np.abs(lag - lag_thr) / np.maximum(lag_sd, 1e-6)
    z_anti = np.abs(anti - anti_thr) / np.maximum(anti_sd, 1e-6)
    near_idx = int(np.argmin(z_lag + z_anti))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    ax_scatter, ax_margin = axes

    for i, row in enumerate(multi):
        sid = row["scenario_id"]
        color = _scenario_color(sid)
        ax_scatter.errorbar(
            lag[i],
            anti[i],
            xerr=lag_sd[i] if not np.isnan(lag_sd[i]) else 0.0,
            yerr=anti_sd[i] if not np.isnan(anti_sd[i]) else 0.0,
            fmt="o",
            markersize=6,
            color=color,
            ecolor=color,
            capsize=3,
            alpha=0.9,
            label=names[i],
        )

    ax_scatter.scatter(
        [lag[near_idx]],
        [anti[near_idx]],
        s=160,
        facecolors="none",
        edgecolors="black",
        linewidths=1.4,
        label="near-boundary exemplar",
    )
    ax_scatter.axvline(lag_thr, color=SYNC_COLORS["lag"], linestyle="--", linewidth=1.0)
    ax_scatter.axhline(anti_thr, color=SYNC_COLORS["anti-phase"], linestyle="--", linewidth=1.0)
    ax_scatter.set_xlabel("mean lag")
    ax_scatter.set_ylabel("mean anti-phase")
    ax_scatter.set_title("Near-boundary ambiguity in lag/anti-phase plane")
    ax_scatter.grid(alpha=0.25)
    ax_scatter.legend(frameon=False, fontsize=8, loc="lower right")

    x = np.arange(len(multi))
    ax_margin.bar(
        x - 0.18,
        anti - anti_thr,
        width=0.36,
        color=SYNC_COLORS["anti-phase"],
        alpha=0.8,
        label="anti - anti_thr",
    )
    ax_margin.bar(
        x + 0.18,
        lag - lag_thr,
        width=0.36,
        color=SYNC_COLORS["lag"],
        alpha=0.8,
        label="lag - lag_thr",
    )
    ax_margin.axhline(0.0, color="black", linewidth=1.0)
    ax_margin.set_xticks(x)
    ax_margin.set_xticklabels(names, rotation=12)
    ax_margin.set_ylabel("margin to threshold")
    ax_margin.set_title("Classifier sensitivity margins")
    ax_margin.grid(axis="y", alpha=0.25)
    ax_margin.legend(frameon=False, fontsize=9)

    fig.suptitle("Failure Mode Panel: Boundary Ambiguity Under Thresholded Classifiers", y=1.02)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _resolve_selected_scenarios(pack: str, selection: str) -> List[DemoScenario]:
    pack_scenarios = SCENARIO_PACKS[pack]
    if selection.strip().lower() == "all":
        return pack_scenarios
    selected_ids = {s.strip() for s in selection.split(",") if s.strip()}
    lookup = {s.scenario_id: s for s in pack_scenarios}
    unknown = sorted([sid for sid in selected_ids if sid not in lookup])
    if unknown:
        valid = ", ".join(sorted(lookup.keys()))
        raise ValueError(f"Unknown scenario id(s): {unknown}. Valid: {valid}")
    return [scenario for scenario in pack_scenarios if scenario.scenario_id in selected_ids]


def _parse_seed_list(raw: str) -> List[int]:
    raw = raw.strip()
    if not raw:
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run visual demo scenario packs and build gallery outputs."
    )
    parser.add_argument(
        "--pack",
        choices=sorted(SCENARIO_PACKS.keys()),
        default="demo",
        help="Scenario pack name",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=ROOT / "experiments" / "configs" / "demo",
        help="Directory containing demo YAML configs",
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=None,
        help="Root where run directories are created (defaults by pack)",
    )
    parser.add_argument(
        "--gallery-dir",
        type=Path,
        default=None,
        help="Directory for generated PNGs and gallery files (defaults by pack)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="Retry budget after initial run attempt",
    )
    parser.add_argument(
        "--tail-rows",
        type=int,
        default=3000,
        help="Number of tail rows to display in figures (0 = full series)",
    )
    parser.add_argument(
        "--scenarios",
        type=str,
        default="all",
        help="Comma-separated scenario ids to run, or 'all'",
    )
    parser.add_argument(
        "--smoothing-window",
        type=int,
        default=80,
        help="Rolling window size for visual smoothing",
    )
    parser.add_argument(
        "--seed-list",
        type=str,
        default="",
        help="Comma-separated seed list for replicate ribbons (overrides config seeds)",
    )
    args = parser.parse_args()

    if args.run_root is None:
        args.run_root = (
            ROOT / "experiments" / "runs" / ("demo_visual_v2" if args.pack == "demo_v2" else "demo_visual") / "runs"
        )
    if args.gallery_dir is None:
        args.gallery_dir = (
            ROOT / "experiments" / "runs" / ("demo_visual_v2" if args.pack == "demo_v2" else "demo_visual") / "gallery"
        )

    selected_seed_list = _parse_seed_list(args.seed_list)
    if not selected_seed_list and args.pack == "demo_v2":
        selected_seed_list = list(DEFAULT_V2_SEEDS)

    scenarios = _resolve_selected_scenarios(args.pack, args.scenarios)

    scenario_summaries: List[Dict[str, str]] = []
    replicate_rows: List[Dict[str, str]] = []
    scenario_runs: Dict[str, List[List[Dict[str, str]]]] = {}
    scenario_burn_in: Dict[str, int] = {}
    thresholds = _phase3_thresholds()

    temp_cfg_dir = args.run_root / "_tmp_configs"

    for scenario in scenarios:
        config_path = args.config_dir / scenario.config_file
        if not config_path.exists():
            raise FileNotFoundError(f"Missing config: {config_path}")
        coupling = _coupling_from_config(config_path)
        burn_in = _burn_in_from_config(config_path)
        scenario_burn_in[scenario.scenario_id] = burn_in

        run_seeds = list(selected_seed_list)
        if not run_seeds:
            run_seeds = [_config_seed(config_path)]

        runs_for_scenario: List[List[Dict[str, str]]] = []
        run_dirs: List[Path] = []
        rep_summaries: List[Dict[str, float]] = []

        for seed in run_seeds:
            effective_config_path = config_path
            if selected_seed_list:
                effective_config_path = _seed_override_config_path(
                    base_config_path=config_path,
                    scenario_id=scenario.scenario_id,
                    seed=seed,
                    temp_dir=temp_cfg_dir,
                )

            print(
                f"running pack={args.pack} scenario={scenario.scenario_id} "
                f"seed={seed} config={effective_config_path}"
            )
            run_dir = run_simulation(
                effective_config_path,
                run_root=args.run_root,
                max_retries=args.max_retries,
            )
            metrics_path = run_dir / "metrics.csv"
            rows = _read_csv(metrics_path)

            runs_for_scenario.append(rows)
            run_dirs.append(run_dir)
            rep_summaries.append(_replicate_summary(rows))
            replicate_rows.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "title": scenario.title,
                    "seed": str(seed),
                    "config_path": str(config_path),
                    "effective_config_path": str(effective_config_path),
                    "run_dir": str(run_dir),
                    "metrics_path": str(metrics_path),
                }
            )

        fig_path = args.gallery_dir / f"{scenario.scenario_id}.png"
        _plot_demo_ribbon(
            runs=runs_for_scenario,
            scenario=scenario,
            output_path=fig_path,
            tail_rows=args.tail_rows,
            smoothing_window=max(1, args.smoothing_window),
            coupling=coupling,
            seeds=run_seeds,
            burn_in=burn_in,
            thresholds=thresholds,
        )

        summary = _scenario_summary_row(
            scenario=scenario,
            config_path=config_path,
            figure_path=fig_path,
            run_dirs=run_dirs,
            replicate_seeds=run_seeds,
            replicate_summaries=rep_summaries,
            coupling=coupling,
        )
        scenario_summaries.append(summary)
        scenario_runs[scenario.scenario_id] = runs_for_scenario

    index_path = args.gallery_dir / "demo_gallery_index.csv"
    replicate_index_path = args.gallery_dir / "demo_gallery_replicates.csv"
    md_path = args.gallery_dir / "demo_gallery.md"
    _write_gallery_index(index_path, scenario_summaries)
    _write_replicate_index(replicate_index_path, replicate_rows)
    _plot_effect_deltas(
        scenario_summaries,
        args.gallery_dir / "demo_effect_deltas_vs_uncoupled.png",
    )
    _write_executive_result_card(
        scenario_summaries,
        csv_path=args.gallery_dir / "demo_executive_result_card.csv",
        fig_path=args.gallery_dir / "demo_executive_result_card.png",
    )
    _plot_sync_overlay(
        scenario_runs,
        output_path=args.gallery_dir / "demo_sync_overlay_smoothed.png",
        smoothing_window=max(1, args.smoothing_window),
        tail_rows=args.tail_rows,
        burn_in=max(scenario_burn_in.values()) if scenario_burn_in else 0,
        thresholds=thresholds,
    )
    _plot_crosscorr_hist_by_scenario(
        scenario_runs,
        output_path=args.gallery_dir / "demo_crosscorr_hist_by_scenario.png",
        tail_rows=args.tail_rows,
    )
    _plot_phase_offset_small_multiples(
        scenario_runs,
        output_path=args.gallery_dir / "demo_phase_offset_small_multiples.png",
        tail_rows=args.tail_rows,
    )
    _plot_failure_mode_boundary(
        scenario_summaries,
        output_path=args.gallery_dir / "demo_failure_mode_boundary.png",
        thresholds=thresholds,
    )
    _write_gallery_markdown(md_path, scenario_summaries, pack=args.pack)

    print(f"wrote {index_path}")
    print(f"wrote {replicate_index_path}")
    print(f"wrote {md_path}")


if __name__ == "__main__":
    main()
