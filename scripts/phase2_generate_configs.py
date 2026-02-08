#!/usr/bin/env python3
"""Generate recentered Phase 2 exploration configs and manifests.

This generator writes a 24-cell factorial using:
- seasonal profile (includes amplitude shape and authority_coupling sign)
- violence profile
- information/memory lock-in profile
- festival mode
"""

from __future__ import annotations

import csv
from copy import deepcopy
from datetime import date
from itertools import product
from pathlib import Path
from typing import Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[1]
PHASE1_BASE = ROOT / "experiments" / "configs" / "phase1_reversal.yaml"
PHASE2_DIR = ROOT / "experiments" / "configs" / "phase2"
EXPLORATION_MANIFEST = PHASE2_DIR / "manifest_exploration.csv"
CONFIRMATION_MANIFEST = PHASE2_DIR / "manifest_confirmation.csv"

SEASONAL_PROFILE = {
    # Pushes against hierarchy: inverted coupling + low crisis/coordination forcing.
    "anti_strong": {
        "authority_coupling": -1,
        "aggregation_benefit_mult": 1.8,
        "coordination_cost_mult": 0.25,
        "hierarchy_rent_mult": 1.8,
        "crisis_mult": 0.25,
    },
    # Baseline around the original Phase 1 operating point.
    "baseline": {
        "authority_coupling": +1,
        "aggregation_benefit_mult": 1.0,
        "coordination_cost_mult": 1.0,
        "hierarchy_rent_mult": 1.0,
        "crisis_mult": 1.0,
    },
    # Pushes toward hierarchy: aligned coupling + strong crisis/coordination forcing.
    "pro_strong": {
        "authority_coupling": +1,
        "aggregation_benefit_mult": 1.2,
        "coordination_cost_mult": 1.8,
        "hierarchy_rent_mult": 1.8,
        "crisis_mult": 1.8,
    },
}

VIOLENCE_FACTOR = {
    "low": 0.05,
    "high": 0.60,
}

LOCKIN_PROFILE = {
    "low": {
        "information_spread_rate": 0.05,
        "memory_decay": 0.30,
    },
    "high": {
        "information_spread_rate": 0.60,
        "memory_decay": 0.03,
    },
}

FESTIVAL_MULTIPLIER = {
    "off": 0.0,
    "on": 1.2,
}


def _expected_hypothesis(
    *,
    seasonal_profile: str,
    violence_profile: str,
    lockin_profile: str,
    festival_mode: str,
) -> str:
    if (
        seasonal_profile == "anti_strong"
        and violence_profile == "low"
        and lockin_profile == "low"
        and festival_mode == "off"
    ):
        return "stable_egalitarian_candidate"

    if seasonal_profile == "anti_strong" and violence_profile == "low" and lockin_profile == "low":
        return "reversal_or_egal_candidate"

    if seasonal_profile == "pro_strong" and violence_profile == "high" and lockin_profile == "high":
        return "stable_hierarchical"

    if seasonal_profile == "pro_strong" and (violence_profile == "high" or lockin_profile == "high"):
        return "hierarchical_bias"

    return "mixed_or_borderline"


def _load_base_config() -> Dict[str, object]:
    return yaml.safe_load(PHASE1_BASE.read_text(encoding="utf-8"))


def _config_name(seasonal_profile: str, violence_profile: str, lockin_profile: str, festival_mode: str) -> str:
    return f"phase2x_sp-{seasonal_profile}_v-{violence_profile}_l-{lockin_profile}_f-{festival_mode}"


