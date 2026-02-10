#!/usr/bin/env python3
"""Generate Phase 3 config YAMLs from a manifest."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _read_manifest_rows(path: Path, *, stage: str | None) -> list[Dict[str, str]]:
    with path.open("r", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("config_path")]
    if stage:
        rows = [r for r in rows if r.get("stage") == stage]
    return rows


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


def _as_float(value: str, *, where: str) -> float:
    try:
        return float(value)
    except ValueError as e:
        raise ValueError(f"Expected float for {where}, got {value!r}") from e


def _as_int(value: str, *, where: str) -> int:
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(f"Expected int for {where}, got {value!r}") from e


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_sign(value: str) -> int:
    v = value.strip().lower()
    if v in {"+1", "1", "plus", "pos", "positive"}:
        return 1
    if v in {"-1", "minus", "neg", "negative"}:
        return -1
    raise ValueError(f"Invalid sign value: {value!r}")


def _phase_offsets(profile: str, *, num_patches: int) -> Dict[str, float]:
    profile = profile.strip().lower()
    if profile == "staggered":
        return {
            f"patch_{i}": round(i / float(num_patches), 4) for i in range(num_patches)
        }
    if profile == "clustered":
        # Two clusters with slight within-cluster jitter.
        half = max(1, num_patches // 2)
        offsets: Dict[str, float] = {}
        for i in range(num_patches):
            if i < half:
                offsets[f"patch_{i}"] = round(0.0 + 0.08 * i, 4)
            else:
                offsets[f"patch_{i}"] = round(0.5 + 0.08 * (i - half), 4)
        return offsets

    raise ValueError(f"Unsupported phase profile: {profile!r}")


def _merged_params(row: Dict[str, str]) -> Dict[str, str]:
    p = {}
    # notes takes precedence over sweep_value
    p.update(_parse_kv(row.get("sweep_value")))
    p.update(_parse_kv(row.get("notes")))
    return p


def _infer_num_patches(params: Dict[str, str], default: int = 4) -> int:
    if "num_patches" in params:
        return _as_int(params["num_patches"], where="num_patches")
    return default


def _build_config(
    *,
    baseline: Dict[str, object],
    row: Dict[str, str],
    params: Dict[str, str],
    agents_per_patch: int,
) -> Dict[str, object]:
    cfg = yaml.safe_load(yaml.safe_dump(baseline, sort_keys=False))

    out_name = Path(row["config_path"]).stem
    cfg["experiment_name"] = out_name
    cfg["description"] = (
        "Phase 3 Stage-1/2 generated config: "
        + (row.get("sweep_value") or row.get("notes") or out_name)
    )

    seed = _as_int(str(row["seed"]), where="seed")
    cfg["runtime_and_reproducibility"]["random_seed"] = seed

    num_patches = _infer_num_patches(params)
    cfg["world_structure"]["num_patches"] = num_patches
    cfg["world_structure"]["population_sizes"] = {
        f"patch_{i}": agents_per_patch for i in range(num_patches)
    }

    phase_profile = params.get("phase_profile", "staggered")
    cfg["seasonality"]["phase_offsets"] = _phase_offsets(
        phase_profile, num_patches=num_patches
    )

    mode = params.get("mode", "mean_field")
    topology = params.get("topology", "all_to_all")
    strength = _as_float(params.get("strength", "0.0"), where="strength")
    sign = _parse_sign(params.get("sign", "+1"))
    lag_steps = _as_int(params.get("lag_steps", "0"), where="lag_steps")
    normalize_by_degree = _as_bool(params.get("normalize_by_degree", "true"))
    target_metric = params.get("target_metric", "frac_hier")

    enabled = bool(strength > 0.0)
    if not enabled:
        mode = "none"
        sign = 0

    cfg["inter_patch_coupling"] = {
        "enabled": enabled,
        "mode": mode,
        "topology": topology,
        "strength": float(strength),
        "sign": int(sign),
        "lag_steps": int(lag_steps),
        "normalize_by_degree": bool(normalize_by_degree),
        "target_metric": target_metric,
    }

    return cfg


def _write_config(path: Path, cfg: Dict[str, object], *, overwrite: bool) -> str:
    if path.exists() and not overwrite:
        return "exists"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return "written"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 3 configs from manifest")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase3" / "manifest_stage1_exploration.csv",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase1_reversal.yaml",
    )
    parser.add_argument(
        "--stage",
        type=str,
        default="exploration",
        help="Optional stage filter; pass empty string for all rows",
    )
    parser.add_argument(
        "--agents-per-patch",
        type=int,
        default=0,
        help="If <=0, defaults to baseline world_structure.population_sizes.agents",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing YAML files",
    )
    args = parser.parse_args()

    rows = _read_manifest_rows(args.manifest, stage=args.stage or None)
    baseline = yaml.safe_load(args.baseline.read_text(encoding="utf-8"))
    baseline_agents = int(
        baseline["world_structure"]["population_sizes"].get("agents", 300)
    )
    agents_per_patch = (
        int(args.agents_per_patch)
        if int(args.agents_per_patch) > 0
        else baseline_agents
    )

    written = 0
    exists = 0
    for row in rows:
        rel_path = Path(row["config_path"])
        out_path = ROOT / rel_path
        params = _merged_params(row)
        cfg = _build_config(
            baseline=baseline,
            row=row,
            params=params,
            agents_per_patch=agents_per_patch,
        )
        status = _write_config(out_path, cfg, overwrite=args.overwrite)
        if status == "written":
            written += 1
        else:
            exists += 1

    print(f"rows={len(rows)} written={written} exists={exists}")
    print(f"manifest: {args.manifest}")
    print(f"agents_per_patch: {agents_per_patch}")


if __name__ == "__main__":
    main()
