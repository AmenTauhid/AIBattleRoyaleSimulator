"""Replay recording and playback: save/load game state per turn."""

from __future__ import annotations

import json
import gzip
import os
from dataclasses import asdict
from typing import Any

from src.core.agent import Agent, BehaviorType, Stats, Buff
from src.core.simulation import GameState, KillEvent, DeathEvent, step_simulation
from src.core.map import GameMap, LootItem, SupplyDrop, Weapon, Armor


def _serialize_agent(agent: Agent) -> dict:
    return {
        "id": agent.id,
        "behavior": agent.behavior.value,
        "base_stats": [agent.base_stats.aggression, agent.base_stats.speed,
                        agent.base_stats.stealth, agent.base_stats.accuracy,
                        agent.base_stats.health, agent.base_stats.luck],
        "hp": agent.hp,
        "max_hp": agent.max_hp,
        "x": agent.x,
        "y": agent.y,
        "alive": agent.alive,
        "kills": agent.kills,
        "weapon": agent.weapon.name if agent.weapon else None,
        "weapon_tier": agent.weapon.tier if agent.weapon else 0,
        "armor": agent.armor.name if agent.armor else None,
        "armor_dur": agent.armor.durability if agent.armor else 0,
    }


def _serialize_frame(state: GameState) -> dict:
    """Serialize a single frame (turn) of game state."""
    new_kills = getattr(state, "new_kills", [])
    new_deaths = getattr(state, "new_deaths", [])

    return {
        "turn": state.turn,
        "alive_count": state.alive_count,
        "zone": [state.game_map.zone_min_x, state.game_map.zone_min_y,
                 state.game_map.zone_max_x, state.game_map.zone_max_y],
        "zone_phase": state.game_map.zone_phase,
        "zone_damage": state.game_map.zone_damage,
        "agents": [_serialize_agent(a) for a in state.agents],
        "kills": [{"turn": k.turn, "killer": k.killer_id, "victim": k.victim_id,
                    "x": k.x, "y": k.y, "cause": k.cause} for k in new_kills],
        "deaths": [{"turn": d.turn, "agent": d.agent_id,
                     "x": d.x, "y": d.y, "cause": d.cause} for d in new_deaths],
        "supply_drops": [{"x": s.x, "y": s.y, "collected": s.collected}
                         for s in state.game_map.supply_drops],
    }


def _serialize_map(game_map: GameMap) -> dict:
    """Serialize the static map data (once per replay)."""
    return {
        "width": game_map.width,
        "height": game_map.height,
        "obstacles": list(game_map.obstacles),
        "water": list(game_map.water_tiles),
        "grass": list(game_map.grass_tiles),
        "high_ground": list(game_map.high_ground_tiles),
        "loot": [{"x": l.x, "y": l.y, "stat": l.stat_name, "amount": l.amount}
                 for l in game_map.loot_items],
    }


def record_replay(
    seed: int,
    output_path: str,
    map_width: int = 100,
    map_height: int = 100,
    num_agents: int = 100,
) -> str:
    """Run a simulation and save the replay to a compressed file."""
    gen = step_simulation(seed, map_width, map_height, num_agents)

    # First frame gives us the initial state + map
    state = next(gen)
    map_data = _serialize_map(state.game_map)
    frames = [_serialize_frame(state)]

    for state in gen:
        frames.append(_serialize_frame(state))

    replay = {
        "version": 1,
        "seed": seed,
        "map": map_data,
        "frames": frames,
        "total_turns": frames[-1]["turn"],
    }

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    with gzip.open(output_path, "wt", encoding="utf-8") as f:
        json.dump(replay, f)

    return output_path


def load_replay(path: str) -> dict:
    """Load a compressed replay file."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)
