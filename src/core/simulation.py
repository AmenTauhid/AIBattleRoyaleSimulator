"""Single game simulation loop with event logging."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.core.agent import (
    Action,
    ActionType,
    Agent,
    BehaviorType,
    Buff,
    Stats,
    decide_action,
    generate_agents,
)
from src.core.combat import resolve_combat
from src.core.map import GameMap, generate_map, shrink_zone, spawn_supply_drop


@dataclass(slots=True)
class KillEvent:
    turn: int
    killer_id: int
    victim_id: int
    x: int
    y: int
    cause: str


@dataclass(slots=True)
class DeathEvent:
    turn: int
    agent_id: int
    x: int
    y: int
    cause: str


@dataclass
class AgentSummary:
    agent_id: int
    behavior: BehaviorType
    base_stats: Stats
    kills: int
    damage_dealt: int
    damage_taken: int
    turns_survived: int
    placement: int
    cause_of_death: str


@dataclass
class SimulationResult:
    winner_id: int
    winner_behavior: BehaviorType
    winner_stats: Stats
    total_turns: int
    kill_events: list[KillEvent]
    death_events: list[DeathEvent]
    agent_summaries: list[AgentSummary]
    map_width: int
    map_height: int


@dataclass
class GameState:
    game_map: GameMap
    agents: list[Agent]
    turn: int = 0
    kill_events: list[KillEvent] = field(default_factory=list)
    death_events: list[DeathEvent] = field(default_factory=list)
    death_order: list[int] = field(default_factory=list)  # agent ids in death order

    @property
    def alive_agents(self) -> list[Agent]:
        return [a for a in self.agents if a.alive]

    @property
    def alive_count(self) -> int:
        return sum(1 for a in self.agents if a.alive)


def _kill_agent(agent: Agent, state: GameState, cause: str, killer_id: int = -1) -> None:
    """Mark agent dead and log events."""
    agent.alive = False
    state.death_order.append(agent.id)

    state.death_events.append(DeathEvent(
        turn=state.turn, agent_id=agent.id,
        x=agent.x, y=agent.y, cause=cause,
    ))
    if killer_id >= 0:
        state.kill_events.append(KillEvent(
            turn=state.turn, killer_id=killer_id, victim_id=agent.id,
            x=agent.x, y=agent.y, cause=cause,
        ))


def _apply_zone_damage(state: GameState) -> None:
    """Deal damage to agents outside the safe zone."""
    gm = state.game_map
    for agent in state.alive_agents:
        if not gm.in_zone(agent.x, agent.y):
            agent.hp -= gm.zone_damage
            agent.damage_taken += gm.zone_damage
            if agent.hp <= 0:
                _kill_agent(agent, state, cause="zone")


def _tick_buffs(agents: list[Agent]) -> None:
    """Decrement buff timers and remove expired buffs."""
    for agent in agents:
        if not agent.alive:
            continue
        remaining = []
        for buff in agent.active_buffs:
            buff.turns_remaining -= 1
            if buff.turns_remaining > 0:
                remaining.append(buff)
        agent.active_buffs = remaining


def _resolve_movement(
    agent: Agent,
    action: Action,
    state: GameState,
) -> None:
    """Move agent according to its decided action."""
    if action.type not in (ActionType.MOVE, ActionType.FLEE):
        return

    speed = agent.effective_stat("speed")
    steps = max(1, speed)

    # Water slows movement by 50%
    if state.game_map.is_water(agent.x, agent.y):
        steps = max(1, steps // 2)

    dx, dy = action.dx, action.dy
    for _ in range(steps):
        nx, ny = agent.x + dx, agent.y + dy
        if state.game_map.is_walkable(nx, ny):
            agent.x = nx
            agent.y = ny
        else:
            if dx != 0 and state.game_map.is_walkable(agent.x + dx, agent.y):
                agent.x += dx
            elif dy != 0 and state.game_map.is_walkable(agent.x, agent.y + dy):
                agent.y += dy
            break


def _check_loot(agent: Agent, state: GameState) -> None:
    """Pick up loot, weapons, armor, and supply drops on the agent's tile."""
    # Stat buff loot
    for loot in state.game_map.loot_items:
        if not loot.collected and loot.x == agent.x and loot.y == agent.y:
            loot.collected = True
            agent.loot_collected += 1
            agent.active_buffs.append(Buff(
                stat_name=loot.stat_name,
                amount=loot.amount,
                turns_remaining=loot.duration,
            ))
            break

    # Ground weapons (pick up if better than current)
    gm = state.game_map
    remaining_weapons = []
    for wx, wy, weapon in gm.ground_weapons:
        if wx == agent.x and wy == agent.y:
            if agent.weapon is None or weapon.tier > agent.weapon.tier:
                agent.weapon = weapon
            # Either way, remove from ground
        else:
            remaining_weapons.append((wx, wy, weapon))
    gm.ground_weapons = remaining_weapons

    # Ground armor (pick up if better than current)
    remaining_armor = []
    for ax, ay, armor in gm.ground_armor:
        if ax == agent.x and ay == agent.y:
            if agent.armor is None or armor.tier > agent.armor.tier:
                agent.armor = armor
        else:
            remaining_armor.append((ax, ay, armor))
    gm.ground_armor = remaining_armor

    # Supply drops
    for drop in gm.supply_drops:
        if not drop.collected and drop.x == agent.x and drop.y == agent.y:
            drop.collected = True
            if drop.weapon and (agent.weapon is None or drop.weapon.tier > agent.weapon.tier):
                agent.weapon = drop.weapon
            if drop.armor and (agent.armor is None or drop.armor.tier > agent.armor.tier):
                agent.armor = drop.armor


