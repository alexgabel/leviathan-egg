#!/usr/bin/env python3
"""Generate Stage-2 confirmation manifest/configs for Path A (tau=0.8).

This creates replicate-seed configs for selected boundary cells from the
recentered Stage-1 exploration grid.
"""

from __future__ import annotations

import csv
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[1]
PHASE2_DIR = ROOT / "experiments" / "configs" / "phase2"
CONFIRMATION_MANIFEST = PHASE2_DIR / "manifest_confirmation.csv"

# Boundary-focused cells selected from tau=0.8 sensitivity labeling on recenter_full.
# Six reversal-like cells + two hierarchical anchors.
BOUNDARY_CELLS: Dict[str, str] = {
    "phase2x_sp-anti_strong_v-low_l-low_f-off.yaml": "reversal_candidate",
    "phase2x_sp-anti_strong_v-low_l-low_f-on.yaml": "reversal_candidate",
    "phase2x_sp-anti_strong_v-low_l-high_f-off.yaml": "reversal_candidate",
    "phase2x_sp-anti_strong_v-low_l-high_f-on.yaml": "reversal_candidate",
    "phase2x_sp-anti_strong_v-high_l-low_f-off.yaml": "reversal_candidate",
    "phase2x_sp-anti_strong_v-high_l-low_f-on.yaml": "reversal_candidate",
    "phase2x_sp-anti_strong_v-high_l-high_f-off.yaml": "hierarchical_anchor",
    "phase2x_sp-anti_strong_v-high_l-high_f-on.yaml": "hierarchical_anchor",
}

REPLICATE_COUNT = 5
SEED_BASE = 4101


def _load_yaml(path: Path) -> Dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_yaml(path: Path, cfg: Dict[str, object]) -> None:
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def _build_rows() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    seed_offset = 0

    # Remove previously generated Path A confirmation configs.
    for old in PHASE2_DIR.glob("phase2c_tau08_*.yaml"):
        old.unlink()

    for base_name, hypothesis in BOUNDARY_CELLS.items():
        source_path = PHASE2_DIR / base_name
        if not source_path.exists():
            raise FileNotFoundError(f"Missing boundary source config: {source_path}")

        source_cfg = _load_yaml(source_path)
        cell_id = source_path.stem.replace("phase2x_", "")

        for rep_idx in range(1, REPLICATE_COUNT + 1):
            seed = SEED_BASE + seed_offset
            seed_offset += 1
            cfg = deepcopy(source_cfg)
            cfg_name = f"phase2c_tau08_{cell_id}_r{rep_idx}"
            cfg["experiment_name"] = cfg_name
            cfg["description"] = (
                "Phase 2 confirmation run (Path A tau=0.8): "
                f"source_cell={source_path.stem}, replicate={rep_idx}, seed={seed}."
            )
            cfg["date_created"] = str(date.today())
            cfg["runtime_and_reproducibility"]["random_seed"] = int(seed)

            out_path = PHASE2_DIR / f"{cfg_name}.yaml"
            _write_yaml(out_path, cfg)

            rows.append(
                {
                    "config_path": f"experiments/configs/phase2/{out_path.name}",
                    "sweep_axis": "confirmation_boundary_tau08",
                    "sweep_value": f"source_cell={source_path.stem};replicate={rep_idx}",
                    "hypothesis": hypothesis,
                    "seed": str(seed),
                    "stage": "confirmation",
                    "notes": (
                        "path_a_tau08;"
                        f"source_config={source_path.name};"
                        "threshold_profile=regime_thresholds_tau08_sensitivity.yaml"
                    ),
                }
            )

    return rows


def _write_manifest(rows: List[Dict[str, str]]) -> None:
    fieldnames = [
        "config_path",
        "sweep_axis",
        "sweep_value",
        "hypothesis",
        "seed",
        "stage",
        "notes",
    ]
    with CONFIRMATION_MANIFEST.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = _build_rows()
    _write_manifest(rows)
    print(f"Wrote {len(rows)} confirmation rows: {CONFIRMATION_MANIFEST}")
    print("Generated configs:", len(list(PHASE2_DIR.glob("phase2c_tau08_*.yaml"))))


if __name__ == "__main__":
    main()
