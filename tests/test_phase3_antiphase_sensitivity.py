from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import yaml


def _write_analysis(path: Path) -> None:
    fieldnames = [
        "sweep_value",
        "strength",
        "sync_order_mean",
        "sync_lock_mean",
        "sync_lag_mean",
        "sync_antiphase_mean",
    ]
    rows = []
    # Cell A (strength 0.01): anti-phase centered at 0.935
    for _ in range(5):
        rows.append(
            {
                "sweep_value": "mode=mean_field;lag_steps=8;strength=0.01",
                "strength": "0.01",
                "sync_order_mean": "0.90",
                "sync_lock_mean": "0.74",
                "sync_lag_mean": "27.0",
                "sync_antiphase_mean": "0.935",
            }
        )
    # Cell B (strength 0.02): anti-phase centered at 0.925
    for _ in range(5):
        rows.append(
            {
                "sweep_value": "mode=mean_field;lag_steps=8;strength=0.02",
                "strength": "0.02",
                "sync_order_mean": "0.90",
                "sync_lock_mean": "0.74",
                "sync_lag_mean": "27.0",
                "sync_antiphase_mean": "0.925",
            }
        )
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_profile(path: Path) -> None:
    payload = {
        "schema_version": "1.0",
        "profile": "phase3_desync_v2",
        "sync_order_hi": 0.95,
        "sync_lock_hi": 0.9,
        "sync_lag_hi": 20.0,
        "desync_order_lo": 0.92,
        "desync_lock_lo": 0.76,
        "desync_lag_lo": 28.2,
        "desync_antiphase_lo": 0.93,
        "desync_logic": "(order<=lo && lock<=lo) && (lag>=lo || antiphase>=lo)",
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_antiphase_sensitivity_writes_window_and_figure(tmp_path):
    analysis_csv = tmp_path / "analysis_latest_per_config.csv"
    profile_yaml = tmp_path / "desync_v2_thresholds.yaml"
    out_csv = tmp_path / "sensitivity_antiphase_threshold.csv"
    out_png = tmp_path / "fig_phase3_v2_antiphase_sensitivity.png"
    _write_analysis(analysis_csv)
    _write_profile(profile_yaml)

    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "phase3_antiphase_sensitivity.py"
    )
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--analysis-csv",
            str(analysis_csv),
            "--threshold-profile",
            str(profile_yaml),
            "--antiphase-min",
            "0.924",
            "--antiphase-max",
            "0.936",
            "--antiphase-step",
            "0.001",
            "--min-target-fraction",
            "0.8",
            "--min-replicates",
            "5",
            "--min-robust-cells",
            "1",
            "--output-csv",
            str(out_csv),
            "--fig-output",
            str(out_png),
        ],
        check=True,
    )

    rows = _read_rows(out_csv)
    assert len(rows) == 13

    row_935 = next(r for r in rows if r["antiphase_threshold"] == "0.935000")
    row_936 = next(r for r in rows if r["antiphase_threshold"] == "0.936000")
    assert row_935["claim_holds"] == "1"
    assert row_935["stability_window_start"] == "0.924000"
    assert row_935["stability_window_end"] == "0.935000"
    assert row_936["claim_holds"] == "0"
    assert row_936["stability_window_start"] == ""

    assert out_png.exists()
    assert out_png.stat().st_size > 0

