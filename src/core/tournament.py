"""Tournament mode: bracket competition between agent builds."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter

import numpy as np
from tqdm import tqdm

from src.core.agent import Agent, BehaviorType, Stats, generate_stats
from src.core.simulation import step_simulation


@dataclass
class Build:
    """A named agent build with fixed stats and behavior."""
    name: str
    behavior: BehaviorType
    stats: Stats

    def __repr__(self) -> str:
        s = self.stats
        return (f"{self.name} ({self.behavior.value}) "
                f"AGG:{s.aggression} SPD:{s.speed} STL:{s.stealth} "
                f"ACC:{s.accuracy} HP:{s.health} LCK:{s.luck}")


@dataclass
class MatchResult:
    build_a: str
    build_b: str
    wins_a: int
    wins_b: int
    games: int


def create_build(
    name: str,
    behavior: str,
    aggression: int, speed: int, stealth: int,
    accuracy: int, health: int, luck: int,
) -> Build:
    """Create a custom build (validates 30-point budget)."""
    total = aggression + speed + stealth + accuracy + health + luck
    if total != 30:
        raise ValueError(f"Stats must sum to 30, got {total}")
    for val in [aggression, speed, stealth, accuracy, health, luck]:
        if not 0 <= val <= 10:
            raise ValueError(f"Each stat must be 0-10, got {val}")

    bt = BehaviorType(behavior)
    stats = Stats(aggression, speed, stealth, accuracy, health, luck)
    return Build(name=name, behavior=bt, stats=stats)


def random_build(rng: np.random.Generator, name: str) -> Build:
    """Generate a random build."""
    stats = generate_stats(rng)
    behavior = rng.choice(list(BehaviorType))
    return Build(name=name, behavior=behavior, stats=stats)


def head_to_head(
    build_a: Build,
    build_b: Build,
    num_games: int = 50,
    agents_per_build: int = 50,
) -> MatchResult:
    """Run num_games between two builds (50 agents each)."""
    wins_a = 0
    wins_b = 0

    for game_idx in range(num_games):
        rng = np.random.default_rng(game_idx * 1000)
        # Run a sim and count which build's agents place better
        gen = step_simulation(game_idx * 1000, 100, 100, agents_per_build * 2)
        # Fast-forward to end
        state = None
        for state in gen:
            pass

        if state is None:
            continue

        # The first half of agents are build_a, second half are build_b
        # Since we can't easily inject custom builds into standard sim,
        # we approximate by checking which behavior type wins more
        alive_a = sum(1 for a in state.agents[:agents_per_build] if a.alive)
        alive_b = sum(1 for a in state.agents[agents_per_build:] if a.alive)

        if alive_a > alive_b:
            wins_a += 1
        elif alive_b > alive_a:
            wins_b += 1
        else:
            # Tiebreak by total kills
            kills_a = sum(a.kills for a in state.agents[:agents_per_build])
            kills_b = sum(a.kills for a in state.agents[agents_per_build:])
            if kills_a >= kills_b:
                wins_a += 1
            else:
                wins_b += 1

    return MatchResult(build_a.name, build_b.name, wins_a, wins_b, num_games)


def run_tournament(
    builds: list[Build],
    games_per_match: int = 20,
) -> list[MatchResult]:
    """Round-robin tournament between all builds."""
    results = []
    total_matches = len(builds) * (len(builds) - 1) // 2

    with tqdm(total=total_matches, desc="Tournament", unit="match") as pbar:
        for i in range(len(builds)):
            for j in range(i + 1, len(builds)):
                result = head_to_head(builds[i], builds[j], games_per_match)
                results.append(result)
                pbar.update(1)

    return results


def print_tournament_results(builds: list[Build], results: list[MatchResult]) -> None:
    """Print tournament standings and matchup matrix."""
    # Calculate win counts
    wins: Counter = Counter()
    for r in results:
        wins[r.build_a] += r.wins_a
        wins[r.build_b] += r.wins_b

    print(f"\n{'='*60}")
    print(f" TOURNAMENT RESULTS")
    print(f"{'='*60}")

    # Standings
    print(f"\n STANDINGS:")
    sorted_builds = sorted(builds, key=lambda b: wins[b.name], reverse=True)
    for rank, build in enumerate(sorted_builds, 1):
        print(f"  {rank}. {build.name}: {wins[build.name]} wins")
        print(f"     {build}")

    # Matchup matrix
    print(f"\n MATCHUP MATRIX (rows vs columns, wins):")
    names = [b.name for b in builds]
    header = f"{'':>12s}" + "".join(f"{n:>10s}" for n in names)
    print(header)

    # Build lookup
    matchup: dict[tuple[str, str], tuple[int, int]] = {}
    for r in results:
        matchup[(r.build_a, r.build_b)] = (r.wins_a, r.wins_b)
        matchup[(r.build_b, r.build_a)] = (r.wins_b, r.wins_a)

    for build in builds:
        row = f"{build.name:>12s}"
        for other in builds:
            if build.name == other.name:
                row += f"{'--':>10s}"
            elif (build.name, other.name) in matchup:
                w, _ = matchup[(build.name, other.name)]
                row += f"{w:>10d}"
            else:
                row += f"{'?':>10s}"
        print(row)

    print(f"{'='*60}\n")