def _find_combat_pairs(state: GameState) -> list[tuple[Agent, Agent]]:
    """Find pairs of alive agents on same or adjacent tiles."""
    alive = state.alive_agents
    # Spatial hash for fast lookup
    positions: dict[tuple[int, int], list[Agent]] = {}
    for a in alive:
        positions.setdefault((a.x, a.y), []).append(a)

    seen_pairs: set[tuple[int, int]] = set()
    pairs: list[tuple[Agent, Agent]] = []

    # Same-tile combat
    for agents_on_tile in positions.values():
        for i in range(len(agents_on_tile)):
            for j in range(i + 1, len(agents_on_tile)):
                a, b = agents_on_tile[i], agents_on_tile[j]
                pair_key = (min(a.id, b.id), max(a.id, b.id))
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    pairs.append((a, b))

    # Near-tile combat (within 2 tiles)
    for (x, y), agents_here in positions.items():
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if dx == 0 and dy == 0:
                    continue
                if abs(dx) + abs(dy) > 2:
                    continue  # Manhattan distance cap
                neighbor = (x + dx, y + dy)
                if neighbor in positions:
                    for a in agents_here:
                        for b in positions[neighbor]:
                            pair_key = (min(a.id, b.id), max(a.id, b.id))
                            if pair_key not in seen_pairs:
                                seen_pairs.add(pair_key)
                                pairs.append((a, b))

    return pairs


