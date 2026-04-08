"""Agent dataclass, stat generation, and behavior trees."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.core.map import GameMap


class BehaviorType(Enum):
    HUNTER = "hunter"
    CAMPER = "camper"
    SCAVENGER = "scavenger"
    NOMAD = "nomad"


class ActionType(Enum):
    MOVE = "move"
    ATTACK = "attack"
    STAY = "stay"
    FLEE = "flee"
    COLLECT_LOOT = "collect_loot"


@dataclass(slots=True)
class Stats:
    aggression: int
    speed: int
    stealth: int
    accuracy: int
    health: int
    luck: int

    def to_array(self) -> np.ndarray:
        return np.array([
            self.aggression, self.speed, self.stealth,
            self.accuracy, self.health, self.luck,
        ], dtype=np.int32)

    @property
    def dominant_stat(self) -> str:
        names = ["aggression", "speed", "stealth", "accuracy", "health", "luck"]
        values = self.to_array()
        return names[int(np.argmax(values))]


@dataclass(slots=True)
class Buff:
    stat_name: str
    amount: int
    turns_remaining: int


@dataclass(slots=True)
class Action:
    type: ActionType
    dx: int = 0
    dy: int = 0
    target_id: int = -1


@dataclass
class Agent:
    id: int
    behavior: BehaviorType
    base_stats: Stats
    hp: int
    max_hp: int
    x: int
    y: int
    alive: bool = True
    kills: int = 0
    damage_dealt: int = 0
    damage_taken: int = 0
    turns_survived: int = 0
    loot_collected: int = 0
    active_buffs: list[Buff] = field(default_factory=list)
    weapon: object = None   # Weapon or None
    armor: object = None    # Armor or None
    team_id: int = -1       # -1 = solo, 0+ = team index
    downed: bool = False    # for squad mode: knocked but revivable

    def effective_stat(self, name: str) -> int:
        base = getattr(self.base_stats, name)
        bonus = sum(b.amount for b in self.active_buffs if b.stat_name == name)
        return min(base + bonus, 15)  # soft cap with buffs


def generate_stats(rng: np.random.Generator, total_points: int = 30) -> Stats:
    """Distribute total_points across 6 stats (each 0-10)."""
    stats = [0, 0, 0, 0, 0, 0]
    for _ in range(total_points):
        eligible = [i for i in range(6) if stats[i] < 10]
        stats[rng.choice(eligible)] += 1
    return Stats(*stats)


def generate_agents(
    rng: np.random.Generator,
    game_map: GameMap,
    num_agents: int = 100,
) -> list[Agent]:
    """Create agents with balanced behavior type distribution and random placement."""
    # Balanced assignment: 25 of each type
    behaviors = []
    per_type = num_agents // len(BehaviorType)
    for bt in BehaviorType:
        behaviors.extend([bt] * per_type)
    # Fill remainder randomly
    while len(behaviors) < num_agents:
        behaviors.append(rng.choice(list(BehaviorType)))
    rng.shuffle(behaviors)

    # Collect open positions
    occupied: set[tuple[int, int]] = set()
    agents: list[Agent] = []

    for i in range(num_agents):
        stats = generate_stats(rng)
        max_hp = 50 + stats.health * 10

        # Spawn in center 60% of the map for denser starting positions
        margin_x = game_map.width // 5
        margin_y = game_map.height // 5
        while True:
            ax = int(rng.integers(margin_x, game_map.width - margin_x))
            ay = int(rng.integers(margin_y, game_map.height - margin_y))
            if (ax, ay) not in game_map.obstacles and (ax, ay) not in occupied:
                break
        occupied.add((ax, ay))

        agents.append(Agent(
            id=i,
            behavior=behaviors[i],
            base_stats=stats,
            hp=max_hp,
            max_hp=max_hp,
            x=ax,
            y=ay,
        ))

    return agents


def generate_squads(
    rng: np.random.Generator,
    game_map: GameMap,
    num_agents: int = 100,
    squad_size: int = 4,
) -> list[Agent]:
    """Create agents organized into squads. Teammates spawn near each other."""
    num_squads = num_agents // squad_size
    agents: list[Agent] = []
    occupied: set[tuple[int, int]] = set()

    behaviors = list(BehaviorType)
    margin_x = game_map.width // 5
    margin_y = game_map.height // 5

    agent_id = 0
    for squad_id in range(num_squads):
        # Pick a spawn cluster center for this squad
        while True:
            cx = int(rng.integers(margin_x + 3, game_map.width - margin_x - 3))
            cy = int(rng.integers(margin_y + 3, game_map.height - margin_y - 3))
            if (cx, cy) not in game_map.obstacles:
                break

        squad_behavior = behaviors[squad_id % len(behaviors)]

        for _ in range(squad_size):
            stats = generate_stats(rng)
            max_hp = 50 + stats.health * 10

            # Spawn near squad center
            for _attempt in range(50):
                ax = cx + int(rng.integers(-3, 4))
                ay = cy + int(rng.integers(-3, 4))
                ax = max(margin_x, min(game_map.width - margin_x - 1, ax))
                ay = max(margin_y, min(game_map.height - margin_y - 1, ay))
                if (ax, ay) not in game_map.obstacles and (ax, ay) not in occupied:
                    break
            occupied.add((ax, ay))

            agents.append(Agent(
                id=agent_id,
                behavior=squad_behavior,
                base_stats=stats,
                hp=max_hp,
                max_hp=max_hp,
                x=ax,
                y=ay,
                team_id=squad_id,
            ))
            agent_id += 1

    # Fill remaining agents as solo
    while len(agents) < num_agents:
        stats = generate_stats(rng)
        max_hp = 50 + stats.health * 10
        while True:
            ax = int(rng.integers(margin_x, game_map.width - margin_x))
            ay = int(rng.integers(margin_y, game_map.height - margin_y))
            if (ax, ay) not in game_map.obstacles and (ax, ay) not in occupied:
                break
        occupied.add((ax, ay))
        agents.append(Agent(
            id=agent_id, behavior=rng.choice(behaviors),
            base_stats=stats, hp=max_hp, max_hp=max_hp, x=ax, y=ay, team_id=-1,
        ))
        agent_id += 1

    return agents


# ---------------------------------------------------------------------------
# Behavior trees
# ---------------------------------------------------------------------------

def _direction_toward(ax: int, ay: int, tx: int, ty: int) -> tuple[int, int]:
    """Return (dx, dy) unit step from (ax,ay) toward (tx,ty)."""
    dx = 0 if tx == ax else (1 if tx > ax else -1)
    dy = 0 if ty == ay else (1 if ty > ay else -1)
    return dx, dy


def _find_nearest_enemy(agent: Agent, agents: list[Agent], max_range: int) -> Agent | None:
    best = None
    best_dist = max_range + 1
    for other in agents:
        if other.id == agent.id or not other.alive:
            continue
        # Skip teammates
        if agent.team_id >= 0 and agent.team_id == other.team_id:
            continue
        dist = abs(other.x - agent.x) + abs(other.y - agent.y)
        if dist < best_dist:
            # Detection check: target stealth reduces visibility
            detection_range = max(1, max_range - other.effective_stat("stealth") // 2)
            if dist <= detection_range:
                best_dist = dist
                best = other
    return best


def _find_nearest_loot(agent: Agent, game_map: GameMap, max_range: int) -> tuple[int, int] | None:
    best = None
    best_dist = max_range + 1
    for loot in game_map.loot_items:
        if loot.collected:
            continue
        dist = abs(loot.x - agent.x) + abs(loot.y - agent.y)
        if dist < best_dist:
            best_dist = dist
            best = (loot.x, loot.y)
    return best


def _zone_center(game_map: GameMap) -> tuple[int, int]:
    cx = (game_map.zone_min_x + game_map.zone_max_x) // 2
    cy = (game_map.zone_min_y + game_map.zone_max_y) // 2
    return cx, cy


def _is_in_zone(x: int, y: int, game_map: GameMap) -> bool:
    return (game_map.zone_min_x <= x <= game_map.zone_max_x and
            game_map.zone_min_y <= y <= game_map.zone_max_y)


def _alive_count(agents: list[Agent]) -> int:
    return sum(1 for a in agents if a.alive)


def decide_action(
    agent: Agent,
    agents: list[Agent],
    game_map: GameMap,
    rng: np.random.Generator,
) -> Action:
    """Decide an agent's action based on its behavior type."""
    # Universal: if outside zone, move toward zone center
    if not _is_in_zone(agent.x, agent.y, game_map):
        cx, cy = _zone_center(game_map)
        dx, dy = _direction_toward(agent.x, agent.y, cx, cy)
        return Action(ActionType.MOVE, dx, dy)

    # Endgame: when few agents remain, everyone becomes a hunter
    alive = _alive_count(agents)
    if alive <= 20:
        return _hunter_decide(agent, agents, game_map, rng)

    if agent.behavior == BehaviorType.HUNTER:
        return _hunter_decide(agent, agents, game_map, rng)
    elif agent.behavior == BehaviorType.CAMPER:
        return _camper_decide(agent, agents, game_map, rng)
    elif agent.behavior == BehaviorType.SCAVENGER:
        return _scavenger_decide(agent, agents, game_map, rng)
    else:
        return _nomad_decide(agent, agents, game_map, rng)


