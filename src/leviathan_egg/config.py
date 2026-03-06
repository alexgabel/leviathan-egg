

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

ALLOWED_COUPLING_MODES = ("none", "mean_field", "pairwise")
ALLOWED_COUPLING_TOPOLOGIES = ("all_to_all", "ring")
ALLOWED_COUPLING_TARGET_METRICS = ("frac_hier",)
ALLOWED_GRAPH_MODES = ("undirected_contact", "directed_influence")
ALLOWED_HYPERBOLICITY_PROXY_MODES = ("tree_likeness",)


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


def _validate_phase_offsets(phase_offsets: Mapping[str, Any], *, num_patches: int) -> None:
    required = [f"patch_{i}" for i in range(num_patches)]
    missing = [k for k in required if k not in phase_offsets]
    if missing:
        raise ConfigError(
            "Missing required seasonality.phase_offsets key(s) for num_patches="
            f"{num_patches}: {', '.join(missing)}"
        )


def _validate_inter_patch_coupling(
    ic: Mapping[str, Any], *, num_patches: int
) -> None:
    if not isinstance(ic["enabled"], bool):
        raise ConfigError("root.inter_patch_coupling.enabled must be boolean")
    if not isinstance(ic["normalize_by_degree"], bool):
        raise ConfigError(
            "root.inter_patch_coupling.normalize_by_degree must be boolean"
        )

    mode = str(ic["mode"])
    if mode not in ALLOWED_COUPLING_MODES:
        raise ConfigError(
            "root.inter_patch_coupling.mode must be one of "
            f"{ALLOWED_COUPLING_MODES}; got {mode!r}"
        )

    topology = str(ic["topology"])
    if topology not in ALLOWED_COUPLING_TOPOLOGIES:
        raise ConfigError(
            "root.inter_patch_coupling.topology must be one of "
            f"{ALLOWED_COUPLING_TOPOLOGIES}; got {topology!r}"
        )

    target_metric = str(ic["target_metric"])
    if target_metric not in ALLOWED_COUPLING_TARGET_METRICS:
        raise ConfigError(
            "root.inter_patch_coupling.target_metric must be one of "
            f"{ALLOWED_COUPLING_TARGET_METRICS}; got {target_metric!r}"
        )

    try:
        strength = float(ic["strength"])
    except (TypeError, ValueError) as e:
        raise ConfigError(
            "root.inter_patch_coupling.strength must be numeric"
        ) from e
    if not (0.0 <= strength <= 1.0):
        raise ConfigError(
            "root.inter_patch_coupling.strength must be in [0, 1]"
        )

    try:
        sign = int(ic["sign"])
    except (TypeError, ValueError) as e:
        raise ConfigError("root.inter_patch_coupling.sign must be integer") from e
    if sign not in (-1, 0, 1):
        raise ConfigError("root.inter_patch_coupling.sign must be one of -1, 0, 1")

    try:
        lag_steps = int(ic["lag_steps"])
    except (TypeError, ValueError) as e:
        raise ConfigError(
            "root.inter_patch_coupling.lag_steps must be integer"
        ) from e
    if lag_steps < 0:
        raise ConfigError("root.inter_patch_coupling.lag_steps must be >= 0")

    enabled = bool(ic["enabled"])
    if enabled:
        if num_patches < 2:
            raise ConfigError(
                "root.inter_patch_coupling.enabled=true requires world_structure.num_patches >= 2"
            )
        if mode == "none":
            raise ConfigError(
                "root.inter_patch_coupling.enabled=true requires mode != 'none'"
            )
        if strength <= 0.0:
            raise ConfigError(
                "root.inter_patch_coupling.enabled=true requires strength > 0"
            )
    else:
        if mode != "none":
            raise ConfigError(
                "root.inter_patch_coupling.enabled=false requires mode='none'"
            )
        if strength != 0.0:
            raise ConfigError(
                "root.inter_patch_coupling.enabled=false requires strength=0.0"
            )


