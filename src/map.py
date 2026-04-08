"""Grid map, zone shrinking, obstacle clusters, and loot placement."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


class TileType:
    EMPTY = 0
    OBSTACLE = 1
    LOOT = 2


@dataclass
class LootItem:
    x: int
    y: int
    stat_name: str
    amount: int
    duration: int
    collected: bool = False


@dataclass
class GameMap:
    width: int = 100
    height: int = 100
    grid: np.ndarray = field(default=None, repr=False)
    obstacles: set[tuple[int, int]] = field(default_factory=set)
    loot_items: list[LootItem] = field(default_factory=list)
    zone_min_x: int = 0
    zone_min_y: int = 0
    zone_max_x: int = 99
    zone_max_y: int = 99
    zone_center_x: int = 50
    zone_center_y: int = 50
    zone_damage: int = 5
    zone_phase: int = 0

    def __post_init__(self) -> None:
        if self.grid is None:
            self.grid = np.zeros((self.height, self.width), dtype=np.int8)

    def in_zone(self, x: int, y: int) -> bool:
        return (self.zone_min_x <= x <= self.zone_max_x and
                self.zone_min_y <= y <= self.zone_max_y)

    def is_walkable(self, x: int, y: int) -> bool:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return False
        return (x, y) not in self.obstacles


def generate_map(
    rng: np.random.Generator,
    width: int = 100,
    height: int = 100,
    num_obstacle_seeds: int = 30,
    num_loot: int = 100,
) -> GameMap:
    """Generate a map with clustered obstacles and scattered loot."""
    game_map = GameMap(width=width, height=height)
    game_map.zone_max_x = width - 1
    game_map.zone_max_y = height - 1

    # Random zone center (inner 40% of map)
    margin = width // 5
    game_map.zone_center_x = int(rng.integers(margin, width - margin))
    game_map.zone_center_y = int(rng.integers(margin, height - margin))

    # Generate clustered obstacles
    center_clear_radius = 5
    cx, cy = width // 2, height // 2

    for _ in range(num_obstacle_seeds):
        sx = int(rng.integers(0, width))
        sy = int(rng.integers(0, height))
        cluster_size = int(rng.integers(3, 8))

        ox, oy = sx, sy
        for _ in range(cluster_size):
            if (0 <= ox < width and 0 <= oy < height and
                    abs(ox - cx) + abs(oy - cy) > center_clear_radius):
                game_map.obstacles.add((ox, oy))
                game_map.grid[oy, ox] = TileType.OBSTACLE
            # Random walk
            ox += int(rng.integers(-1, 2))
            oy += int(rng.integers(-1, 2))
            ox = max(0, min(width - 1, ox))
            oy = max(0, min(height - 1, oy))

    # Generate loot
    stat_names = ["aggression", "speed", "stealth", "accuracy", "health", "luck"]

    for _ in range(num_loot):
        while True:
            lx = int(rng.integers(0, width))
            ly = int(rng.integers(0, height))
            if (lx, ly) not in game_map.obstacles:
                break

        # Edge loot is slightly better
        dist_from_center = abs(lx - cx) + abs(ly - cy)
        if dist_from_center > (width + height) // 4:
            amount = int(rng.choice([1, 2, 3], p=[0.3, 0.4, 0.3]))
        else:
            amount = int(rng.choice([1, 2, 3], p=[0.5, 0.35, 0.15]))

        game_map.loot_items.append(LootItem(
            x=lx,
            y=ly,
            stat_name=rng.choice(stat_names),
            amount=amount,
            duration=int(rng.integers(10, 21)),
        ))
        game_map.grid[ly, lx] = TileType.LOOT

    return game_map


def shrink_zone(game_map: GameMap) -> None:
    """Shrink the safe zone by one phase. Call every N turns."""
    game_map.zone_phase += 1
    # Aggressive shrink: 7 tiles per phase so agents converge faster
    shrink = 7 * game_map.zone_phase
    half_w = game_map.width // 2
    half_h = game_map.height // 2

    game_map.zone_min_x = max(0, game_map.zone_center_x - max(2, half_w - shrink))
    game_map.zone_max_x = min(game_map.width - 1, game_map.zone_center_x + max(2, half_w - shrink))
    game_map.zone_min_y = max(0, game_map.zone_center_y - max(2, half_h - shrink))
    game_map.zone_max_y = min(game_map.height - 1, game_map.zone_center_y + max(2, half_h - shrink))

    # Escalating damage -- punishes zone campers harder
    game_map.zone_damage = 8 + game_map.zone_phase * 5
