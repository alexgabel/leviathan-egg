from __future__ import annotations

import csv
import hashlib
import subprocess
import sys
from pathlib import Path

import yaml


def _write_analysis_csv(path: Path, *, antiphase: float, replicates: int = 5) -> None:
    fieldnames = [
        "sweep_value",
        "strength",
        "label",
        "sync_antiphase_mean",
        "sync_lag_mean",
        "sync_order_mean",
        "sync_lock_mean",
    ]
    rows = []
    for _ in range(replicates):
        rows.append(
            {
                "sweep_value": "mode=mean_field;lag_steps=8;strength=0.04",
                "strength": "0.04",
                "label": "desynchrony",
                "sync_antiphase_mean": f"{antiphase:.6f}",
                "sync_lag_mean": "28.2",
                "sync_order_mean": "0.91",
                "sync_lock_mean": "0.75",
            }
        )
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_profile(path: Path, *, antiphase_lo: float) -> None:
    payload = {
        "schema_version": "1.0",
        "profile": "phase3_desync_v2",
        "desync_antiphase_lo": antiphase_lo,
        "desync_logic": "(order<=lo && lock<=lo) && (lag>=lo || antiphase>=lo)",
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_verdict(args: list[str]) -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "phase3_desync_verdict.py"
    )
    subprocess.run([sys.executable, str(script), *args], check=True)


def test_profile_threshold_used_when_min_antiphase_omitted(tmp_path):
    analysis_csv = tmp_path / "analysis.csv"
    profile_yaml = tmp_path / "profile.yaml"
    cells_csv = tmp_path / "cells.csv"
    robust_csv = tmp_path / "robust.csv"
    meta_yaml = tmp_path / "meta.yaml"

    _write_analysis_csv(analysis_csv, antiphase=0.92, replicates=5)
    _write_profile(profile_yaml, antiphase_lo=0.93)

    _run_verdict(
        [
            "--analysis-csv",
            str(analysis_csv),
            "--threshold-profile",
            str(profile_yaml),
            "--min-target-fraction",
            "0.8",
            "--min-replicates",
            "5",
            "--cells-output",
            str(cells_csv),
            "--robust-output",
            str(robust_csv),
            "--meta-output",
            str(meta_yaml),
        ]
    )

    robust_rows = _read_csv_rows(robust_csv)
    assert len(robust_rows) == 0

    meta = yaml.safe_load(meta_yaml.read_text(encoding="utf-8"))
    assert meta["gates"]["min_antiphase_mean"] == 0.93
    assert meta["gates"]["min_antiphase_source"] == "threshold_profile.desync_antiphase_lo"
    assert meta["inputs"]["threshold_profile"] == str(profile_yaml)
    assert meta["threshold_profile_path"] == str(profile_yaml)
    assert meta["threshold_profile_sha256"] == _sha256_file(profile_yaml)
    assert meta["analysis_input_path"] == str(analysis_csv)
    assert meta["analysis_input_sha256"] == _sha256_file(analysis_csv)
    assert meta["resolved_gates"] == meta["gates"]


def test_cli_override_keeps_backwards_compatible_override_behavior(tmp_path):
    analysis_csv = tmp_path / "analysis.csv"
    profile_yaml = tmp_path / "profile.yaml"
    cells_csv = tmp_path / "cells.csv"
    robust_csv = tmp_path / "robust.csv"
    meta_yaml = tmp_path / "meta.yaml"

    _write_analysis_csv(analysis_csv, antiphase=0.92, replicates=5)
    _write_profile(profile_yaml, antiphase_lo=0.93)

    _run_verdict(
        [
            "--analysis-csv",
            str(analysis_csv),
            "--threshold-profile",
            str(profile_yaml),
            "--min-antiphase-mean",
            "0.90",
            "--min-target-fraction",
            "0.8",
            "--min-replicates",
            "5",
            "--cells-output",
            str(cells_csv),
            "--robust-output",
            str(robust_csv),
            "--meta-output",
            str(meta_yaml),
        ]
    )

    robust_rows = _read_csv_rows(robust_csv)
    assert len(robust_rows) == 1

    meta = yaml.safe_load(meta_yaml.read_text(encoding="utf-8"))
    assert meta["gates"]["min_antiphase_mean"] == 0.9
    assert meta["gates"]["min_antiphase_source"] == "cli_override"


def test_default_antiphase_gate_is_used_without_profile_or_override(tmp_path):
    analysis_csv = tmp_path / "analysis.csv"
    cells_csv = tmp_path / "cells.csv"
    robust_csv = tmp_path / "robust.csv"
    meta_yaml = tmp_path / "meta.yaml"

    _write_analysis_csv(analysis_csv, antiphase=0.60, replicates=5)

    _run_verdict(
        [
            "--analysis-csv",
            str(analysis_csv),
            "--min-target-fraction",
            "0.8",
            "--min-replicates",
            "5",
            "--cells-output",
            str(cells_csv),
            "--robust-output",
            str(robust_csv),
            "--meta-output",
            str(meta_yaml),
        ]
    )

    robust_rows = _read_csv_rows(robust_csv)
    assert len(robust_rows) == 1

    meta = yaml.safe_load(meta_yaml.read_text(encoding="utf-8"))
    assert meta["gates"]["min_antiphase_mean"] == 0.5
    assert meta["gates"]["min_antiphase_source"] == "default"


def test_metadata_hash_and_resolved_gates_are_reproducible_across_runs(tmp_path):
    analysis_csv = tmp_path / "analysis.csv"
    profile_yaml = tmp_path / "profile.yaml"
    cells_csv = tmp_path / "cells.csv"
    robust_csv = tmp_path / "robust.csv"
    meta_yaml_1 = tmp_path / "meta_1.yaml"
    meta_yaml_2 = tmp_path / "meta_2.yaml"

    _write_analysis_csv(analysis_csv, antiphase=0.94, replicates=5)
    _write_profile(profile_yaml, antiphase_lo=0.93)

    base_args = [
        "--analysis-csv",
        str(analysis_csv),
        "--threshold-profile",
        str(profile_yaml),
        "--min-target-fraction",
        "0.8",
        "--min-replicates",
        "5",
        "--cells-output",
        str(cells_csv),
        "--robust-output",
        str(robust_csv),
    ]
    _run_verdict([*base_args, "--meta-output", str(meta_yaml_1)])
    _run_verdict([*base_args, "--meta-output", str(meta_yaml_2)])

    meta1 = yaml.safe_load(meta_yaml_1.read_text(encoding="utf-8"))
    meta2 = yaml.safe_load(meta_yaml_2.read_text(encoding="utf-8"))

    assert meta1["threshold_profile_path"] == str(profile_yaml)
    assert meta1["analysis_input_path"] == str(analysis_csv)
    assert meta1["threshold_profile_sha256"] == _sha256_file(profile_yaml)
    assert meta1["analysis_input_sha256"] == _sha256_file(analysis_csv)
    assert meta1["resolved_gates"] == meta2["resolved_gates"]
    assert meta1["threshold_profile_sha256"] == meta2["threshold_profile_sha256"]
    assert meta1["analysis_input_sha256"] == meta2["analysis_input_sha256"]
    assert meta1["counts"] == meta2["counts"]
