

"""
Configuration loading and validation for Leviathan Egg.

Phase 1.B:
- Load YAML from path
- Validate required top-level sections
- Fill defaults and keep a resolved config dict for logging
- Convert to typed dataclasses
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml


class ConfigError(ValueError):
    """Raised when a configuration file is invalid."""


REQUIRED_TOP_LEVEL_SECTIONS = (
    "world_structure",
    "seasonality",
    "authority_and_power",
    "runtime_and_reproducibility",
    "observation",
)


def _expect_mapping(obj: Any, *, where: str) -> Mapping[str, Any]:
    if not isinstance(obj, Mapping):
        raise ConfigError(f"Expected mapping at {where}, got {type(obj).__name__}")
    return obj


def _require_keys(d: Mapping[str, Any], keys: tuple[str, ...], *, where: str) -> None:
    missing = [k for k in keys if k not in d]
    if missing:
        raise ConfigError(f"Missing required key(s) at {where}: {', '.join(missing)}")


def _deep_copy(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _deep_copy(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_copy(v) for v in obj]
    return obj


def _set_default(d: Dict[str, Any], key: str, value: Any) -> None:
    if key not in d:
        d[key] = value


# ---------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class ExperimentMeta:
    experiment_name: str
    description: str
    author: str
    date_created: str


@dataclass(frozen=True)
class WorldStructure:
    num_patches: int
    population_sizes: Dict[str, int]
    environmental_parameters: Dict[str, Any]


@dataclass(frozen=True)
class Seasonality:
    seasonal_period: int
    phase_offsets: Dict[str, float]
    forcing_amplitudes: Dict[str, float]
    forcing_sign: Dict[str, Any]


@dataclass(frozen=True)
class AuthorityAndPower:
    violence_factor: float
    information_spread_rate: float
    charisma_levels: Dict[str, float]

    authority_threshold: float
    authority_steepness: float

    benefit_scale: float
    cost_scale: float
    cost_exponent: float

    rent_scale: float
    domination_tax: float

    lock_in_effects: bool
    exit_friction_base: float
    exit_friction_from_violence: float
    exit_friction_from_information: float

    memory_decay: float
    prestige_noise: float


@dataclass(frozen=True)
class RuntimeAndReproducibility:
    total_steps: int
    burn_in_period: int
    random_seed: int
    logging_frequency: int


@dataclass(frozen=True)
class Observation:
    metrics_to_log: list[str]
    aggregation_windows: list[int]


@dataclass(frozen=True)
class Config:
    meta: ExperimentMeta
    world_structure: WorldStructure
    seasonality: Seasonality
    authority_and_power: AuthorityAndPower
    runtime_and_reproducibility: RuntimeAndReproducibility
    observation: Observation
    resolved: Dict[str, Any]

    def to_resolved_dict(self) -> Dict[str, Any]:
        return _deep_copy(self.resolved)


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def load_config(path: str | Path) -> Config:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config file does not exist: {p}")

    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise ConfigError(f"Failed to parse YAML at {p}: {e}") from e

    d = _expect_mapping(raw, where="root")
    _require_keys(d, REQUIRED_TOP_LEVEL_SECTIONS, where="root")

    # -----------------------------------------------------------------
    # Build resolved config (deep copy + defaults)
    # -----------------------------------------------------------------
    resolved: Dict[str, Any] = _deep_copy(dict(d))

    _set_default(resolved, "experiment_name", p.stem)
    _set_default(resolved, "description", "")
    _set_default(resolved, "author", "")
    _set_default(resolved, "date_created", "")

    for section in REQUIRED_TOP_LEVEL_SECTIONS:
        resolved[section] = dict(_expect_mapping(resolved[section], where=f"root.{section}"))

    # World structure
    ws = resolved["world_structure"]
    _require_keys(ws, ("num_patches", "population_sizes"), where="root.world_structure")
    _set_default(ws, "environmental_parameters", {})

    # Seasonality
    se = resolved["seasonality"]
    _require_keys(
        se,
        ("seasonal_period", "phase_offsets", "forcing_amplitudes", "forcing_sign"),
        where="root.seasonality",
    )

    # Authority & power
    ap = resolved["authority_and_power"]
    _require_keys(
        ap,
        ("violence_factor", "information_spread_rate", "charisma_levels"),
        where="root.authority_and_power",
    )

    _set_default(ap, "authority_threshold", 1.0)
    _set_default(ap, "authority_steepness", 3.0)
    _set_default(ap, "benefit_scale", 2.0)
    _set_default(ap, "cost_scale", 0.8)
    _set_default(ap, "cost_exponent", 1.6)
    _set_default(ap, "rent_scale", 0.4)
    _set_default(ap, "domination_tax", 0.6)
    _set_default(ap, "lock_in_effects", True)
    _set_default(ap, "exit_friction_base", 0.0)
    _set_default(ap, "exit_friction_from_violence", 1.2)
    _set_default(ap, "exit_friction_from_information", 1.2)
    _set_default(ap, "memory_decay", 0.10)
    _set_default(ap, "prestige_noise", 0.05)

    # Runtime
    rr = resolved["runtime_and_reproducibility"]
    _require_keys(rr, ("total_steps", "burn_in_period", "random_seed"), where="root.runtime_and_reproducibility")
    _set_default(rr, "logging_frequency", 1)

    # Observation
    ob = resolved["observation"]
    _require_keys(ob, ("metrics_to_log", "aggregation_windows"), where="root.observation")

    # -----------------------------------------------------------------
    # Typed objects
    # -----------------------------------------------------------------
    meta = ExperimentMeta(
        experiment_name=str(resolved["experiment_name"]),
        description=str(resolved["description"]),
        author=str(resolved["author"]),
        date_created=str(resolved["date_created"]),
    )

    world_structure = WorldStructure(
        num_patches=int(ws["num_patches"]),
        population_sizes={k: int(v) for k, v in ws["population_sizes"].items()},
        environmental_parameters=dict(ws["environmental_parameters"]),
    )

    seasonality = Seasonality(
        seasonal_period=int(se["seasonal_period"]),
        phase_offsets={k: float(v) for k, v in se["phase_offsets"].items()},
        forcing_amplitudes={k: float(v) for k, v in se["forcing_amplitudes"].items()},
        forcing_sign=dict(se["forcing_sign"]),
    )

    authority_and_power = AuthorityAndPower(
        violence_factor=float(ap["violence_factor"]),
        information_spread_rate=float(ap["information_spread_rate"]),
        charisma_levels={k: float(v) for k, v in ap["charisma_levels"].items()},
        authority_threshold=float(ap["authority_threshold"]),
        authority_steepness=float(ap["authority_steepness"]),
        benefit_scale=float(ap["benefit_scale"]),
        cost_scale=float(ap["cost_scale"]),
        cost_exponent=float(ap["cost_exponent"]),
        rent_scale=float(ap["rent_scale"]),
        domination_tax=float(ap["domination_tax"]),
        lock_in_effects=bool(ap["lock_in_effects"]),
        exit_friction_base=float(ap["exit_friction_base"]),
        exit_friction_from_violence=float(ap["exit_friction_from_violence"]),
        exit_friction_from_information=float(ap["exit_friction_from_information"]),
        memory_decay=float(ap["memory_decay"]),
        prestige_noise=float(ap["prestige_noise"]),
    )

    runtime_and_reproducibility = RuntimeAndReproducibility(
        total_steps=int(rr["total_steps"]),
        burn_in_period=int(rr["burn_in_period"]),
        random_seed=int(rr["random_seed"]),
        logging_frequency=int(rr["logging_frequency"]),
    )

    observation = Observation(
        metrics_to_log=[str(x) for x in ob["metrics_to_log"]],
        aggregation_windows=[int(x) for x in ob["aggregation_windows"]],
    )

    return Config(
        meta=meta,
        world_structure=world_structure,
        seasonality=seasonality,
        authority_and_power=authority_and_power,
        runtime_and_reproducibility=runtime_and_reproducibility,
        observation=observation,
        resolved=resolved,
    )