def _validate_graph_extraction(ge: Mapping[str, Any]) -> None:
    if not isinstance(ge["enabled"], bool):
        raise ConfigError("root.graph_extraction.enabled must be boolean")
    if not isinstance(ge["emit_edge_list"], bool):
        raise ConfigError("root.graph_extraction.emit_edge_list must be boolean")
    if not isinstance(ge["emit_window_metrics"], bool):
        raise ConfigError("root.graph_extraction.emit_window_metrics must be boolean")
    if not isinstance(ge["pool_patches"], bool):
        raise ConfigError("root.graph_extraction.pool_patches must be boolean")

    graph_mode = str(ge["graph_mode"])
    if graph_mode not in ALLOWED_GRAPH_MODES:
        raise ConfigError(
            "root.graph_extraction.graph_mode must be one of "
            f"{ALLOWED_GRAPH_MODES}; got {graph_mode!r}"
        )

    try:
        window_periods = int(ge["window_periods"])
    except (TypeError, ValueError) as e:
        raise ConfigError("root.graph_extraction.window_periods must be integer") from e
    if window_periods < 1:
        raise ConfigError("root.graph_extraction.window_periods must be >= 1")


def _validate_structural_metrics(sm: Mapping[str, Any]) -> None:
    metrics_to_compute = sm["metrics_to_compute"]
    if not isinstance(metrics_to_compute, list) or not all(
        isinstance(item, str) for item in metrics_to_compute
    ):
        raise ConfigError(
            "root.structural_metrics.metrics_to_compute must be a list of strings"
        )

    proxy_mode = str(sm["hyperbolicity_proxy_mode"])
    if proxy_mode not in ALLOWED_HYPERBOLICITY_PROXY_MODES:
        raise ConfigError(
            "root.structural_metrics.hyperbolicity_proxy_mode must be one of "
            f"{ALLOWED_HYPERBOLICITY_PROXY_MODES}; got {proxy_mode!r}"
        )


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
class InterPatchCoupling:
    enabled: bool
    mode: str
    topology: str
    strength: float
    sign: int
    lag_steps: int
    normalize_by_degree: bool
    target_metric: str


@dataclass(frozen=True)
class GraphExtraction:
    enabled: bool
    graph_mode: str
    window_periods: int
    emit_edge_list: bool
    emit_window_metrics: bool
    pool_patches: bool


@dataclass(frozen=True)
class StructuralMetrics:
    metrics_to_compute: list[str]
    hyperbolicity_proxy_mode: str


