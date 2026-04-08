"""CLI entry point for the Battle Royale Simulator."""

from __future__ import annotations

import argparse
import os
import sys
import time

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analysis.batch import run_batch
from src.analysis.analytics import generate_report, print_summary, _aggregate


def run_simulate(args: argparse.Namespace) -> None:
    """Run batch simulations and generate analysis."""
    os.makedirs(args.output, exist_ok=True)

    print(f"Battle Royale Simulator")
    print(f"  Simulations: {args.sims}")
    print(f"  Map size: {args.map_size}x{args.map_size}")
    print(f"  Output: {args.output}/")
    print()

    start = time.time()
    results = run_batch(
        num_sims=args.sims,
        map_width=args.map_size,
        map_height=args.map_size,
        num_workers=args.workers,
    )
    elapsed = time.time() - start
    print(f"\nCompleted {args.sims} simulations in {elapsed:.1f}s")

    print("Generating analysis...")
    generate_report(results, args.output)

    data = _aggregate(results)
    print_summary(data)

    print(f"Charts saved to: {os.path.join(args.output, 'charts')}/")
    print(f"Full report: {os.path.join(args.output, 'meta_report.md')}")


def run_evolve(args: argparse.Namespace) -> None:
    """Run genetic algorithm evolution."""
    from src.evolution.genetic import evolve
    from src.evolution.ga_analytics import generate_evolution_report, print_evolution_summary

    os.makedirs(args.output, exist_ok=True)

    print(f"Battle Royale Simulator - Evolution Mode")
    print(f"  Generations: {args.generations}")
    print(f"  Population: {args.population}")
    print(f"  Games per eval: {args.games_per_eval}")
    print(f"  Map size: {args.map_size}x{args.map_size}")
    print(f"  Output: {args.output}/")
    print()

    start = time.time()
    result = evolve(
        num_generations=args.generations,
        population_size=args.population,
        games_per_eval=args.games_per_eval,
        mutation_rate=args.mutation_rate,
        map_width=args.map_size,
        map_height=args.map_size,
        seed=args.seed,
    )
    elapsed = time.time() - start
    print(f"\nEvolution completed in {elapsed:.1f}s")

    print("Generating evolution report...")
    generate_evolution_report(result, args.output)
    print_evolution_summary(result)

    print(f"Charts saved to: {os.path.join(args.output, 'charts')}/")
    print(f"Full report: {os.path.join(args.output, 'evolution_report.md')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Battle Royale Simulator - run simulations or evolve optimal builds",
    )
    subparsers = parser.add_subparsers(dest="command", help="Mode to run")

    # Simulate subcommand
    sim_parser = subparsers.add_parser("simulate", help="Run batch simulations and analyze")
    sim_parser.add_argument("--sims", type=int, default=1000, help="Number of simulations (default: 1000)")
    sim_parser.add_argument("--output", type=str, default="results", help="Output directory (default: results/)")
    sim_parser.add_argument("--map-size", type=int, default=100, help="Map size (default: 100)")
    sim_parser.add_argument("--workers", type=int, default=None, help="Parallel workers (default: auto)")

    # Evolve subcommand
    evo_parser = subparsers.add_parser("evolve", help="Evolve optimal agent builds via genetic algorithm")
    evo_parser.add_argument("--generations", type=int, default=200, help="Number of generations (default: 200)")
    evo_parser.add_argument("--population", type=int, default=100, help="Population size (default: 100)")
    evo_parser.add_argument("--games-per-eval", type=int, default=3, help="Games per fitness eval (default: 3)")
    evo_parser.add_argument("--mutation-rate", type=float, default=0.15, help="Mutation rate (default: 0.15)")
    evo_parser.add_argument("--output", type=str, default="evolution_results", help="Output directory")
    evo_parser.add_argument("--map-size", type=int, default=100, help="Map size (default: 100)")
    evo_parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")

    args = parser.parse_args()

    if args.command == "simulate":
        run_simulate(args)
    elif args.command == "evolve":
        run_evolve(args)
    else:
        # Default: simulate mode with legacy flat args
        parser.print_help()
        print("\nExamples:")
        print("  python src/main.py simulate --sims 1000 --output results/")
        print("  python src/main.py evolve --generations 200 --output evolution_results/")


if __name__ == "__main__":
    main()
