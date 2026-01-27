"""
World dynamics for Leviathan Egg.

Phase 1.D (single-patch core engine):
- Agents have prestige, competence, and group membership.
- Groups have members, an authority on/off state, and a leader (or None).
- Seasonality provides scalar drivers; authority is a stochastic logistic switch on κ.
- Agents may move between groups (fusion) or spawn new groups (fission) by utility comparison.
- Exit friction increases when leaving hierarchical groups (violence + information channels).
- Prestige evolves with decay + noise; leaders get a festival boost.

This is intentionally minimal and designed for Phase 1 only (single patch).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from leviathan_egg.config import Config
from leviathan_egg.seasons import seasonal_terms


def _sigmoid(x: float) -> float:
    # Stable-ish sigmoid; for Phase 1 ranges this is sufficient.
    if x >= 0:
        z = np.exp(-x)
        return 1.0 / (1.0 + z)
    z = np.exp(x)
    return z / (1.0 + z)


@dataclass
class Agent:
    agent_id: int
    group_id: int
    prestige: float
    competence: float


@dataclass
class Group:
    group_id: int
    members: Set[int]
    authority_on: bool = False
    leader_id: Optional[int] = None


class World:
    """
    Single-patch world state.

    Determinism guarantee:
      Given the same config + seed, stepping from the same initial state produces the same
      sequence of states and metrics (within floating point determinism of numpy).
    """

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.runtime_and_reproducibility.random_seed)

        n_agents = int(cfg.world_structure.population_sizes.get("agents", 0))
        if n_agents <= 0:
            raise ValueError("world_structure.population_sizes.agents must be positive")

        # Initialize agents with fixed competence and initial prestige.
        # Competence: static "skill" term; Prestige: dynamic state updated over time.
        competences = self.rng.normal(loc=0.0, scale=1.0, size=n_agents)
        prestiges = np.clip(self.rng.normal(loc=0.0, scale=1.0, size=n_agents), -3.0, 3.0)

        # Initialize a small number of groups with random assignment (fission–fusion will adapt).
        n_groups_init = max(1, min(n_agents, n_agents // 25))
        group_ids = np.arange(n_groups_init, dtype=int)
        assignments = self.rng.integers(low=0, high=n_groups_init, size=n_agents)

        self.agents: Dict[int, Agent] = {}
        self.groups: Dict[int, Group] = {}

        for gid in group_ids:
            self.groups[int(gid)] = Group(group_id=int(gid), members=set())

        for i in range(n_agents):
            gid = int(assignments[i])
            self.agents[i] = Agent(
                agent_id=i,
                group_id=gid,
                prestige=float(prestiges[i]),
                competence=float(competences[i]),
            )
            self.groups[gid].members.add(i)

        self._next_group_id = n_groups_init

        # Ensure group states are initialized (authority + leader)
        self._recompute_group_states(t=0)

    # ------------------------------------------------------------------
    # Core dynamics
    # ------------------------------------------------------------------

    def step(self, t: int) -> None:
        """
        Advance the world state by one time step.

        This mutates agent prestiges, group authority states, leaders, and memberships.
        """
        # 1) Determine seasonal drivers (single patch)
        season = seasonal_terms(t, self.cfg, patch_id=0)

        # 2) Update group authority states and leaders based on κ and seasonal festival
        self._recompute_group_states(t=t, season=season)

        # 3) Movement: agents consider moving (fusion) or splitting off (fission)
        self._movement_step(t=t, season=season)

        # 4) Prestige update: decay + noise; leader festival boost
        self._prestige_update(t=t, season=season)

        # 5) Clean up empty groups and reindex leaders if needed
        self._cleanup_groups()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _recompute_group_states(self, t: int, season: Optional[Dict[str, float]] = None) -> None:
        if season is None:
            season = seasonal_terms(t, self.cfg, patch_id=0)

        ap = self.cfg.authority_and_power

        coord = float(season["coordination_cost"])
        crisis = float(season["crisis"])
        festival = float(season["festival"])

        for g in self.groups.values():
            n = len(g.members)
            if n == 0:
                g.authority_on = False
                g.leader_id = None
                continue

            # κ: coordination load + crisis need
            # Coordination load grows superlinearly; crisis scales with group size.
            kappa = coord * (n ** ap.cost_exponent) + crisis * n

            # Logistic probability of authority being "on"
            p_auth = _sigmoid(ap.authority_steepness * (kappa - ap.authority_threshold))
            g.authority_on = bool(self.rng.random() < p_auth)

            # Choose leader if authority is on; otherwise no leader.
            if not g.authority_on:
                g.leader_id = None
                continue

            # Leader selection: prestige + competence, with festival boost for charismatic moments.
            best_id = None
            best_score = -1e18
            for aid in g.members:
                a = self.agents[aid]
                score = a.prestige + a.competence + festival
                if score > best_score:
                    best_score = score
                    best_id = aid
                elif score == best_score:
                    # tie-break deterministically via RNG
                    if self.rng.random() < 0.5:
                        best_id = aid
            g.leader_id = best_id

    def _utility(self, n: int, *, is_leader: bool, authority_on: bool, season: Dict[str, float]) -> float:
        """
        Utility proxy of belonging to a group of size n in current season.
        Used for movement decisions (fusion/fission).

        Intuition:
          - aggregation benefit ~ log(n)
          - coordination cost ~ n^phi
          - hierarchy rent benefits leader, domination tax harms non-leaders when authority_on
        """
        ap = self.cfg.authority_and_power
        agg = float(season["aggregation_benefit"])
        coord = float(season["coordination_cost"])
        rent_mult = float(season["hierarchy_rent"])

        # Base: benefits of aggregation with diminishing returns
        u = ap.benefit_scale * agg * float(np.log(max(1, n)))

        # Costs: coordination (convex)
        u -= ap.cost_scale * coord * (n ** ap.cost_exponent)

        if authority_on:
            if is_leader:
                # Leader receives rents, scaled by group size and seasonality
                u += ap.rent_scale * rent_mult * n
            else:
                # Non-leaders pay domination tax (disutility)
                u -= ap.domination_tax * rent_mult

        return float(u)

    def _exit_friction(self, g: Group) -> float:
        """
        Extra movement penalty when leaving a group.
        When authority is on, violence + information increase exit friction (lock-in).
        """
        ap = self.cfg.authority_and_power
        if not ap.lock_in_effects:
            return float(ap.exit_friction_base)

        friction = float(ap.exit_friction_base)
        if g.authority_on:
            friction += float(ap.exit_friction_from_violence) * float(ap.violence_factor)
            friction += float(ap.exit_friction_from_information) * float(ap.information_spread_rate)
        return friction

    def _movement_step(self, t: int, season: Dict[str, float]) -> None:
        """
        Minimal fission/fusion dynamics.

        Each agent evaluates:
          - stay in current group
          - move to a sampled candidate group (fusion)
          - split off into a new singleton group (fission)
        and chooses the best option after accounting for exit friction.
        """
        # Sample a fraction of agents per step for efficiency and to avoid unrealistic global coordination.
        n_agents = len(self.agents)
        sample_frac = 0.25
        k = max(1, int(sample_frac * n_agents))
        sampled = self.rng.choice(n_agents, size=k, replace=False)

        group_ids = list(self.groups.keys())
        if len(group_ids) == 0:
            return

        for aid in sampled:
            a = self.agents[int(aid)]
            g_cur = self.groups[a.group_id]
            n_cur = len(g_cur.members)

            # Determine if the agent is leader (only meaningful if authority on)
            is_leader = bool(g_cur.authority_on and g_cur.leader_id == a.agent_id)

            u_stay = self._utility(n_cur, is_leader=is_leader, authority_on=g_cur.authority_on, season=season)

            # Consider fission: become a singleton group (authority off by default)
            u_split = self._utility(1, is_leader=False, authority_on=False, season=season)
            u_split -= self._exit_friction(g_cur)

            # Consider fusion: move to a random other group
            if len(group_ids) > 1:
                gid_other = int(self.rng.choice([gid for gid in group_ids if gid != a.group_id]))
                g_other = self.groups[gid_other]
                n_other = len(g_other.members) + 1

                # If moving, you are not leader immediately (leadership recomputed next step)
                u_move = self._utility(n_other, is_leader=False, authority_on=g_other.authority_on, season=season)
                u_move -= self._exit_friction(g_cur)
            else:
                u_move = -1e18
                gid_other = -1

            # Choose best option
            best = u_stay
            action = "stay"
            if u_move > best:
                best = u_move
                action = "move"
            if u_split > best:
                best = u_split
                action = "split"

            if action == "stay":
                continue

            # Apply action
            if action == "move" and gid_other >= 0:
                self._move_agent(a.agent_id, from_gid=a.group_id, to_gid=gid_other)
            elif action == "split":
                new_gid = self._next_group_id
                self._next_group_id += 1
                self.groups[new_gid] = Group(group_id=new_gid, members=set(), authority_on=False, leader_id=None)
                self._move_agent(a.agent_id, from_gid=a.group_id, to_gid=new_gid)

        # After movement, group leadership/authority can be stale; recompute quickly at current t.
        self._recompute_group_states(t=t, season=season)

    def _move_agent(self, aid: int, *, from_gid: int, to_gid: int) -> None:
        if from_gid == to_gid:
            return
        if aid not in self.groups[from_gid].members:
            return
        self.groups[from_gid].members.remove(aid)
        self.groups[to_gid].members.add(aid)
        self.agents[aid].group_id = to_gid

    def _prestige_update(self, t: int, season: Dict[str, float]) -> None:
        ap = self.cfg.authority_and_power
        decay = float(ap.memory_decay)
        noise = float(ap.prestige_noise)
        festival = float(season["festival"])

        # Map leader ids for quick lookup
        leader_ids = {g.leader_id for g in self.groups.values() if g.authority_on and g.leader_id is not None}

        for a in self.agents.values():
            # Exponential-ish decay toward 0 plus Gaussian noise
            a.prestige = (1.0 - decay) * a.prestige + float(self.rng.normal(0.0, noise))

            # Leaders get boosted during festivals (charisma channel)
            if a.agent_id in leader_ids:
                a.prestige += float(festival)

            # Clip to keep values bounded (helps stability)
            a.prestige = float(np.clip(a.prestige, -10.0, 10.0))

    def _cleanup_groups(self) -> None:
        empty = [gid for gid, g in self.groups.items() if len(g.members) == 0]
        for gid in empty:
            del self.groups[gid]

        # Ensure each group's leader is still a member
        for g in self.groups.values():
            if g.leader_id is not None and g.leader_id not in g.members:
                g.leader_id = None
                g.authority_on = False

    # ------------------------------------------------------------------
    # Convenience / inspection helpers
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, object]:
        """Small serializable snapshot for debugging and tests."""
        return {
            "num_agents": len(self.agents),
            "num_groups": len(self.groups),
            "groups": {
                gid: {
                    "size": len(g.members),
                    "authority_on": g.authority_on,
                    "leader_id": g.leader_id,
                }
                for gid, g in self.groups.items()
            },
            "agent_groups": {aid: a.group_id for aid, a in self.agents.items()},
            "agent_prestige": {aid: a.prestige for aid, a in self.agents.items()},
        }
