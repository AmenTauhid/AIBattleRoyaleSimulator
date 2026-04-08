"""Genetic algorithm engine for evolving optimal agent builds."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from tqdm import tqdm

from src.agent import Agent, BehaviorType, Buff, Stats
from src.combat import resolve_combat
from src.map import GameMap, generate_map, shrink_zone
from src.simulation import (
    GameState,
    KillEvent,
    DeathEvent,
    SimulationResult,
    AgentSummary,
    _kill_agent,
    _apply_zone_damage,
    _tick_buffs,
    _resolve_movement,
    _check_loot,
    _resolve_all_combat,
)
from src.agent import decide_action, ActionType


STAT_NAMES = ["aggression", "speed", "stealth", "accuracy", "health", "luck"]
BEHAVIORS = list(BehaviorType)


@dataclass
class Genome:
    """An evolvable agent blueprint."""
    stat_weights: np.ndarray  # 6 floats, normalized to distribute 30 points
    behavior_idx: int         # index into BEHAVIORS
    fitness: float = 0.0
    generation: int = 0

    @property
    def behavior(self) -> BehaviorType:
        return BEHAVIORS[self.behavior_idx]

    def to_stats(self) -> Stats:
        """Convert weights to a concrete 30-point stat allocation."""
        weights = np.maximum(self.stat_weights, 0.01)
        normalized = weights / weights.sum()
        raw = normalized * 30

        # Round while preserving total of 30
        stats = np.floor(raw).astype(int)
        remainder = 30 - stats.sum()
        # Distribute remainder to stats with largest fractional parts
        fractions = raw - stats
        for _ in range(int(remainder)):
            idx = np.argmax(fractions)
            stats[idx] += 1
            fractions[idx] = -1  # don't pick again

        # Clamp to 0-10
        stats = np.clip(stats, 0, 10)
        # If clamping reduced total, redistribute
        while stats.sum() < 30:
            eligible = np.where(stats < 10)[0]
            if len(eligible) == 0:
                break
            idx = eligible[np.argmax(fractions[eligible])]
            stats[idx] += 1
        while stats.sum() > 30:
            eligible = np.where(stats > 0)[0]
            if len(eligible) == 0:
                break
            idx = eligible[np.argmin(stats[eligible])]
            stats[idx] -= 1

        return Stats(*stats.tolist())

    def copy(self) -> Genome:
        return Genome(
            stat_weights=self.stat_weights.copy(),
            behavior_idx=self.behavior_idx,
            fitness=0.0,
            generation=self.generation,
        )


@dataclass
class GenerationLog:
    """Stats tracked per generation."""
    generation: int
    best_fitness: float
    avg_fitness: float
    best_genome: Genome
    avg_stats: np.ndarray        # average stat weights across population
    behavior_counts: list[int]   # count of each behavior type


@dataclass
class EvolutionResult:
    """Full result of an evolution run."""
    logs: list[GenerationLog]
    best_genome: Genome
    final_population: list[Genome]
    total_generations: int


def random_genome(rng: np.random.Generator, generation: int = 0) -> Genome:
    """Create a random genome."""
    weights = rng.random(6) * 10
    behavior_idx = int(rng.integers(0, len(BEHAVIORS)))
    return Genome(stat_weights=weights, behavior_idx=behavior_idx, generation=generation)


def crossover(parent_a: Genome, parent_b: Genome, rng: np.random.Generator) -> Genome:
    """Blend two parent genomes."""
    # Blend stat weights with random interpolation per stat
    alpha = rng.random(6)
    child_weights = parent_a.stat_weights * alpha + parent_b.stat_weights * (1 - alpha)

    # Behavior from random parent
    behavior_idx = parent_a.behavior_idx if rng.random() < 0.5 else parent_b.behavior_idx

    return Genome(stat_weights=child_weights, behavior_idx=behavior_idx)


def mutate(genome: Genome, rng: np.random.Generator, mutation_rate: float = 0.15) -> Genome:
    """Apply random mutations to a genome."""
    g = genome.copy()

    # Perturb each stat weight independently
    for i in range(6):
        if rng.random() < mutation_rate:
            g.stat_weights[i] += rng.normal(0, 1.5)
            g.stat_weights[i] = max(0.01, g.stat_weights[i])

    # Occasionally flip behavior type
    if rng.random() < mutation_rate * 0.5:
        g.behavior_idx = int(rng.integers(0, len(BEHAVIORS)))

    return g


def _genome_to_agent(genome: Genome, agent_id: int, x: int, y: int) -> Agent:
    """Create an Agent from a Genome."""
    stats = genome.to_stats()
    max_hp = 50 + stats.health * 10
    return Agent(
        id=agent_id,
        behavior=genome.behavior,
        base_stats=stats,
        hp=max_hp,
        max_hp=max_hp,
        x=x,
        y=y,
    )


def evaluate_population(
    population: list[Genome],
    rng: np.random.Generator,
    games_per_eval: int = 3,
    map_width: int = 100,
    map_height: int = 100,
) -> None:
    """Run games and assign fitness scores to each genome."""
    # Reset fitness
    for g in population:
        g.fitness = 0.0

    num_agents = len(population)

    for game_idx in range(games_per_eval):
        seed = int(rng.integers(0, 2**31))
        game_rng = np.random.default_rng(seed)

        game_map = generate_map(game_rng, width=map_width, height=map_height)

        # Place agents from genomes
        occupied: set[tuple[int, int]] = set()
        agents: list[Agent] = []
        margin_x = map_width // 5
        margin_y = map_height // 5

        for i, genome in enumerate(population):
            while True:
                ax = int(game_rng.integers(margin_x, map_width - margin_x))
                ay = int(game_rng.integers(margin_y, map_height - margin_y))
                if (ax, ay) not in game_map.obstacles and (ax, ay) not in occupied:
                    break
            occupied.add((ax, ay))
            agents.append(_genome_to_agent(genome, i, ax, ay))

        state = GameState(game_map=game_map, agents=agents)

        # Run simulation
        max_turns = 500
        zone_shrink_interval = 15

        while state.alive_count > 1 and state.turn < max_turns:
            state.turn += 1

            if state.turn % zone_shrink_interval == 0:
                shrink_zone(state.game_map)

            _apply_zone_damage(state)
            if state.alive_count <= 1:
                break

            _tick_buffs(agents)

            actions = {}
            alive = state.alive_agents
            for agent in alive:
                actions[agent.id] = decide_action(agent, agents, game_map, game_rng)

            move_order = list(range(len(alive)))
            game_rng.shuffle(move_order)
            for idx in move_order:
                agent = alive[idx]
                if agent.alive:
                    _resolve_movement(agent, actions[agent.id], state)

            for agent in state.alive_agents:
                _check_loot(agent, state)

            # Combat with kill rewards
            from src.simulation import _find_combat_pairs
            pairs = _find_combat_pairs(state)
            game_rng.shuffle(pairs)
            for a, b in pairs:
                if not a.alive or not b.alive:
                    continue
                result = resolve_combat(a, b, game_rng)
                if result["escaped"]:
                    for ddx, ddy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = b.x + ddx, b.y + ddy
                        if state.game_map.is_walkable(nx, ny):
                            b.x, b.y = nx, ny
                            break
                    continue
                if result["defender_died"]:
                    _kill_agent(b, state, cause="combat", killer_id=a.id)
                    a.hp = min(a.max_hp, a.hp + a.max_hp // 4)
                if result["attacker_died"]:
                    _kill_agent(a, state, cause="combat", killer_id=b.id)
                    b.hp = min(b.max_hp, b.hp + b.max_hp // 4)

            for agent in state.alive_agents:
                agent.turns_survived += 1

        # Score genomes based on placement
        # Build placement order
        survivors = state.alive_agents
        survivors.sort(key=lambda a: (-a.kills, -a.hp))

        placement: dict[int, int] = {}
        if survivors:
            placement[survivors[0].id] = 1
            for i, s in enumerate(survivors[1:], 2):
                placement[s.id] = i

        for rank, aid in enumerate(reversed(state.death_order)):
            if aid not in placement:
                placement[aid] = len(survivors) + rank + 1

        for a in agents:
            if a.id not in placement:
                placement[a.id] = num_agents

        # Fitness: placement-based (winner gets 100, last gets 1) + kill bonus
        for a in agents:
            p = placement[a.id]
            placement_score = (num_agents - p + 1) / num_agents * 100
            kill_bonus = a.kills * 5
            population[a.id].fitness += placement_score + kill_bonus

    # Average across games
    for g in population:
        g.fitness /= games_per_eval


def evolve(
    num_generations: int = 200,
    population_size: int = 100,
    elite_count: int = 10,
    games_per_eval: int = 3,
    mutation_rate: float = 0.15,
    map_width: int = 100,
    map_height: int = 100,
    seed: int = 42,
) -> EvolutionResult:
    """Run the full genetic algorithm evolution loop."""
    rng = np.random.default_rng(seed)

    # Initialize random population
    population = [random_genome(rng, generation=0) for _ in range(population_size)]

    logs: list[GenerationLog] = []
    best_ever = None

    for gen in tqdm(range(num_generations), desc="Evolving", unit="gen"):
        # Evaluate
        evaluate_population(population, rng, games_per_eval, map_width, map_height)

        # Sort by fitness (descending)
        population.sort(key=lambda g: g.fitness, reverse=True)

        # Log this generation
        fitnesses = [g.fitness for g in population]
        avg_stats = np.mean([g.stat_weights for g in population], axis=0)
        behavior_counts = [
            sum(1 for g in population if g.behavior_idx == i)
            for i in range(len(BEHAVIORS))
        ]

        best = population[0]
        log = GenerationLog(
            generation=gen,
            best_fitness=best.fitness,
            avg_fitness=float(np.mean(fitnesses)),
            best_genome=best.copy(),
            avg_stats=avg_stats.copy(),
            behavior_counts=behavior_counts,
        )
        log.best_genome.generation = gen
        logs.append(log)

        if best_ever is None or best.fitness > best_ever.fitness:
            best_ever = best.copy()
            best_ever.generation = gen

        # Selection + reproduction
        # Keep elites unchanged
        next_gen = [g.copy() for g in population[:elite_count]]

        # Fill rest via tournament selection + crossover + mutation
        while len(next_gen) < population_size:
            # Tournament selection (pick best of 3 random)
            candidates_a = rng.choice(population_size, size=3, replace=False)
            parent_a = population[min(candidates_a)]

            candidates_b = rng.choice(population_size, size=3, replace=False)
            parent_b = population[min(candidates_b)]

            child = crossover(parent_a, parent_b, rng)
            child = mutate(child, rng, mutation_rate)
            child.generation = gen + 1
            next_gen.append(child)

        population = next_gen

    # Final evaluation
    evaluate_population(population, rng, games_per_eval, map_width, map_height)
    population.sort(key=lambda g: g.fitness, reverse=True)

    if population[0].fitness > best_ever.fitness:
        best_ever = population[0].copy()

    return EvolutionResult(
        logs=logs,
        best_genome=best_ever,
        final_population=population,
        total_generations=num_generations,
    )
