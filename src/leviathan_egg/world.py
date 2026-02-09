"""
World dynamics for Leviathan Egg.

Phase 3 update:
- Supports multi-patch state containers while preserving Phase-1-equivalent behavior
  when `num_patches=1`.
- Inter-patch coupling v1 is implemented as weak signed coupling on authority pressure.
  Coupling remains disabled by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Set

import numpy as np

from leviathan_egg.config import Config
from leviathan_egg.seasons import seasonal_terms


def _sigmoid(x: float) -> float:
    # Stable-ish sigmoid; for current ranges this is sufficient.
    if x >= 0:
        z = np.exp(-x)
        return 1.0 / (1.0 + z)
    z = np.exp(x)
    return z / (1.0 + z)


@dataclass
class Agent:
    agent_id: int
    patch_id: int
    group_id: int
    prestige: float
    competence: float


@dataclass
class Group:
    group_id: int
    patch_id: int
    members: Set[int]
    authority_on: bool = False
    leader_id: Optional[int] = None


@dataclass
class PatchState:
    patch_id: int
    agent_ids: Set[int]
    group_ids: Set[int]


class World:
    """
    Multi-patch world state with global registries for backward compatibility.

    Determinism guarantee:
      Given the same config + seed, stepping from the same initial state produces the same
      sequence of states and metrics (within floating-point determinism of numpy).
    """

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.runtime_and_reproducibility.random_seed)

        self.num_patches = int(cfg.world_structure.num_patches)
        if self.num_patches <= 0:
            raise ValueError("world_structure.num_patches must be positive")

        # Global registries (kept for existing metric/readers).
        self.agents: Dict[int, Agent] = {}
        self.groups: Dict[int, Group] = {}
        self.patches: Dict[int, PatchState] = {}
        self._next_agent_id = 0
        self._next_group_id = 0

        self._initialize_patches()
        self._hier_frac_history: Dict[int, list[float]] = {
            patch_id: [self._patch_hier_fraction(patch_id)]
            for patch_id in range(self.num_patches)
        }
        self.last_coupling_bias_by_patch: Dict[int, float] = {
            patch_id: 0.0 for patch_id in range(self.num_patches)
        }

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _population_size_for_patch(self, patch_id: int) -> int:
        pop_cfg = self.cfg.world_structure.population_sizes
        if f"patch_{patch_id}" in pop_cfg:
            return int(pop_cfg[f"patch_{patch_id}"])
        return int(pop_cfg.get("agents", 0))

    def _initialize_patches(self) -> None:
        for patch_id in range(self.num_patches):
            n_agents = self._population_size_for_patch(patch_id)
            if n_agents <= 0:
                raise ValueError(
                    f"world_structure.population_sizes for patch_{patch_id} must be positive"
                )

            patch = PatchState(patch_id=patch_id, agent_ids=set(), group_ids=set())
            self.patches[patch_id] = patch

            competences = self.rng.normal(loc=0.0, scale=1.0, size=n_agents)
            prestiges = np.clip(
                self.rng.normal(loc=0.0, scale=1.0, size=n_agents),
                -3.0,
                3.0,
            )

            n_groups_init = max(1, min(n_agents, n_agents // 25))
            assignments = self.rng.integers(low=0, high=n_groups_init, size=n_agents)

            patch_group_ids = []
            for _ in range(n_groups_init):
                gid = self._next_group_id
                self._next_group_id += 1
                self.groups[gid] = Group(group_id=gid, patch_id=patch_id, members=set())
                patch.group_ids.add(gid)
                patch_group_ids.append(gid)

            for local_idx in range(n_agents):
                aid = self._next_agent_id
                self._next_agent_id += 1
                gid = patch_group_ids[int(assignments[local_idx])]
                self.agents[aid] = Agent(
                    agent_id=aid,
                    patch_id=patch_id,
                    group_id=gid,
                    prestige=float(prestiges[local_idx]),
                    competence=float(competences[local_idx]),
                )
                self.groups[gid].members.add(aid)
                patch.agent_ids.add(aid)

            self._recompute_group_states_for_patch(patch_id=patch_id, t=0)

    # ------------------------------------------------------------------
    # Core dynamics
    # ------------------------------------------------------------------

    def step(self, t: int) -> None:
        """
        Advance world state by one time step.

        Dynamics are patch-local by default. If inter-patch coupling is enabled via config,
        seasonal authority pressure receives a coupling bias based on lagged patch hierarchy.
        """
        season_by_patch = {
            patch_id: seasonal_terms(t, self.cfg, patch_id=patch_id)
            for patch_id in range(self.num_patches)
        }

        self._apply_inter_patch_coupling(t=t, season_by_patch=season_by_patch)

        for patch_id in range(self.num_patches):
            season = season_by_patch[patch_id]
            self._recompute_group_states_for_patch(
                patch_id=patch_id, t=t, season=season
            )
            self._movement_step_patch(patch_id=patch_id, t=t, season=season)
            self._prestige_update_patch(patch_id=patch_id, season=season)

        self._cleanup_groups()
        self._record_hierarchy_history()

    def _apply_inter_patch_coupling(
        self, *, t: int, season_by_patch: Dict[int, Dict[str, float]]
    ) -> None:
        _ = t

        for patch_id in range(self.num_patches):
            season_by_patch[patch_id]["coupling_bias"] = 0.0
            self.last_coupling_bias_by_patch[patch_id] = 0.0

        ic = self.cfg.inter_patch_coupling
        if not ic.enabled:
            return

        # Coupling v1 is intentionally weak: authority pressure receives a bounded additive
        # bias derived from lagged hierarchy differences across connected patches.
        max_bias = 0.25

        local_hier = {
            patch_id: self._patch_hier_fraction_lagged(
                patch_id=patch_id, lag_steps=ic.lag_steps
            )
            for patch_id in range(self.num_patches)
        }

        for patch_id in range(self.num_patches):
            neighbors = self._coupling_neighbors(
                patch_id=patch_id,
                mode=ic.mode,
                topology=ic.topology,
            )
            if not neighbors:
                continue

            local = local_hier[patch_id]
            neighbor_values = [local_hier[n] for n in neighbors]

            if ic.mode == "mean_field":
                influence = float(np.mean(neighbor_values) - local)
            else:
                diffs = [v - local for v in neighbor_values]
                influence = float(np.mean(diffs))
                if not ic.normalize_by_degree:
                    influence = float(np.sum(diffs))

            signed = float(ic.sign) * float(ic.strength) * influence
            delta = float(np.clip(max_bias * signed, -max_bias, max_bias))
            season_by_patch[patch_id]["coupling_bias"] = delta
            self.last_coupling_bias_by_patch[patch_id] = delta

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _recompute_group_states_for_patch(
        self,
        *,
        patch_id: int,
        t: int,
        season: Optional[Dict[str, float]] = None,
    ) -> None:
        if season is None:
            season = seasonal_terms(t, self.cfg, patch_id=patch_id)

        ap = self.cfg.authority_and_power
        coord = float(season["coordination_cost"])
        crisis = float(season["crisis"])
        festival = float(season["festival"])
        coupling_bias = float(season.get("coupling_bias", 0.0))

        patch = self.patches[patch_id]
        for gid in sorted(patch.group_ids):
            g = self.groups[gid]
            n = len(g.members)
            if n == 0:
                g.authority_on = False
                g.leader_id = None
                continue

            # κ: coordination load + crisis need
            kappa = coord * (n ** ap.cost_exponent) + (crisis + coupling_bias) * n
            p_auth = _sigmoid(ap.authority_steepness * (kappa - ap.authority_threshold))
            g.authority_on = bool(self.rng.random() < p_auth)

            if not g.authority_on:
                g.leader_id = None
                continue

            best_id = None
            best_score = -1e18
            for aid in sorted(g.members):
                a = self.agents[aid]
                score = a.prestige + a.competence + festival
                if score > best_score:
                    best_score = score
                    best_id = aid
                elif score == best_score:
                    if self.rng.random() < 0.5:
                        best_id = aid
            g.leader_id = best_id

    def _utility(
        self, n: int, *, is_leader: bool, authority_on: bool, season: Dict[str, float]
    ) -> float:
        """
        Utility proxy of belonging to a group of size n in current season.
        Used for movement decisions (fusion/fission).
        """
        ap = self.cfg.authority_and_power
        agg = float(season["aggregation_benefit"])
        coord = float(season["coordination_cost"])
        rent_mult = float(season["hierarchy_rent"])

        u = ap.benefit_scale * agg * float(np.log(max(1, n)))
        u -= ap.cost_scale * coord * (n ** ap.cost_exponent)

        if authority_on:
            if is_leader:
                u += ap.rent_scale * rent_mult * n
            else:
                u -= ap.domination_tax * rent_mult

        return float(u)

    def _exit_friction(self, g: Group) -> float:
        """
        Extra movement penalty when leaving a group.
        """
        ap = self.cfg.authority_and_power
        if not ap.lock_in_effects:
            return float(ap.exit_friction_base)

        friction = float(ap.exit_friction_base)
        if g.authority_on:
            friction += (
                float(ap.exit_friction_from_violence) * float(ap.violence_factor)
            )
            friction += (
                float(ap.exit_friction_from_information)
                * float(ap.information_spread_rate)
            )
        return friction

    def _movement_step_patch(self, *, patch_id: int, t: int, season: Dict[str, float]) -> None:
        patch = self.patches[patch_id]
        if not patch.agent_ids:
            return

        n_agents = len(patch.agent_ids)
        sample_frac = 0.25
        k = max(1, int(sample_frac * n_agents))
        agent_ids = np.array(sorted(patch.agent_ids), dtype=int)
        sampled = self.rng.choice(agent_ids, size=k, replace=False)

        group_ids = sorted(patch.group_ids)
        if not group_ids:
            return

        for aid in sampled:
            a = self.agents[int(aid)]
            g_cur = self.groups[a.group_id]
            n_cur = len(g_cur.members)
            is_leader = bool(g_cur.authority_on and g_cur.leader_id == a.agent_id)

            u_stay = self._utility(
                n_cur,
                is_leader=is_leader,
                authority_on=g_cur.authority_on,
                season=season,
            )
            u_split = self._utility(
                1, is_leader=False, authority_on=False, season=season
            )
            u_split -= self._exit_friction(g_cur)

            if len(group_ids) > 1:
                other_choices = [gid for gid in group_ids if gid != a.group_id]
                gid_other = int(self.rng.choice(np.array(other_choices, dtype=int)))
                g_other = self.groups[gid_other]
                n_other = len(g_other.members) + 1
                u_move = self._utility(
                    n_other,
                    is_leader=False,
                    authority_on=g_other.authority_on,
                    season=season,
                )
                u_move -= self._exit_friction(g_cur)
            else:
                gid_other = -1
                u_move = -1e18

            best = u_stay
            action = "stay"
            if u_move > best:
                best = u_move
                action = "move"
            if u_split > best:
                action = "split"

            if action == "stay":
                continue

            if action == "move" and gid_other >= 0:
                self._move_agent(a.agent_id, from_gid=a.group_id, to_gid=gid_other)
            elif action == "split":
                new_gid = self._next_group_id
                self._next_group_id += 1
                self.groups[new_gid] = Group(
                    group_id=new_gid,
                    patch_id=patch_id,
                    members=set(),
                    authority_on=False,
                    leader_id=None,
                )
                self.patches[patch_id].group_ids.add(new_gid)
                self._move_agent(a.agent_id, from_gid=a.group_id, to_gid=new_gid)

        self._recompute_group_states_for_patch(patch_id=patch_id, t=t, season=season)

    def _move_agent(self, aid: int, *, from_gid: int, to_gid: int) -> None:
        if from_gid == to_gid:
            return
        if from_gid not in self.groups or to_gid not in self.groups:
            return
        if aid not in self.groups[from_gid].members:
            return
        if self.groups[from_gid].patch_id != self.groups[to_gid].patch_id:
            raise ValueError("cross-patch agent moves are not enabled in Phase 3 scaffolding")

        self.groups[from_gid].members.remove(aid)
        self.groups[to_gid].members.add(aid)
        self.agents[aid].group_id = to_gid

    def _prestige_update_patch(self, *, patch_id: int, season: Dict[str, float]) -> None:
        ap = self.cfg.authority_and_power
        decay = float(ap.memory_decay)
        noise = float(ap.prestige_noise)
        festival = float(season["festival"])

        patch = self.patches[patch_id]
        leader_ids = {
            self.groups[gid].leader_id
            for gid in patch.group_ids
            if self.groups[gid].authority_on and self.groups[gid].leader_id is not None
        }

        for aid in sorted(patch.agent_ids):
            a = self.agents[aid]
            a.prestige = (1.0 - decay) * a.prestige + float(self.rng.normal(0.0, noise))
            if a.agent_id in leader_ids:
                a.prestige += float(festival)
            a.prestige = float(np.clip(a.prestige, -10.0, 10.0))

    def _cleanup_groups(self) -> None:
        empty = [gid for gid, g in self.groups.items() if len(g.members) == 0]
        for gid in empty:
            patch_id = self.groups[gid].patch_id
            del self.groups[gid]
            self.patches[patch_id].group_ids.discard(gid)

        for g in self.groups.values():
            if g.leader_id is not None and g.leader_id not in g.members:
                g.leader_id = None
                g.authority_on = False

    def _patch_hier_fraction(self, patch_id: int) -> float:
        patch = self.patches[patch_id]
        total_agents = len(patch.agent_ids)
        if total_agents == 0:
            return 0.0

        hier_agents = 0
        for gid in patch.group_ids:
            g = self.groups[gid]
            if g.authority_on:
                hier_agents += len(g.members)
        return hier_agents / total_agents

    def _patch_hier_fraction_lagged(self, *, patch_id: int, lag_steps: int) -> float:
        series = self._hier_frac_history[patch_id]
        if not series:
            return self._patch_hier_fraction(patch_id)
        idx = max(0, len(series) - 1 - max(0, int(lag_steps)))
        return float(series[idx])

    def _coupling_neighbors(
        self,
        *,
        patch_id: int,
        mode: str,
        topology: str,
    ) -> list[int]:
        if self.num_patches <= 1 or mode == "none":
            return []

        if mode == "mean_field" or topology == "all_to_all":
            return [pid for pid in range(self.num_patches) if pid != patch_id]

        if topology == "ring":
            left = (patch_id - 1) % self.num_patches
            right = (patch_id + 1) % self.num_patches
            if left == right:
                return [left]
            return [left, right]

        return [pid for pid in range(self.num_patches) if pid != patch_id]

    def _record_hierarchy_history(self) -> None:
        for patch_id in range(self.num_patches):
            self._hier_frac_history[patch_id].append(
                self._patch_hier_fraction(patch_id)
            )

    def patch_hierarchy_history(
        self, patch_id: int, *, window: Optional[int] = None
    ) -> list[float]:
        history = self._hier_frac_history.get(patch_id, [])
        if window is None or window <= 0 or window >= len(history):
            return list(history)
        return list(history[-window:])

    # ------------------------------------------------------------------
    # Convenience / inspection helpers
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, object]:
        """Small serializable snapshot for debugging and tests."""
        return {
            "num_patches": self.num_patches,
            "num_agents": len(self.agents),
            "num_groups": len(self.groups),
            "patches": {
                patch_id: {
                    "num_agents": len(self.patches[patch_id].agent_ids),
                    "num_groups": len(self.patches[patch_id].group_ids),
                }
                for patch_id in range(self.num_patches)
            },
            "groups": {
                gid: {
                    "patch_id": g.patch_id,
                    "size": len(g.members),
                    "authority_on": g.authority_on,
                    "leader_id": g.leader_id,
                }
                for gid, g in self.groups.items()
            },
            "agent_groups": {aid: a.group_id for aid, a in self.agents.items()},
            "agent_patches": {aid: a.patch_id for aid, a in self.agents.items()},
            "agent_prestige": {aid: a.prestige for aid, a in self.agents.items()},
        }
