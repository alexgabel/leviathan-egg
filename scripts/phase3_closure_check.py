#!/usr/bin/env python3
"""Machine-verifiable closure checks for Phase 3 artifacts and governance text."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_yaml(path: Path) -> Dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping at {path}, got {type(data).__name__}")
    return data


def _check_outputs(run_root: Path, closeout_script: Path) -> List[str]:
    errors: List[str] = []
    if not closeout_script.exists():
        errors.append(f"missing one-command script: {closeout_script}")

    required = [
        "desync_cells_v1.csv",
        "desync_cells_v2.csv",
        "desync_robust_cells_v1.csv",
        "desync_robust_cells_v2.csv",
        "verdict_meta_v1.yaml",
        "verdict_meta_v2.yaml",
        "sensitivity_antiphase_threshold.csv",
        "fig_phase3_v2_antiphase_sensitivity.png",
        "fig_phase3_desync_probability_v1_v2.png",
        "fig_phase3_lag_antiphase_plane_v1_v2.png",
        "fig_phase3_trace_desync_core_v2.png",
        "fig_phase3_trace_boundary_near_v2.png",
        "fig_phase3_label_distributions_v1_v2.png",
        "representative_selection_v2.csv",
    ]
    for name in required:
        path = run_root / name
        if not path.exists():
            errors.append(f"missing closeout output: {path}")
            continue
        if path.is_file() and path.stat().st_size <= 0:
            errors.append(f"empty closeout output: {path}")
    return errors


def _check_meta(meta_path: Path, profile_path: Path) -> List[str]:
    errors: List[str] = []
    if not meta_path.exists():
        return [f"missing metadata file: {meta_path}"]

    data = _read_yaml(meta_path)
    required_keys = [
        "threshold_profile_path",
        "threshold_profile_sha256",
        "resolved_gates",
        "analysis_input_path",
        "gates",
    ]
    for key in required_keys:
        if key not in data:
            errors.append(f"{meta_path}: missing key '{key}'")

    if errors:
        return errors

    profile_hash_expected = _sha256_file(profile_path)
    profile_hash_observed = str(data.get("threshold_profile_sha256", ""))
    if not profile_hash_observed:
        errors.append(f"{meta_path}: threshold_profile_sha256 is empty")
    elif profile_hash_observed != profile_hash_expected:
        errors.append(
            f"{meta_path}: threshold_profile_sha256 mismatch "
            f"(expected {profile_hash_expected}, got {profile_hash_observed})"
        )

    observed_profile_path = Path(str(data.get("threshold_profile_path", "")))
    if not observed_profile_path:
        errors.append(f"{meta_path}: threshold_profile_path is empty")
    else:
        if observed_profile_path.resolve() != profile_path.resolve():
            errors.append(
                f"{meta_path}: threshold_profile_path mismatch "
                f"(expected {profile_path.resolve()}, got {observed_profile_path.resolve()})"
            )

    analysis_input_path = Path(str(data.get("analysis_input_path", "")))
    if not analysis_input_path.exists():
        errors.append(f"{meta_path}: analysis_input_path missing on disk: {analysis_input_path}")

    resolved_gates = data.get("resolved_gates")
    if not isinstance(resolved_gates, dict):
        errors.append(f"{meta_path}: resolved_gates is not a mapping")
    else:
        for gate_key in (
            "target_label",
            "min_target_fraction",
            "min_replicates",
            "min_antiphase_mean",
            "min_antiphase_source",
        ):
            if gate_key not in resolved_gates:
                errors.append(f"{meta_path}: resolved_gates missing '{gate_key}'")
    return errors


def _check_notes(
    results_note: Path,
    captions_note: Path,
    *,
    window_start: str,
    window_end: str,
) -> List[str]:
    errors: List[str] = []
    if not results_note.exists():
        errors.append(f"missing results note: {results_note}")
        return errors
    if not captions_note.exists():
        errors.append(f"missing captions note: {captions_note}")
        return errors

    results_text = _read_text(results_note)
    captions_text = _read_text(captions_note)
    combined = results_text + "\n" + captions_text

    for required in ("strict lag-gated", "desync_v2_thresholds.yaml", "stability window"):
        if required not in combined:
            errors.append(f"notes missing required string: '{required}'")

    if "sensitivity_antiphase_threshold.csv" not in results_text:
        errors.append("results note missing sensitivity table reference")
    if "fig_phase3_v2_antiphase_sensitivity.png" not in results_text:
        errors.append("results note missing sensitivity figure reference")
    if "sensitivity_antiphase_threshold.csv" not in captions_text:
        errors.append("captions note missing sensitivity table reference")
    if "fig_phase3_v2_antiphase_sensitivity.png" not in captions_text:
        errors.append("captions note missing sensitivity figure reference")

    if window_start not in combined or window_end not in combined:
        errors.append(
            f"notes missing expected stability window bounds ({window_start}, {window_end})"
        )

    if "classifier v2" not in combined:
        errors.append("notes missing explicit classifier v2 wording")
    if "only under the frozen profile" not in combined:
        errors.append("notes missing profile-scoped conditional wording")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Phase-3 closure gates")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=ROOT / "experiments" / "runs" / "phase3" / "desync_refine_lag8_fine",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase3" / "desync_v2_thresholds.yaml",
    )
    parser.add_argument(
        "--results-note",
        type=Path,
        default=ROOT / "paper" / "notes" / "phase3_results_draft.md",
    )
    parser.add_argument(
        "--captions-note",
        type=Path,
        default=ROOT / "paper" / "notes" / "phase3_figure_captions.md",
    )
    parser.add_argument(
        "--closeout-script",
        type=Path,
        default=ROOT / "scripts" / "phase3_closeout.py",
    )
    parser.add_argument("--window-start", type=str, default="0.920")
    parser.add_argument("--window-end", type=str, default="0.939")
    args = parser.parse_args()

    failures: List[str] = []
    failures.extend(_check_outputs(args.run_root, args.closeout_script))
    failures.extend(_check_meta(args.run_root / "verdict_meta_v1.yaml", args.profile))
    failures.extend(_check_meta(args.run_root / "verdict_meta_v2.yaml", args.profile))
    failures.extend(
        _check_notes(
            args.results_note,
            args.captions_note,
            window_start=args.window_start,
            window_end=args.window_end,
        )
    )

    if failures:
        print("FAIL: phase3 closure checks failed")
        for item in failures:
            print(f"- {item}")
        sys.exit(1)

    print("PASS: phase3 closure checks passed")
    print(f"run_root={args.run_root}")
    print(f"profile={args.profile}")


if __name__ == "__main__":
    main()