def _resolve_all_combat(state: GameState, rng: np.random.Generator) -> None:
    """Resolve all combat encounters for this turn."""
    pairs = _find_combat_pairs(state)
    # Shuffle to avoid systematic bias
    rng.shuffle(pairs)

    for a, b in pairs:
        if not a.alive or not b.alive:
            continue

        result = resolve_combat(a, b, rng, game_map=state.game_map)

        if result["escaped"]:
            # Defender flees to adjacent tile
            for ddx, ddy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = b.x + ddx, b.y + ddy
                if state.game_map.is_walkable(nx, ny):
                    b.x, b.y = nx, ny
                    break
            continue

        if result["defender_died"]:
            _kill_agent(b, state, cause="combat", killer_id=a.id)
            # Kill reward: heal 25% max HP
            a.hp = min(a.max_hp, a.hp + a.max_hp // 4)
        if result["attacker_died"]:
            _kill_agent(a, state, cause="combat", killer_id=b.id)
            b.hp = min(b.max_hp, b.hp + b.max_hp // 4)


def _run_turn(state: GameState, agents: list[Agent], game_map: GameMap,
              rng: np.random.Generator, zone_shrink_interval: int) -> None:
    """Execute a single turn of the simulation (mutates state in place)."""
    state.turn += 1

    # Zone shrink
    if state.turn % zone_shrink_interval == 0:
        shrink_zone(state.game_map)

    # Supply drop every 30 turns
    if state.turn % 30 == 0 and state.alive_count > 5:
        spawn_supply_drop(state.game_map, rng, state.turn)

    # Zone damage
    _apply_zone_damage(state)

    if state.alive_count <= 1:
        return

    # Buff tick
    _tick_buffs(agents)

    # Decision phase
    actions: dict[int, Action] = {}
    alive = state.alive_agents
    for agent in alive:
        actions[agent.id] = decide_action(agent, agents, game_map, rng)

    # Movement (random order)
    move_order = list(range(len(alive)))
    rng.shuffle(move_order)
    for idx in move_order:
        agent = alive[idx]
        if agent.alive:
            _resolve_movement(agent, actions[agent.id], state)

    # Loot collection
    for agent in state.alive_agents:
        _check_loot(agent, state)

    # Combat
    _resolve_all_combat(state, rng)

    # Bookkeeping
    for agent in state.alive_agents:
        agent.turns_survived += 1


def step_simulation(
    seed: int,
    map_width: int = 100,
    map_height: int = 100,
    num_agents: int = 100,
    max_turns: int = 500,
    zone_shrink_interval: int = 15,
):
    """Generator that yields GameState after each turn for real-time rendering."""
    rng = np.random.default_rng(seed)

    game_map = generate_map(rng, width=map_width, height=map_height)
    agents = generate_agents(rng, game_map, num_agents=num_agents)
    state = GameState(game_map=game_map, agents=agents)

    yield state  # initial state (turn 0)

    while state.alive_count > 1 and state.turn < max_turns:
        prev_kill_count = len(state.kill_events)
        prev_death_count = len(state.death_events)

        _run_turn(state, agents, game_map, rng, zone_shrink_interval)

        # Attach new events this turn for the viewer to consume
        state.new_kills = state.kill_events[prev_kill_count:]
        state.new_deaths = state.death_events[prev_death_count:]

        yield state

    yield state  # final state


def run_simulation(
    seed: int,
    map_width: int = 100,
    map_height: int = 100,
    num_agents: int = 100,
    max_turns: int = 500,
    zone_shrink_interval: int = 15,
) -> SimulationResult:
    """Run a single battle royale simulation to completion."""
    rng = np.random.default_rng(seed)

    game_map = generate_map(rng, width=map_width, height=map_height)
    agents = generate_agents(rng, game_map, num_agents=num_agents)
    state = GameState(game_map=game_map, agents=agents)

    while state.alive_count > 1 and state.turn < max_turns:
        _run_turn(state, agents, game_map, rng, zone_shrink_interval)

    # Determine winner
    survivors = state.alive_agents
    if survivors:
        # If multiple survive at max_turns, pick by kills then HP
        survivors.sort(key=lambda a: (-a.kills, -a.hp))
        winner = survivors[0]
    else:
        # Edge case: last agents killed each other simultaneously
        last_dead = state.death_order[-1] if state.death_order else 0
        winner = agents[last_dead]

    # Build placement (reverse death order: last to die = 2nd place, etc.)
    placement: dict[int, int] = {}
    placement[winner.id] = 1
    total = len(agents)
    for rank, aid in enumerate(reversed(state.death_order)):
        if aid != winner.id:
            placement[aid] = rank + 2
    # Any agent not yet placed
    for a in agents:
        if a.id not in placement:
            placement[a.id] = total

    summaries = []
    for a in agents:
        cause = "winner" if a.id == winner.id else "combat"
        for de in state.death_events:
            if de.agent_id == a.id:
                cause = de.cause
                break
        summaries.append(AgentSummary(
            agent_id=a.id,
            behavior=a.behavior,
            base_stats=a.base_stats,
            kills=a.kills,
            damage_dealt=a.damage_dealt,
            damage_taken=a.damage_taken,
            turns_survived=a.turns_survived,
            placement=placement[a.id],
            cause_of_death=cause,
        ))

    return SimulationResult(
        winner_id=winner.id,
        winner_behavior=winner.behavior,
        winner_stats=winner.base_stats,
        total_turns=state.turn,
        kill_events=state.kill_events,
        death_events=state.death_events,
        agent_summaries=summaries,
        map_width=map_width,
        map_height=map_height,
    )