def _hunter_decide(
    agent: Agent, agents: list[Agent], game_map: GameMap, rng: np.random.Generator,
) -> Action:
    nearest = _find_nearest_enemy(agent, agents, max_range=12)
    if nearest:
        dist = abs(nearest.x - agent.x) + abs(nearest.y - agent.y)
        if dist <= 1:
            # Disengage if very low HP and enemy is healthier
            if agent.hp < agent.max_hp * 0.2 and nearest.hp > agent.hp * 2:
                dx, dy = _direction_toward(agent.x, agent.y, nearest.x, nearest.y)
                return Action(ActionType.FLEE, -dx, -dy)
            return Action(ActionType.ATTACK, target_id=nearest.id)
        # Move toward enemy
        dx, dy = _direction_toward(agent.x, agent.y, nearest.x, nearest.y)
        return Action(ActionType.MOVE, dx, dy)
    # No enemies visible -> sweep the map
    cx, cy = _zone_center(game_map)
    dx, dy = _direction_toward(agent.x, agent.y, cx, cy)
    if dx == 0 and dy == 0:
        dx, dy = int(rng.integers(-1, 2)), int(rng.integers(-1, 2))
    return Action(ActionType.MOVE, dx, dy)


def _camper_decide(
    agent: Agent, agents: list[Agent], game_map: GameMap, rng: np.random.Generator,
) -> Action:
    nearest = _find_nearest_enemy(agent, agents, max_range=3)
    if nearest:
        dist = abs(nearest.x - agent.x) + abs(nearest.y - agent.y)
        if dist <= 1:
            # Fight or flee -- flee chance reduced when zone is small
            zone_size = max(1, (game_map.zone_max_x - game_map.zone_min_x))
            zone_factor = min(1.0, zone_size / 50.0)  # 1.0 at full size, ~0 when tiny
            flee_chance = (agent.effective_stat("stealth") * 0.06 + agent.effective_stat("speed") * 0.03) * zone_factor
            if rng.random() < flee_chance:
                dx, dy = _direction_toward(agent.x, agent.y, nearest.x, nearest.y)
                return Action(ActionType.FLEE, -dx, -dy)
            return Action(ActionType.ATTACK, target_id=nearest.id)

    # Stay near zone center if close to edge
    zone_margin_x = min(agent.x - game_map.zone_min_x, game_map.zone_max_x - agent.x)
    zone_margin_y = min(agent.y - game_map.zone_min_y, game_map.zone_max_y - agent.y)
    if min(zone_margin_x, zone_margin_y) < 5:
        cx, cy = _zone_center(game_map)
        dx, dy = _direction_toward(agent.x, agent.y, cx, cy)
        return Action(ActionType.MOVE, dx, dy)

    return Action(ActionType.STAY)


