"""Grid map, zone shrinking, terrain, loot, obstacles, and supply drops."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


class TileType:
    EMPTY = 0
    OBSTACLE = 1
    LOOT = 2
    WATER = 3       # slows movement by 50%
    TALL_GRASS = 4  # +3 stealth while on tile
    HIGH_GROUND = 5 # +2 accuracy while on tile


TERRAIN_TILES = {TileType.WATER, TileType.TALL_GRASS, TileType.HIGH_GROUND}


@dataclass
class LootItem:
    x: int
    y: int
    stat_name: str
    amount: int
    duration: int
    collected: bool = False


@dataclass
class Weapon:
    name: str
    damage_bonus: int     # added to base aggression damage
    accuracy_bonus: int   # added to hit chance calc
    range_bonus: int      # extends combat trigger range for holder
    tier: int             # 1=common, 2=rare, 3=legendary

    def __repr__(self) -> str:
        return f"Weapon({self.name}, T{self.tier})"


@dataclass
class Armor:
    name: str
    damage_reduction: float  # fraction of damage absorbed (0.0-0.6)
    durability: int          # hits remaining before breaking
    tier: int

    def absorb(self, damage: int) -> int:
        """Return damage after armor absorption. Degrades durability."""
        if self.durability <= 0:
            return damage
        absorbed = int(damage * self.damage_reduction)
        self.durability -= 1
        return damage - absorbed

    def __repr__(self) -> str:
        return f"Armor({self.name}, T{self.tier}, {self.durability}hp)"


@dataclass
class SupplyDrop:
    x: int
    y: int
    turn_spawned: int
    weapon: Weapon | None = None
    armor: Armor | None = None
    collected: bool = False


# Weapon and armor templates
WEAPONS = {
    1: [
        Weapon("Pistol", damage_bonus=3, accuracy_bonus=1, range_bonus=0, tier=1),
        Weapon("Shotgun", damage_bonus=5, accuracy_bonus=-1, range_bonus=0, tier=1),
        Weapon("SMG", damage_bonus=4, accuracy_bonus=0, range_bonus=0, tier=1),
    ],
    2: [
        Weapon("Assault Rifle", damage_bonus=7, accuracy_bonus=2, range_bonus=1, tier=2),
        Weapon("Sniper Rifle", damage_bonus=10, accuracy_bonus=4, range_bonus=2, tier=2),
        Weapon("LMG", damage_bonus=8, accuracy_bonus=1, range_bonus=0, tier=2),
    ],
    3: [
        Weapon("Legendary AR", damage_bonus=12, accuracy_bonus=3, range_bonus=1, tier=3),
        Weapon("Legendary Sniper", damage_bonus=15, accuracy_bonus=5, range_bonus=3, tier=3),
        Weapon("Rocket Launcher", damage_bonus=20, accuracy_bonus=-2, range_bonus=0, tier=3),
    ],
}

ARMORS = {
    1: Armor("Light Vest", damage_reduction=0.15, durability=5, tier=1),
    2: Armor("Medium Vest", damage_reduction=0.30, durability=8, tier=2),
    3: Armor("Heavy Vest", damage_reduction=0.45, durability=12, tier=3),
}


def random_weapon(rng: np.random.Generator, tier: int = 1) -> Weapon:
    """Create a copy of a random weapon at the given tier."""
    template = rng.choice(WEAPONS[tier])
    return Weapon(template.name, template.damage_bonus, template.accuracy_bonus,
                  template.range_bonus, template.tier)


def random_armor(rng: np.random.Generator, tier: int = 1) -> Armor:
    """Create a copy of armor at the given tier."""
    template = ARMORS[tier]
    return Armor(template.name, template.damage_reduction, template.durability, template.tier)


@dataclass
class GameMap:
    width: int = 100
    height: int = 100
    grid: np.ndarray = field(default=None, repr=False)
    obstacles: set[tuple[int, int]] = field(default_factory=set)
    water_tiles: set[tuple[int, int]] = field(default_factory=set)
    grass_tiles: set[tuple[int, int]] = field(default_factory=set)
    high_ground_tiles: set[tuple[int, int]] = field(default_factory=set)
    loot_items: list[LootItem] = field(default_factory=list)
    ground_weapons: list[tuple[int, int, Weapon]] = field(default_factory=list)
    ground_armor: list[tuple[int, int, Armor]] = field(default_factory=list)
    supply_drops: list[SupplyDrop] = field(default_factory=list)
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

    def tile_at(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return int(self.grid[y, x])
        return TileType.OBSTACLE

    def is_water(self, x: int, y: int) -> bool:
        return (x, y) in self.water_tiles

    def is_grass(self, x: int, y: int) -> bool:
        return (x, y) in self.grass_tiles

    def is_high_ground(self, x: int, y: int) -> bool:
        return (x, y) in self.high_ground_tiles


def _place_terrain_patch(
    game_map: GameMap, rng: np.random.Generator,
    tile_type: int, tile_set: set, num_seeds: int, patch_size: int,
) -> None:
    """Place clusters of a terrain type using random walk from seeds."""
    for _ in range(num_seeds):
        sx = int(rng.integers(5, game_map.width - 5))
        sy = int(rng.integers(5, game_map.height - 5))
        size = int(rng.integers(patch_size // 2, patch_size + 1))

        ox, oy = sx, sy
        for _ in range(size):
            if (0 <= ox < game_map.width and 0 <= oy < game_map.height
                    and (ox, oy) not in game_map.obstacles):
                tile_set.add((ox, oy))
                game_map.grid[oy, ox] = tile_type
            ox += int(rng.integers(-1, 2))
            oy += int(rng.integers(-1, 2))
            ox = max(0, min(game_map.width - 1, ox))
            oy = max(0, min(game_map.height - 1, oy))


def generate_map(
    rng: np.random.Generator,
    width: int = 100,
    height: int = 100,
    num_obstacle_seeds: int = 30,
    num_loot: int = 100,
) -> GameMap:
    """Generate a map with obstacles, terrain, loot, and ground weapons."""
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
            ox += int(rng.integers(-1, 2))
            oy += int(rng.integers(-1, 2))
            ox = max(0, min(width - 1, ox))
            oy = max(0, min(height - 1, oy))

    # Generate terrain patches
    _place_terrain_patch(game_map, rng, TileType.WATER, game_map.water_tiles, 8, 12)
    _place_terrain_patch(game_map, rng, TileType.TALL_GRASS, game_map.grass_tiles, 15, 8)
    _place_terrain_patch(game_map, rng, TileType.HIGH_GROUND, game_map.high_ground_tiles, 10, 6)

    # Generate loot
    stat_names = ["aggression", "speed", "stealth", "accuracy", "health", "luck"]

    for _ in range(num_loot):
        while True:
            lx = int(rng.integers(0, width))
            ly = int(rng.integers(0, height))
            if (lx, ly) not in game_map.obstacles:
                break

        dist_from_center = abs(lx - cx) + abs(ly - cy)
        if dist_from_center > (width + height) // 4:
            amount = int(rng.choice([1, 2, 3], p=[0.3, 0.4, 0.3]))
        else:
            amount = int(rng.choice([1, 2, 3], p=[0.5, 0.35, 0.15]))

        game_map.loot_items.append(LootItem(
            x=lx, y=ly,
            stat_name=rng.choice(stat_names),
            amount=amount,
            duration=int(rng.integers(10, 21)),
        ))
        # Don't overwrite terrain tiles in grid for loot
        if game_map.grid[ly, lx] == TileType.EMPTY:
            game_map.grid[ly, lx] = TileType.LOOT

    # Scatter ground weapons (tier 1 mostly, some tier 2)
    num_weapons = width * height // 200  # ~50 on 100x100
    for _ in range(num_weapons):
        while True:
            wx = int(rng.integers(0, width))
            wy = int(rng.integers(0, height))
            if (wx, wy) not in game_map.obstacles:
                break
        tier = 1 if rng.random() < 0.75 else 2
        game_map.ground_weapons.append((wx, wy, random_weapon(rng, tier)))

    # Scatter ground armor (less common)
    num_armor = width * height // 400  # ~25 on 100x100
    for _ in range(num_armor):
        while True:
            ax = int(rng.integers(0, width))
            ay = int(rng.integers(0, height))
            if (ax, ay) not in game_map.obstacles:
                break
        tier = 1 if rng.random() < 0.7 else 2
        game_map.ground_armor.append((ax, ay, random_armor(rng, tier)))

    return game_map


def spawn_supply_drop(game_map: GameMap, rng: np.random.Generator, turn: int) -> SupplyDrop:
    """Spawn a supply drop with tier 3 loot inside the current zone."""
    while True:
        x = int(rng.integers(game_map.zone_min_x, game_map.zone_max_x + 1))
        y = int(rng.integers(game_map.zone_min_y, game_map.zone_max_y + 1))
        if (x, y) not in game_map.obstacles:
            break

    drop = SupplyDrop(x=x, y=y, turn_spawned=turn)
    # Always has a legendary weapon, sometimes also has armor
    drop.weapon = random_weapon(rng, tier=3)
    if rng.random() < 0.5:
        drop.armor = random_armor(rng, tier=3)
    game_map.supply_drops.append(drop)
    return drop


def shrink_zone(game_map: GameMap) -> None:
    """Shrink the safe zone by one phase."""
    game_map.zone_phase += 1
    shrink = 7 * game_map.zone_phase
    half_w = game_map.width // 2
    half_h = game_map.height // 2

    game_map.zone_min_x = max(0, game_map.zone_center_x - max(2, half_w - shrink))
    game_map.zone_max_x = min(game_map.width - 1, game_map.zone_center_x + max(2, half_w - shrink))
    game_map.zone_min_y = max(0, game_map.zone_center_y - max(2, half_h - shrink))
    game_map.zone_max_y = min(game_map.height - 1, game_map.zone_center_y + max(2, half_h - shrink))

    game_map.zone_damage = 8 + game_map.zone_phase * 5
