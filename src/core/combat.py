"""Combat resolution: stealth escape, initiative, hit/damage/crit formulas."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.core.agent import Agent
    from src.core.map import GameMap


def attempt_stealth_escape(
    defender: Agent,
    game_map: object | None,
    rng: np.random.Generator,
) -> bool:
    """Return True if defender escapes via stealth."""
    stealth = defender.effective_stat("stealth")
    # Tall grass bonus
    if game_map and hasattr(game_map, 'is_grass') and game_map.is_grass(defender.x, defender.y):
        stealth += 3
    escape_chance = stealth * 0.05 + defender.effective_stat("speed") * 0.02
    return bool(rng.random() < escape_chance)


def roll_initiative(
    a: Agent,
    b: Agent,
    rng: np.random.Generator,
) -> tuple[Agent, Agent]:
    """Return (first_striker, second_striker) based on initiative roll."""
    a_init = (a.effective_stat("speed")
              + a.effective_stat("aggression") * 0.5
              + rng.random() * a.effective_stat("luck"))
    b_init = (b.effective_stat("speed")
              + b.effective_stat("stealth") * 0.5
              + rng.random() * b.effective_stat("luck"))
    if a_init >= b_init:
        return a, b
    return b, a


def attack_roll(
    attacker: Agent,
    defender: Agent,
    rng: np.random.Generator,
    game_map: object | None = None,
) -> int:
    """Resolve a single attack. Return damage dealt (0 if miss)."""
    accuracy = attacker.effective_stat("accuracy")

    # Weapon accuracy bonus
    if attacker.weapon:
        accuracy += attacker.weapon.accuracy_bonus

    # High ground bonus
    if game_map and hasattr(game_map, 'is_high_ground') and game_map.is_high_ground(attacker.x, attacker.y):
        accuracy += 2

    hit_chance = (0.3 + accuracy * 0.06 - defender.effective_stat("speed") * 0.03)
    hit_chance = max(0.10, min(0.95, hit_chance))

    if rng.random() >= hit_chance:
        return 0  # miss

    base_damage = 8 + attacker.effective_stat("aggression") * 2

    # Weapon damage bonus
    if attacker.weapon:
        base_damage += attacker.weapon.damage_bonus

    # Combat experience: each prior kill adds 10% damage (up to 50%)
    kill_bonus = min(0.5, attacker.kills * 0.10)
    base_damage = int(base_damage * (1 + kill_bonus))

    # Crit check
    crit_chance = 0.05 + attacker.effective_stat("luck") * 0.03
    if rng.random() < crit_chance:
        base_damage = int(base_damage * 1.5)

    # Armor absorption
    if defender.armor and defender.armor.durability > 0:
        base_damage = defender.armor.absorb(base_damage)

    return max(1, base_damage)


def resolve_combat(
    attacker: Agent,
    defender: Agent,
    rng: np.random.Generator,
    game_map: object | None = None,
) -> dict:
    """Resolve one round of combat between two agents."""
    result = {
        "escaped": False,
        "first_id": attacker.id,
        "damage_to_defender": 0,
        "damage_to_attacker": 0,
        "defender_died": False,
        "attacker_died": False,
    }

    # Stealth escape attempt
    if attempt_stealth_escape(defender, game_map, rng):
        result["escaped"] = True
        return result

    # Initiative
    first, second = roll_initiative(attacker, defender, rng)
    result["first_id"] = first.id

    # First striker attacks
    dmg = attack_roll(first, second, rng, game_map)
    if first.id == attacker.id:
        result["damage_to_defender"] = dmg
    else:
        result["damage_to_attacker"] = dmg

    second.hp -= dmg
    first.damage_dealt += dmg
    second.damage_taken += dmg

    if second.hp <= 0:
        second.alive = False
        if second.id == defender.id:
            result["defender_died"] = True
        else:
            result["attacker_died"] = True
        first.kills += 1
        return result

    # Second striker counter-attacks
    dmg2 = attack_roll(second, first, rng, game_map)
    if second.id == defender.id:
        result["damage_to_attacker"] = dmg2
    else:
        result["damage_to_defender"] = dmg2

    first.hp -= dmg2
    second.damage_dealt += dmg2
    first.damage_taken += dmg2

    if first.hp <= 0:
        first.alive = False
        if first.id == attacker.id:
            result["attacker_died"] = True
        else:
            result["defender_died"] = True
        second.kills += 1

    return result
