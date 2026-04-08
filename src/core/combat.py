"""Combat resolution: stealth escape, initiative, hit/damage/crit formulas."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.core.agent import Agent


def attempt_stealth_escape(
    defender: Agent,
    rng: np.random.Generator,
) -> bool:
    """Return True if defender escapes via stealth."""
    escape_chance = defender.effective_stat("stealth") * 0.05 + defender.effective_stat("speed") * 0.02
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
) -> int:
    """Resolve a single attack. Return damage dealt (0 if miss)."""
    hit_chance = (0.3
                  + attacker.effective_stat("accuracy") * 0.06
                  - defender.effective_stat("speed") * 0.03)
    hit_chance = max(0.10, min(0.95, hit_chance))

    if rng.random() >= hit_chance:
        return 0  # miss

    base_damage = 8 + attacker.effective_stat("aggression") * 2

    # Combat experience: each prior kill adds 10% damage (up to 50%)
    kill_bonus = min(0.5, attacker.kills * 0.10)
    base_damage = int(base_damage * (1 + kill_bonus))

    # Crit check
    crit_chance = 0.05 + attacker.effective_stat("luck") * 0.03
    if rng.random() < crit_chance:
        base_damage = int(base_damage * 1.5)

    return base_damage


def resolve_combat(
    attacker: Agent,
    defender: Agent,
    rng: np.random.Generator,
) -> dict:
    """Resolve one round of combat between two agents.

    Returns a dict with:
        escaped: bool - defender escaped via stealth
        first_id: int - who struck first
        damage_to_defender: int
        damage_to_attacker: int
        defender_died: bool
        attacker_died: bool
    """
    result = {
        "escaped": False,
        "first_id": attacker.id,
        "damage_to_defender": 0,
        "damage_to_attacker": 0,
        "defender_died": False,
        "attacker_died": False,
    }

    # Stealth escape attempt
    if attempt_stealth_escape(defender, rng):
        result["escaped"] = True
        return result

    # Initiative
    first, second = roll_initiative(attacker, defender, rng)
    result["first_id"] = first.id

    # First striker attacks
    dmg = attack_roll(first, second, rng)
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
    dmg2 = attack_roll(second, first, rng)
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
