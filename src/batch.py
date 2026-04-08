"""Parallel batch runner for simulations."""

from __future__ import annotations

import os
from multiprocessing import Pool
from functools import partial

from tqdm import tqdm

from src.simulation import SimulationResult, run_simulation


def _run_sim_wrapper(seed: int, map_width: int, map_height: int) -> SimulationResult:
    """Wrapper for multiprocessing (top-level function for pickling)."""
    return run_simulation(seed, map_width=map_width, map_height=map_height)


def run_batch(
    num_sims: int,
    map_width: int = 100,
    map_height: int = 100,
    num_workers: int | None = None,
) -> list[SimulationResult]:
    """Run num_sims simulations in parallel with a progress bar."""
    if num_workers is None:
        num_workers = min(os.cpu_count() or 4, 8)

    worker_fn = partial(_run_sim_wrapper, map_width=map_width, map_height=map_height)

    seeds = list(range(num_sims))

    if num_sims <= 4 or num_workers <= 1:
        # Run sequentially for small batches or debugging
        results = []
        for seed in tqdm(seeds, desc="Simulating", unit="sim"):
            results.append(worker_fn(seed))
        return results

    with Pool(processes=num_workers) as pool:
        results = list(tqdm(
            pool.imap_unordered(worker_fn, seeds),
            total=num_sims,
            desc="Simulating",
            unit="sim",
        ))

    return results
