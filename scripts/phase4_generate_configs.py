#!/usr/bin/env python3
"""Generate Phase 4 config YAMLs from a manifest."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict

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


def _merged_params(row: Dict[str, str]) -> Dict[str, str]:
    p: Dict[str, str] = {}
    p.update(_parse_kv(row.get("sweep_value")))
    p.update(_parse_kv(row.get("notes")))
    return p


def _as_int(value: str, *, where: str) -> int:
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(f"Expected int for {where}, got {value!r}") from e


def _apply_source_profile(cfg: Dict[str, object], source_profile: str) -> None:
    ap = cfg["authority_and_power"]
    se = cfg["seasonality"]

    if source_profile == "reversal":
        return

    if source_profile == "hierarchical_lock":
        ap["authority_threshold"] = 0.7
        ap["violence_factor"] = 0.45
        ap["information_spread_rate"] = 0.45
        ap["memory_decay"] = 0.06
        se["forcing_amplitudes"]["hierarchy_rent"] = 0.9
        se["forcing_amplitudes"]["crisis"] = 0.8
        return

    if source_profile == "low_hierarchy":
        ap["authority_threshold"] = 2.5
        ap["violence_factor"] = 0.05
        ap["information_spread_rate"] = 0.05
        ap["memory_decay"] = 0.16
        se["forcing_amplitudes"]["hierarchy_rent"] = 0.3
        se["forcing_amplitudes"]["crisis"] = 0.3
        se["forcing_amplitudes"]["coordination_cost"] = 0.9
        return

    raise ValueError(f"Unsupported source_profile: {source_profile!r}")


def _build_config(
    *,
    baseline: Dict[str, object],
    row: Dict[str, str],
    params: Dict[str, str],
) -> Dict[str, object]:
    cfg = yaml.safe_load(yaml.safe_dump(baseline, sort_keys=False))
    out_name = Path(row["config_path"]).stem
    cfg["experiment_name"] = out_name
    cfg["description"] = (
        "Phase 4 Stage-1 generated config: "
        + (row.get("sweep_value") or row.get("notes") or out_name)
    )
    cfg["runtime_and_reproducibility"]["random_seed"] = _as_int(str(row["seed"]), where="seed")

    cfg["world_structure"]["num_patches"] = 1
    cfg["world_structure"]["population_sizes"] = {
        "agents": int(cfg["world_structure"]["population_sizes"].get("agents", 300))
    }
    cfg["seasonality"]["phase_offsets"] = {"patch_0": 0.0}
    cfg["inter_patch_coupling"] = {
        "enabled": False,
        "mode": "none",
        "topology": "all_to_all",
        "strength": 0.0,
        "sign": 1,
        "lag_steps": 0,
        "normalize_by_degree": True,
        "target_metric": "frac_hier",
    }

    source_profile = params.get("source_profile", "reversal")
    graph_mode = params.get("graph_mode", "undirected_contact")
    window_periods = _as_int(params.get("window_periods", "1"), where="window_periods")
    _apply_source_profile(cfg, source_profile)

    cfg["source_profile"] = source_profile
    cfg["graph_extraction"] = {
        "enabled": True,
        "graph_mode": graph_mode,
        "window_periods": window_periods,
        "emit_edge_list": True,
        "emit_window_metrics": True,
        "pool_patches": False,
    }
    cfg["structural_metrics"] = {
        "metrics_to_compute": [
            "density",
            "clustering_mean",
            "tree_excess_ratio",
            "branching_skew",
            "delta_hyperbolicity_proxy",
        ],
        "hyperbolicity_proxy_mode": "tree_likeness",
    }

    return cfg


def _write_config(path: Path, cfg: Dict[str, object], *, overwrite: bool) -> str:
    if path.exists() and not overwrite:
        return "exists"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return "written"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Phase 4 configs from manifest")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "experiments" / "configs" / "phase4" / "manifest_stage1_exploration.csv",
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
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    rows = _read_manifest_rows(args.manifest, stage=args.stage or None)
    baseline = yaml.safe_load(args.baseline.read_text(encoding="utf-8"))

    written = 0
    exists = 0
    for row in rows:
        out_path = ROOT / Path(row["config_path"])
        cfg = _build_config(
            baseline=baseline,
            row=row,
            params=_merged_params(row),
        )
        status = _write_config(out_path, cfg, overwrite=args.overwrite)
        if status == "written":
            written += 1
        else:
            exists += 1

    print(f"rows={len(rows)} written={written} exists={exists}")
    print(f"manifest: {args.manifest}")


if __name__ == "__main__":
    main()
