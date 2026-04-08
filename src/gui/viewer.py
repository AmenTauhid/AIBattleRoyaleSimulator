"""Pygame-based real-time viewer for battle royale simulations."""

from __future__ import annotations

import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pygame
from pygame.locals import (
    QUIT, KEYDOWN, MOUSEBUTTONDOWN, K_SPACE, K_UP, K_DOWN, K_LEFT, K_RIGHT,
    K_s, K_r, K_v, K_l, K_ESCAPE, K_q,
)

from src.core.agent import BehaviorType
from src.core.simulation import step_simulation, GameState
from src.gui.colors import *

# Layout constants
GRID_SIZE = 700
PANEL_WIDTH = 280
WINDOW_WIDTH = GRID_SIZE + PANEL_WIDTH
WINDOW_HEIGHT = GRID_SIZE + 50  # extra for bottom bar
PANEL_X = GRID_SIZE

FONT_SIZE = 14
FONT_SIZE_LARGE = 18
FONT_SIZE_TITLE = 22

BEHAVIOR_LABELS = {
    BehaviorType.HUNTER: "Hunter",
    BehaviorType.CAMPER: "Camper",
    BehaviorType.SCAVENGER: "Scavenger",
    BehaviorType.NOMAD: "Nomad",
}


class Viewer:
    def __init__(self, seed: int = 42, map_size: int = 100,
                 num_agents: int = 100, fps: int = 60, squads: bool = False):
        self.seed = seed
        self.map_size = map_size
        self.num_agents = num_agents
        self.target_fps = fps
        self.squads = squads
        self.cell_size = GRID_SIZE / map_size

        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Battle Royale Simulator")
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("consolas", FONT_SIZE)
        self.font_large = pygame.font.SysFont("consolas", FONT_SIZE_LARGE)
        self.font_title = pygame.font.SysFont("consolas", FONT_SIZE_TITLE, bold=True)

        # Create surfaces for overlays
        self.danger_surface = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)

        self._reset()

    def _reset(self):
        """Start or restart the simulation."""
        self.sim_gen = step_simulation(
            self.seed, self.map_size, self.map_size, self.num_agents,
            squads=self.squads,
        )
        self.state: GameState = next(self.sim_gen)

        self.paused = True
        self.speed = 3  # turns per second
        self.last_turn_time = 0.0
        self.game_over = False
        self.winner_id = -1

        self.kill_feed: list[str] = []
        self.effects: list[tuple[int, int, float, tuple]] = []  # (x, y, timer, color)
        self.total_agents = self.num_agents
        self.selected_agent_id: int = -1  # click-to-follow
        self.show_vision = False          # toggle V key
        self.show_labels = False          # toggle L key

        # Live graph data: population per behavior type over time
        self.pop_history: dict[BehaviorType, list[int]] = {bt: [] for bt in BehaviorType}
        self.total_alive_history: list[int] = []

        # Pre-render static map elements
        self._render_static_map()

    def _render_static_map(self):
        """Pre-render obstacles and terrain onto a cached surface."""
        self.map_surface = pygame.Surface((GRID_SIZE, GRID_SIZE))
        self.map_surface.fill(GRID_BG)

        cs = self.cell_size
        gm = self.state.game_map

        # Terrain tiles
        for (wx, wy) in gm.water_tiles:
            rect = pygame.Rect(wx * cs, wy * cs, max(cs, 1), max(cs, 1))
            pygame.draw.rect(self.map_surface, WATER, rect)
        for (gx, gy) in gm.grass_tiles:
            rect = pygame.Rect(gx * cs, gy * cs, max(cs, 1), max(cs, 1))
            pygame.draw.rect(self.map_surface, TALL_GRASS, rect)
        for (hx, hy) in gm.high_ground_tiles:
            rect = pygame.Rect(hx * cs, hy * cs, max(cs, 1), max(cs, 1))
            pygame.draw.rect(self.map_surface, HIGH_GROUND, rect)

        # Obstacles on top
        for (ox, oy) in gm.obstacles:
            rect = pygame.Rect(ox * cs, oy * cs, max(cs, 1), max(cs, 1))
            pygame.draw.rect(self.map_surface, OBSTACLE, rect)

    def run(self):
        """Main loop."""
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                elif event.type == KEYDOWN:
                    running = self._handle_key(event.key)
                elif event.type == MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            # Advance simulation
            if not self.paused and not self.game_over:
                now = time.time()
                turn_interval = 1.0 / max(self.speed, 1)
                if now - self.last_turn_time >= turn_interval:
                    self._advance_turn()
                    self.last_turn_time = now

            # Render
            self._render()
            pygame.display.flip()
            self.clock.tick(self.target_fps)

        pygame.quit()

    def _handle_key(self, key) -> bool:
        """Handle keypress. Returns False to quit."""
        if key in (K_ESCAPE, K_q):
            return False
        elif key == K_SPACE:
            self.paused = not self.paused
        elif key == K_UP:
            self.speed = min(self.speed + 1, 30)
        elif key == K_DOWN:
            self.speed = max(self.speed - 1, 1)
        elif key == K_RIGHT:
            self.speed = min(self.speed + 5, 30)
        elif key == K_LEFT:
            self.speed = max(self.speed - 5, 1)
        elif key == K_s:
            if not self.game_over:
                self._advance_turn()
        elif key == K_r:
            self.seed += 1
            self._reset()
        elif key == K_v:
            self.show_vision = not self.show_vision
        elif key == K_l:
            self.show_labels = not self.show_labels
        return True

    def _handle_click(self, pos: tuple[int, int]):
        """Select/deselect agent by clicking on the grid."""
        mx, my = pos
        if mx >= GRID_SIZE:
            return  # clicked on panel
        cs = self.cell_size
        grid_x = int(mx / cs)
        grid_y = int(my / cs)

        # Find closest alive agent to click position
        best_id = -1
        best_dist = 3  # max click distance in tiles
        for agent in self.state.agents:
            if not agent.alive:
                continue
            dist = abs(agent.x - grid_x) + abs(agent.y - grid_y)
            if dist < best_dist:
                best_dist = dist
                best_id = agent.id

        if best_id == self.selected_agent_id:
            self.selected_agent_id = -1  # deselect on re-click
        else:
            self.selected_agent_id = best_id

    def _advance_turn(self):
        """Step the simulation forward one turn."""
        try:
            self.state = next(self.sim_gen)
        except StopIteration:
            self.game_over = True
            survivors = self.state.alive_agents
            if survivors:
                survivors.sort(key=lambda a: (-a.kills, -a.hp))
                self.winner_id = survivors[0].id
            return

        # Process new events
        new_kills = getattr(self.state, "new_kills", [])
        new_deaths = getattr(self.state, "new_deaths", [])

        for ke in new_kills:
            killer = self.state.agents[ke.killer_id]
            victim = self.state.agents[ke.victim_id]
            killer_label = f"{BEHAVIOR_LABELS[killer.behavior]} #{ke.killer_id}"
            victim_label = f"{BEHAVIOR_LABELS[victim.behavior]} #{ke.victim_id}"
            self.kill_feed.append(f"{killer_label} > {victim_label}")
            self.effects.append((ke.x, ke.y, 1.0, KILL_FLASH))

        for de in new_deaths:
            if de.cause == "zone":
                agent = self.state.agents[de.agent_id]
                label = f"{BEHAVIOR_LABELS[agent.behavior]} #{de.agent_id}"
                self.kill_feed.append(f"Zone > {label}")
                self.effects.append((de.x, de.y, 1.0, ZONE_BORDER))

        # Trim kill feed
        self.kill_feed = self.kill_feed[-12:]

        # Record population history for live graph
        for bt in BehaviorType:
            count = sum(1 for a in self.state.agents if a.alive and a.behavior == bt)
            self.pop_history[bt].append(count)
        self.total_alive_history.append(self.state.alive_count)

        # Check game over
        if self.state.alive_count <= 1:
            self.game_over = True
            survivors = self.state.alive_agents
            if survivors:
                self.winner_id = survivors[0].id

    def _render(self):
        """Render the full frame."""
        self.screen.fill(BACKGROUND)

        # Grid area
        self._render_grid()
        self._render_zone()
        self._render_loot()
        self._render_agents()
        self._render_effects()

        # Side panel
        self._render_panel()

        # Live population graph
        self._render_live_graph()

        # Bottom bar
        self._render_bottom_bar()

    def _render_grid(self):
        """Draw the map with obstacles."""
        self.screen.blit(self.map_surface, (0, 0))

    def _render_zone(self):
        """Draw the danger zone overlay and border."""
        gm = self.state.game_map
        cs = self.cell_size

        # Danger zone overlay
        self.danger_surface.fill((0, 0, 0, 0))

        # Draw danger tint outside zone
        zone_rect = pygame.Rect(
            gm.zone_min_x * cs, gm.zone_min_y * cs,
            (gm.zone_max_x - gm.zone_min_x + 1) * cs,
            (gm.zone_max_y - gm.zone_min_y + 1) * cs,
        )

        # Fill entire surface with danger color
        danger_alpha = min(60 + gm.zone_phase * 8, 120)
        self.danger_surface.fill((100, 20, 20, danger_alpha))
        # Cut out the safe zone (make it transparent)
        pygame.draw.rect(self.danger_surface, (0, 0, 0, 0), zone_rect)

        self.screen.blit(self.danger_surface, (0, 0))

        # Zone border
        border_rect = pygame.Rect(
            gm.zone_min_x * cs, gm.zone_min_y * cs,
            (gm.zone_max_x - gm.zone_min_x + 1) * cs,
            (gm.zone_max_y - gm.zone_min_y + 1) * cs,
        )
        pygame.draw.rect(self.screen, ZONE_BORDER, border_rect, 2)

    def _render_loot(self):
        """Draw loot, weapons, armor, and supply drops."""
        cs = self.cell_size
        loot_r = max(1, cs / 4)
        gm = self.state.game_map

        # Stat buff loot
        for loot in gm.loot_items:
            if not loot.collected:
                cx = loot.x * cs + cs / 2
                cy = loot.y * cs + cs / 2
                pygame.draw.circle(self.screen, LOOT, (cx, cy), loot_r)

        # Ground weapons (small purple diamond)
        for wx, wy, weapon in gm.ground_weapons:
            cx = wx * cs + cs / 2
            cy = wy * cs + cs / 2
            r = max(1, cs / 3)
            points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
            pygame.draw.polygon(self.screen, WEAPON_GROUND, points)

        # Ground armor (small blue square)
        for ax, ay, armor in gm.ground_armor:
            r = max(1, cs / 3)
            rect = pygame.Rect(ax * cs + cs / 2 - r, ay * cs + cs / 2 - r, r * 2, r * 2)
            pygame.draw.rect(self.screen, ARMOR_GROUND, rect)

        # Supply drops (pulsing magenta circle)
        for drop in gm.supply_drops:
            if not drop.collected:
                cx = drop.x * cs + cs / 2
                cy = drop.y * cs + cs / 2
                pulse = max(2, cs * 0.8)
                pygame.draw.circle(self.screen, SUPPLY_DROP, (cx, cy), pulse)
                pygame.draw.circle(self.screen, SUPPLY_DROP_GLOW, (cx, cy), pulse, 1)

    def _render_agents(self):
        """Draw alive agents as colored circles with HP bars, vision, labels."""
        cs = self.cell_size
        agent_r = max(2, cs / 2.5)

        for agent in self.state.agents:
            if not agent.alive:
                continue

            cx = agent.x * cs + cs / 2
            cy = agent.y * cs + cs / 2
            color = AGENT_COLORS[agent.behavior]
            is_selected = agent.id == self.selected_agent_id

            # Vision range circle (toggle with V)
            if self.show_vision or is_selected:
                vision_r = max(1, 6 - agent.effective_stat("stealth") // 2)
                pixel_r = vision_r * cs
                vision_surf = pygame.Surface((pixel_r * 2, pixel_r * 2), pygame.SRCALPHA)
                alpha = 40 if not is_selected else 60
                pygame.draw.circle(vision_surf, (*color, alpha),
                                   (pixel_r, pixel_r), pixel_r)
                self.screen.blit(vision_surf, (cx - pixel_r, cy - pixel_r))

            # Agent circle
            pygame.draw.circle(self.screen, color, (cx, cy), agent_r)

            # Selection highlight
            if is_selected:
                pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), agent_r + 3, 2)
                pygame.draw.circle(self.screen, color, (cx, cy), agent_r + 5, 1)

            # Winner highlight
            elif self.game_over and agent.id == self.winner_id:
                pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), agent_r + 2, 2)

            # Weapon indicator (small dot)
            if agent.weapon:
                tier_colors = {1: (180, 180, 180), 2: (100, 200, 255), 3: (255, 150, 255)}
                wc = tier_colors.get(agent.weapon.tier, (180, 180, 180))
                pygame.draw.circle(self.screen, wc, (cx + agent_r, cy - agent_r), max(1, cs / 6))

            # Behavior label (toggle with L)
            if self.show_labels:
                label_text = BEHAVIOR_LABELS[agent.behavior][0]  # First letter
                lbl = self.font.render(label_text, True, color)
                self.screen.blit(lbl, (cx - 3, cy + agent_r + 1))

            # HP bar
            hp_frac = agent.hp / agent.max_hp if agent.max_hp > 0 else 0
            bar_w = cs * 0.9
            bar_h = max(1, cs / 5)
            bar_x = cx - bar_w / 2
            bar_y = cy - agent_r - bar_h - 1

            # Background
            pygame.draw.rect(self.screen, HP_BAR_BG,
                             (bar_x, bar_y, bar_w, bar_h))
            # Fill
            if hp_frac > 0.5:
                hp_color = HP_BAR_HIGH
            elif hp_frac > 0.25:
                hp_color = HP_BAR_MID
            else:
                hp_color = HP_BAR_LOW
            pygame.draw.rect(self.screen, hp_color,
                             (bar_x, bar_y, bar_w * hp_frac, bar_h))

    def _render_effects(self):
        """Draw combat flash effects with decay."""
        cs = self.cell_size
        dt = 1.0 / max(self.target_fps, 1)
        remaining = []

        for (x, y, timer, color) in self.effects:
            alpha = int(255 * timer)
            radius = max(3, cs * timer * 1.5)
            cx = x * cs + cs / 2
            cy = y * cs + cs / 2

            effect_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(effect_surf, (*color, alpha),
                               (radius, radius), radius)
            self.screen.blit(effect_surf, (cx - radius, cy - radius))

            new_timer = timer - dt * 3  # decay over ~0.3 seconds
            if new_timer > 0:
                remaining.append((x, y, new_timer, color))

        self.effects = remaining

    def _render_panel(self):
        """Draw the stats and info side panel."""
        panel_rect = pygame.Rect(PANEL_X, 0, PANEL_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, PANEL_BG, panel_rect)
        pygame.draw.line(self.screen, PANEL_BORDER,
                         (PANEL_X, 0), (PANEL_X, WINDOW_HEIGHT), 2)

        x = PANEL_X + 15
        y = 15

        # Title
        title = self.font_title.render("BATTLE ROYALE", True, TITLE_COLOR)
        self.screen.blit(title, (x, y))
        y += 35

        # Game stats
        y = self._panel_stat(x, y, "Turn", str(self.state.turn))
        y = self._panel_stat(x, y, "Alive", f"{self.state.alive_count}/{self.total_agents}")
        y = self._panel_stat(x, y, "Zone Phase", str(self.state.game_map.zone_phase))
        y = self._panel_stat(x, y, "Zone DMG", f"{self.state.game_map.zone_damage}/turn")
        y = self._panel_stat(x, y, "Speed", f"{self.speed} t/s")
        y += 10

        # Status
        if self.game_over:
            status = self.font_large.render("GAME OVER", True, GAMEOVER_COLOR)
            self.screen.blit(status, (x, y))
            y += 25
            if self.winner_id >= 0:
                winner = self.state.agents[self.winner_id]
                w_label = f"Winner: {BEHAVIOR_LABELS[winner.behavior]} #{self.winner_id}"
                wtext = self.font.render(w_label, True, TEXT_HIGHLIGHT)
                self.screen.blit(wtext, (x, y))
                y += 18
                kills_text = self.font.render(f"  Kills: {winner.kills}", True, TEXT_COLOR)
                self.screen.blit(kills_text, (x, y))
                y += 18
                hp_text = self.font.render(f"  HP: {winner.hp}/{winner.max_hp}", True, TEXT_COLOR)
                self.screen.blit(hp_text, (x, y))
                y += 25
        elif self.paused:
            status = self.font_large.render("PAUSED", True, PAUSED_COLOR)
            self.screen.blit(status, (x, y))
            y += 25
        else:
            y += 25

        # Selected agent details
        if self.selected_agent_id >= 0:
            agent = self.state.agents[self.selected_agent_id]
            pygame.draw.line(self.screen, PANEL_BORDER, (x, y), (PANEL_X + PANEL_WIDTH - 15, y))
            y += 8
            color = AGENT_COLORS[agent.behavior]
            header = f"AGENT #{agent.id}"
            self.screen.blit(self.font_large.render(header, True, color), (x, y))
            y += 22
            status_txt = "ALIVE" if agent.alive else "DEAD"
            self.screen.blit(self.font.render(f"{BEHAVIOR_LABELS[agent.behavior]} - {status_txt}", True, TEXT_COLOR), (x, y))
            y += 18
            self.screen.blit(self.font.render(f"HP: {agent.hp}/{agent.max_hp}  Kills: {agent.kills}", True, TEXT_COLOR), (x, y))
            y += 18
            self.screen.blit(self.font.render(f"Pos: ({agent.x}, {agent.y})", True, TEXT_DIM), (x, y))
            y += 18
            # Stats
            stats_str = f"AGG:{agent.base_stats.aggression} SPD:{agent.base_stats.speed} STL:{agent.base_stats.stealth}"
            self.screen.blit(self.font.render(stats_str, True, TEXT_DIM), (x, y))
            y += 16
            stats_str2 = f"ACC:{agent.base_stats.accuracy} HP:{agent.base_stats.health} LCK:{agent.base_stats.luck}"
            self.screen.blit(self.font.render(stats_str2, True, TEXT_DIM), (x, y))
            y += 18
            # Equipment
            w_name = agent.weapon.name if agent.weapon else "None"
            a_name = f"{agent.armor.name} ({agent.armor.durability})" if agent.armor else "None"
            self.screen.blit(self.font.render(f"Weapon: {w_name}", True, TEXT_DIM), (x, y))
            y += 16
            self.screen.blit(self.font.render(f"Armor:  {a_name}", True, TEXT_DIM), (x, y))
            y += 16

        # Separator
        pygame.draw.line(self.screen, PANEL_BORDER, (x, y), (PANEL_X + PANEL_WIDTH - 15, y))
        y += 10

        # Legend
        legend_title = self.font.render("AGENTS", True, TITLE_COLOR)
        self.screen.blit(legend_title, (x, y))
        y += 22

        for bt in BehaviorType:
            color = AGENT_COLORS[bt]
            count = sum(1 for a in self.state.agents if a.alive and a.behavior == bt)
            pygame.draw.circle(self.screen, color, (x + 6, y + 6), 5)
            label = f"{BEHAVIOR_LABELS[bt]}: {count}"
            text = self.font.render(label, True, TEXT_COLOR)
            self.screen.blit(text, (x + 18, y))
            y += 20
        y += 5

        # Top killers
        pygame.draw.line(self.screen, PANEL_BORDER, (x, y), (PANEL_X + PANEL_WIDTH - 15, y))
        y += 10
        kf_title = self.font.render("TOP KILLERS", True, TITLE_COLOR)
        self.screen.blit(kf_title, (x, y))
        y += 22

        top_killers = sorted(
            [a for a in self.state.agents if a.kills > 0],
            key=lambda a: -a.kills,
        )[:5]
        for a in top_killers:
            color = AGENT_COLORS[a.behavior]
            label = f"#{a.id} {BEHAVIOR_LABELS[a.behavior]}: {a.kills} kills"
            alive_marker = "" if a.alive else " [DEAD]"
            text = self.font.render(label + alive_marker, True, color if a.alive else TEXT_DIM)
            self.screen.blit(text, (x, y))
            y += 18
        y += 5

        # Kill feed
        pygame.draw.line(self.screen, PANEL_BORDER, (x, y), (PANEL_X + PANEL_WIDTH - 15, y))
        y += 10
        kf_title = self.font.render("KILL FEED", True, TITLE_COLOR)
        self.screen.blit(kf_title, (x, y))
        y += 22

        # Show most recent events
        max_feed = min(len(self.kill_feed), (WINDOW_HEIGHT - y - 60) // 16)
        for entry in self.kill_feed[-max_feed:]:
            text = self.font.render(entry, True, TEXT_DIM)
            self.screen.blit(text, (x, y))
            y += 16

    def _render_live_graph(self):
        """Draw a live population-over-time graph at the bottom of the panel."""
        if len(self.total_alive_history) < 2:
            return

        graph_w = PANEL_WIDTH - 30
        graph_h = 100
        graph_x = PANEL_X + 15
        graph_y = WINDOW_HEIGHT - 50 - graph_h - 10

        # Background
        pygame.draw.rect(self.screen, (15, 15, 25),
                         (graph_x, graph_y, graph_w, graph_h))
        pygame.draw.rect(self.screen, PANEL_BORDER,
                         (graph_x, graph_y, graph_w, graph_h), 1)

        # Label
        lbl = self.font.render("POPULATION", True, TEXT_DIM)
        self.screen.blit(lbl, (graph_x, graph_y - 16))

        n = len(self.total_alive_history)
        max_val = self.total_agents

        # Draw line for each behavior type
        for bt in BehaviorType:
            history = self.pop_history[bt]
            if len(history) < 2:
                continue
            color = AGENT_COLORS[bt]
            points = []
            for i, val in enumerate(history):
                px = graph_x + (i / max(n - 1, 1)) * graph_w
                py = graph_y + graph_h - (val / max(max_val, 1)) * graph_h
                points.append((px, py))
            if len(points) >= 2:
                pygame.draw.lines(self.screen, color, False, points, 1)

        # Total alive line (white, thicker)
        points = []
        for i, val in enumerate(self.total_alive_history):
            px = graph_x + (i / max(n - 1, 1)) * graph_w
            py = graph_y + graph_h - (val / max(max_val, 1)) * graph_h
            points.append((px, py))
        if len(points) >= 2:
            pygame.draw.lines(self.screen, TEXT_COLOR, False, points, 2)

    def _render_bottom_bar(self):
        """Draw controls help at the bottom."""
        bar_y = GRID_SIZE
        bar_rect = pygame.Rect(0, bar_y, GRID_SIZE, 50)
        pygame.draw.rect(self.screen, PANEL_BG, bar_rect)
        pygame.draw.line(self.screen, PANEL_BORDER, (0, bar_y), (GRID_SIZE, bar_y))

        controls = "SPACE: Play/Pause | S: Step | UP/DN: Speed | V: Vision | L: Labels | R: Restart"
        text = self.font.render(controls, True, TEXT_DIM)
        self.screen.blit(text, (15, bar_y + 8))

        # Seed info
        seed_text = self.font.render(f"Seed: {self.seed}", True, TEXT_DIM)
        self.screen.blit(seed_text, (15, bar_y + 28))

    def _panel_stat(self, x: int, y: int, label: str, value: str) -> int:
        """Render a label: value stat line. Returns new y."""
        lbl = self.font.render(f"{label}:", True, TEXT_DIM)
        val = self.font.render(value, True, TEXT_COLOR)
        self.screen.blit(lbl, (x, y))
        self.screen.blit(val, (x + 110, y))
        return y + 20


def run_viewer(seed: int = 42, map_size: int = 100,
               num_agents: int = 100, fps: int = 60,
               squads: bool = False) -> None:
    """Launch the Pygame viewer."""
    viewer = Viewer(seed=seed, map_size=map_size, num_agents=num_agents,
                    fps=fps, squads=squads)
    viewer.run()