def _render_configs() -> List[Dict[str, str]]:
    base = _load_base_config()
    manifest_rows: List[Dict[str, str]] = []

    PHASE2_DIR.mkdir(parents=True, exist_ok=True)

    # Replace both the recentered generated set and older legacy generated set.
    for old in PHASE2_DIR.glob("phase2x_sp-*_v-*_l-*_f-*.yaml"):
        old.unlink()
    for old in PHASE2_DIR.glob("phase2_s-*_v-*_l-*_f-*.yaml"):
        old.unlink()

    seed_base = 3001
    i = 0

    for seasonal_profile, violence_profile, lockin_profile, festival_mode in product(
        ("anti_strong", "baseline", "pro_strong"),
        ("low", "high"),
        ("low", "high"),
        ("off", "on"),
    ):
        seed = seed_base + i
        i += 1

        cfg = deepcopy(base)
        name = _config_name(seasonal_profile, violence_profile, lockin_profile, festival_mode)

        cfg["experiment_name"] = name
        cfg["description"] = (
            "Phase 2 exploration recentered factorial cell: "
            f"seasonal_profile={seasonal_profile}, violence={violence_profile}, "
            f"lockin={lockin_profile}, festival={festival_mode}."
        )
        cfg["date_created"] = str(date.today())
        cfg["schema_version"] = "1.0"

        base_amps = base["seasonality"]["forcing_amplitudes"]
        profile = SEASONAL_PROFILE[seasonal_profile]
        amps = cfg["seasonality"]["forcing_amplitudes"]
        amps["aggregation_benefit"] = round(
            float(base_amps["aggregation_benefit"]) * profile["aggregation_benefit_mult"], 6
        )
        amps["coordination_cost"] = round(
            float(base_amps["coordination_cost"]) * profile["coordination_cost_mult"], 6
        )
        amps["hierarchy_rent"] = round(
            float(base_amps["hierarchy_rent"]) * profile["hierarchy_rent_mult"], 6
        )
        amps["crisis"] = round(float(base_amps["crisis"]) * profile["crisis_mult"], 6)
        amps["festival"] = round(
            float(base_amps["festival"]) * FESTIVAL_MULTIPLIER[festival_mode], 6
        )

        cfg["seasonality"]["forcing_sign"]["authority_coupling"] = int(profile["authority_coupling"])

        ap = cfg["authority_and_power"]
        ap["violence_factor"] = VIOLENCE_FACTOR[violence_profile]
        ap["information_spread_rate"] = LOCKIN_PROFILE[lockin_profile]["information_spread_rate"]
        ap["memory_decay"] = LOCKIN_PROFILE[lockin_profile]["memory_decay"]

        cfg["runtime_and_reproducibility"]["random_seed"] = int(seed)

        config_path = PHASE2_DIR / f"{name}.yaml"
        config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

        hypothesis = _expected_hypothesis(
            seasonal_profile=seasonal_profile,
            violence_profile=violence_profile,
            lockin_profile=lockin_profile,
            festival_mode=festival_mode,
        )

        sweep_value = (
            f"seasonal_profile={seasonal_profile};"
            f"violence={violence_profile};"
            f"lockin={lockin_profile};"
            f"festival={festival_mode}"
        )

        manifest_rows.append(
            {
                "config_path": f"experiments/configs/phase2/{config_path.name}",
                "sweep_axis": "factorial_24_recentered",
                "sweep_value": sweep_value,
                "hypothesis": hypothesis,
                "seed": str(seed),
                "stage": "exploration",
                "notes": (
                    f"authority_coupling={profile['authority_coupling']};"
                    f"agg_mult={profile['aggregation_benefit_mult']};"
                    f"coord_mult={profile['coordination_cost_mult']};"
                    f"rent_mult={profile['hierarchy_rent_mult']};"
                    f"crisis_mult={profile['crisis_mult']};"
                    f"violence_factor={VIOLENCE_FACTOR[violence_profile]};"
                    f"info_rate={LOCKIN_PROFILE[lockin_profile]['information_spread_rate']};"
                    f"memory_decay={LOCKIN_PROFILE[lockin_profile]['memory_decay']};"
                    f"festival_multiplier={FESTIVAL_MULTIPLIER[festival_mode]}"
                ),
            }
        )

    return manifest_rows


def _write_exploration_manifest(rows: List[Dict[str, str]]) -> None:
    fieldnames = [
        "config_path",
        "sweep_axis",
        "sweep_value",
        "hypothesis",
        "seed",
        "stage",
        "notes",
    ]
    with EXPLORATION_MANIFEST.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_confirmation_header_only() -> None:
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


def main() -> None:
    rows = _render_configs()
    _write_exploration_manifest(rows)
    _write_confirmation_header_only()
    print(f"Wrote {len(rows)} exploration configs and manifest: {EXPLORATION_MANIFEST}")
    print(f"Reset confirmation manifest to header only: {CONFIRMATION_MANIFEST}")


if __name__ == "__main__":
    main()