@dataclass(frozen=True)
class Config:
    schema_version: str
    meta: ExperimentMeta
    world_structure: WorldStructure
    seasonality: Seasonality
    authority_and_power: AuthorityAndPower
    runtime_and_reproducibility: RuntimeAndReproducibility
    observation: Observation
    inter_patch_coupling: InterPatchCoupling
    graph_extraction: GraphExtraction
    structural_metrics: StructuralMetrics
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
    _set_default(resolved, "schema_version", "1.0")
    _set_default(resolved, "inter_patch_coupling", {})
    _set_default(resolved, "graph_extraction", {})
    _set_default(resolved, "structural_metrics", {})

    for section in REQUIRED_TOP_LEVEL_SECTIONS:
        resolved[section] = dict(_expect_mapping(resolved[section], where=f"root.{section}"))
    resolved["inter_patch_coupling"] = dict(
        _expect_mapping(
            resolved["inter_patch_coupling"],
            where="root.inter_patch_coupling",
        )
    )
    resolved["graph_extraction"] = dict(
        _expect_mapping(
            resolved["graph_extraction"],
            where="root.graph_extraction",
        )
    )
    resolved["structural_metrics"] = dict(
        _expect_mapping(
            resolved["structural_metrics"],
            where="root.structural_metrics",
        )
    )

    # World structure
    ws = resolved["world_structure"]
    _require_keys(ws, ("num_patches", "population_sizes"), where="root.world_structure")
    _set_default(ws, "environmental_parameters", {})
    try:
        num_patches = int(ws["num_patches"])
    except (TypeError, ValueError) as e:
        raise ConfigError("root.world_structure.num_patches must be integer") from e
    if num_patches < 1:
        raise ConfigError("root.world_structure.num_patches must be >= 1")

    # Seasonality
    se = resolved["seasonality"]
    _require_keys(
        se,
        ("seasonal_period", "phase_offsets", "forcing_amplitudes", "forcing_sign"),
        where="root.seasonality",
    )
    se["phase_offsets"] = dict(
        _expect_mapping(se["phase_offsets"], where="root.seasonality.phase_offsets")
    )
    se["forcing_amplitudes"] = dict(
        _expect_mapping(
            se["forcing_amplitudes"], where="root.seasonality.forcing_amplitudes"
        )
    )
    se["forcing_sign"] = dict(
        _expect_mapping(se["forcing_sign"], where="root.seasonality.forcing_sign")
    )
    _validate_phase_offsets(se["phase_offsets"], num_patches=num_patches)

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

    # Inter-patch coupling (Phase 3 scaffolding)
    ic = resolved["inter_patch_coupling"]
    _set_default(ic, "enabled", False)
    _set_default(ic, "mode", "none")
    _set_default(ic, "topology", "all_to_all")
    _set_default(ic, "strength", 0.0)
    _set_default(ic, "sign", 1)
    _set_default(ic, "lag_steps", 0)
    _set_default(ic, "normalize_by_degree", True)
    _set_default(ic, "target_metric", "frac_hier")
    _validate_inter_patch_coupling(ic, num_patches=num_patches)

    # Phase 4 structural observation
    ge = resolved["graph_extraction"]
    _set_default(ge, "enabled", False)
    _set_default(ge, "graph_mode", "undirected_contact")
    _set_default(ge, "window_periods", 1)
    _set_default(ge, "emit_edge_list", False)
    _set_default(ge, "emit_window_metrics", False)
    _set_default(ge, "pool_patches", False)
    _validate_graph_extraction(ge)

    sm = resolved["structural_metrics"]
    _set_default(
        sm,
        "metrics_to_compute",
        [
            "density",
            "clustering_mean",
            "tree_excess_ratio",
            "branching_skew",
            "delta_hyperbolicity_proxy",
        ],
    )
    _set_default(sm, "hyperbolicity_proxy_mode", "tree_likeness")
    _validate_structural_metrics(sm)

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
        num_patches=num_patches,
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

    inter_patch_coupling = InterPatchCoupling(
        enabled=bool(ic["enabled"]),
        mode=str(ic["mode"]),
        topology=str(ic["topology"]),
        strength=float(ic["strength"]),
        sign=int(ic["sign"]),
        lag_steps=int(ic["lag_steps"]),
        normalize_by_degree=bool(ic["normalize_by_degree"]),
        target_metric=str(ic["target_metric"]),
    )

    graph_extraction = GraphExtraction(
        enabled=bool(ge["enabled"]),
        graph_mode=str(ge["graph_mode"]),
        window_periods=int(ge["window_periods"]),
        emit_edge_list=bool(ge["emit_edge_list"]),
        emit_window_metrics=bool(ge["emit_window_metrics"]),
        pool_patches=bool(ge["pool_patches"]),
    )

    structural_metrics = StructuralMetrics(
        metrics_to_compute=[str(x) for x in sm["metrics_to_compute"]],
        hyperbolicity_proxy_mode=str(sm["hyperbolicity_proxy_mode"]),
    )

    return Config(
        schema_version=str(resolved["schema_version"]),
        meta=meta,
        world_structure=world_structure,
        seasonality=seasonality,
        authority_and_power=authority_and_power,
        runtime_and_reproducibility=runtime_and_reproducibility,
        observation=observation,
        inter_patch_coupling=inter_patch_coupling,
        graph_extraction=graph_extraction,
        structural_metrics=structural_metrics,
        resolved=resolved,
    )
