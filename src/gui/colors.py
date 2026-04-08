"""Color constants for the Pygame viewer."""

from src.core.agent import BehaviorType

# Background and grid
BACKGROUND = (20, 20, 30)
GRID_BG = (28, 28, 38)
OBSTACLE = (55, 55, 65)
LOOT = (255, 215, 0)
LOOT_DIM = (180, 150, 0)
WATER = (30, 80, 140)
TALL_GRASS = (40, 90, 35)
HIGH_GROUND = (120, 100, 60)
WEAPON_GROUND = (200, 120, 255)
ARMOR_GROUND = (100, 180, 255)
SUPPLY_DROP = (255, 100, 255)
SUPPLY_DROP_GLOW = (255, 150, 255)

# Zone
ZONE_BORDER = (255, 50, 50)
ZONE_DANGER = (100, 20, 20)
ZONE_SAFE_TINT = (25, 45, 25)

# Agents by behavior type
AGENT_COLORS = {
    BehaviorType.HUNTER: (230, 60, 60),
    BehaviorType.CAMPER: (60, 130, 230),
    BehaviorType.SCAVENGER: (60, 200, 80),
    BehaviorType.NOMAD: (240, 200, 50),
    BehaviorType.ADAPTIVE: (200, 100, 255),
}

AGENT_COLORS_DIM = {
    BehaviorType.HUNTER: (150, 40, 40),
    BehaviorType.CAMPER: (40, 85, 150),
    BehaviorType.SCAVENGER: (40, 130, 55),
    BehaviorType.NOMAD: (160, 130, 35),
    BehaviorType.ADAPTIVE: (130, 65, 170),
}

# HP bars
HP_BAR_BG = (40, 40, 40)
HP_BAR_HIGH = (50, 200, 50)
HP_BAR_MID = (220, 180, 30)
HP_BAR_LOW = (220, 50, 50)

# Combat effects
COMBAT_FLASH = (255, 255, 255)
KILL_FLASH = (255, 80, 80)

# Side panel
PANEL_BG = (22, 22, 32)
PANEL_BORDER = (50, 50, 65)
TEXT_COLOR = (220, 220, 220)
TEXT_DIM = (120, 120, 135)
TEXT_HIGHLIGHT = (255, 255, 100)
TITLE_COLOR = (180, 180, 200)

# Status colors
PAUSED_COLOR = (255, 200, 50)
GAMEOVER_COLOR = (100, 255, 100)