def _scavenger_decide(
    agent: Agent, agents: list[Agent], game_map: GameMap, rng: np.random.Generator,
) -> Action:
    # Prioritize loot
    loot_pos = _find_nearest_loot(agent, game_map, max_range=10)
    if loot_pos:
        dx, dy = _direction_toward(agent.x, agent.y, loot_pos[0], loot_pos[1])
        return Action(ActionType.MOVE, dx, dy)

    # Check for threats
    nearest = _find_nearest_enemy(agent, agents, max_range=4)
    if nearest:
        dist = abs(nearest.x - agent.x) + abs(nearest.y - agent.y)
        if dist <= 1:
            if agent.hp > agent.max_hp * 0.4:
                # Flee if healthy enough to run
                dx, dy = _direction_toward(agent.x, agent.y, nearest.x, nearest.y)
                return Action(ActionType.FLEE, -dx, -dy)
            return Action(ActionType.ATTACK, target_id=nearest.id)

    # Wander within zone
    dx, dy = int(rng.integers(-1, 2)), int(rng.integers(-1, 2))
    return Action(ActionType.MOVE, dx, dy)


def _nomad_decide(
    agent: Agent, agents: list[Agent], game_map: GameMap, rng: np.random.Generator,
) -> Action:
    # Fight if adjacent
    nearest = _find_nearest_enemy(agent, agents, max_range=2)
    if nearest:
        dist = abs(nearest.x - agent.x) + abs(nearest.y - agent.y)
        if dist <= 1:
            return Action(ActionType.ATTACK, target_id=nearest.id)

    # Move randomly
    dx, dy = int(rng.integers(-1, 2)), int(rng.integers(-1, 2))
    return Action(ActionType.MOVE, dx, dy)
