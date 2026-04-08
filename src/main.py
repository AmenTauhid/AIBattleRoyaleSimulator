"""CLI entry point for the Battle Royale Simulator."""

from __future__ import annotations

import argparse
import os
import sys
import time

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.batch import run_batch
from src.analytics import generate_report, print_summary, _aggregate


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Battle Royale Simulator - run AI agent simulations and analyze results",
    )
    parser.add_argument(
        "--sims", type=int, default=1000,
        help="Number of simulations to run (default: 1000)",
    )
    parser.add_argument(
        "--output", type=str, default="results",
        help="Output directory for charts and report (default: results/)",
    )
    parser.add_argument(
        "--map-size", type=int, default=100,
        help="Map width and height (default: 100)",
    )
    parser.add_argument(
        "--workers", type=int, default=None,
        help="Number of parallel workers (default: auto)",
    )
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
