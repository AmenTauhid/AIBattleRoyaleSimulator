"""Replay database: catalog, save, and browse recorded replays."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from src.core.replay import load_replay, record_replay


DB_FILE = "replay_catalog.json"


@dataclass
class ReplayEntry:
    filename: str
    seed: int
    total_turns: int
    winner_behavior: str
    winner_kills: int
    timestamp: str
    tags: list[str]


def _catalog_path(replay_dir: str) -> str:
    return os.path.join(replay_dir, DB_FILE)


def load_catalog(replay_dir: str) -> list[ReplayEntry]:
    """Load the replay catalog from disk."""
    path = _catalog_path(replay_dir)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [ReplayEntry(**entry) for entry in data]


def save_catalog(replay_dir: str, catalog: list[ReplayEntry]) -> None:
    """Save the replay catalog to disk."""
    os.makedirs(replay_dir, exist_ok=True)
    path = _catalog_path(replay_dir)
    data = [
        {
            "filename": e.filename,
            "seed": e.seed,
            "total_turns": e.total_turns,
            "winner_behavior": e.winner_behavior,
            "winner_kills": e.winner_kills,
            "timestamp": e.timestamp,
            "tags": e.tags,
        }
        for e in catalog
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def record_and_catalog(
    seed: int,
    replay_dir: str = "replays",
    tags: list[str] | None = None,
    map_width: int = 100,
    map_height: int = 100,
    num_agents: int = 100,
) -> ReplayEntry:
    """Record a replay and add it to the catalog."""
    os.makedirs(replay_dir, exist_ok=True)
    filename = f"replay_seed{seed}_{int(time.time())}.json.gz"
    filepath = os.path.join(replay_dir, filename)

    record_replay(seed, filepath, map_width, map_height, num_agents)

    # Read back to get metadata
    data = load_replay(filepath)
    frames = data["frames"]
    last_frame = frames[-1] if frames else {}

    # Find winner
    winner_behavior = "unknown"
    winner_kills = 0
    for agent in last_frame.get("agents", []):
        if agent.get("alive", False):
            winner_behavior = agent.get("behavior", "unknown")
            winner_kills = agent.get("kills", 0)
            break

    entry = ReplayEntry(
        filename=filename,
        seed=seed,
        total_turns=data.get("total_turns", 0),
        winner_behavior=winner_behavior,
        winner_kills=winner_kills,
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        tags=tags or [],
    )

    catalog = load_catalog(replay_dir)
    catalog.append(entry)
    save_catalog(replay_dir, catalog)

    return entry


def list_replays(replay_dir: str = "replays") -> None:
    """Print all replays in the catalog."""
    catalog = load_catalog(replay_dir)
    if not catalog:
        print("No replays recorded yet.")
        return

    print(f"\n{'='*70}")
    print(f" REPLAY DATABASE ({len(catalog)} replays)")
    print(f"{'='*70}")
    for i, entry in enumerate(catalog):
        tags_str = f" [{', '.join(entry.tags)}]" if entry.tags else ""
        print(f"  {i + 1}. {entry.filename}")
        print(f"     Seed: {entry.seed} | Turns: {entry.total_turns} | "
              f"Winner: {entry.winner_behavior} ({entry.winner_kills} kills)")
        print(f"     Recorded: {entry.timestamp}{tags_str}")
    print(f"{'='*70}\n")
