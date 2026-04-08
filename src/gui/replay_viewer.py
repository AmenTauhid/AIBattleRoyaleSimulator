"""Pygame replay viewer with timeline scrubbing."""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pygame
from pygame.locals import (
    QUIT, KEYDOWN, MOUSEBUTTONDOWN, K_SPACE, K_UP, K_DOWN, K_LEFT, K_RIGHT,
    K_s, K_ESCAPE, K_q, K_HOME, K_END,
)

from src.core.replay import load_replay
from src.core.agent import BehaviorType
from src.gui.colors import *

GRID_SIZE = 700
PANEL_WIDTH = 280
WINDOW_WIDTH = GRID_SIZE + PANEL_WIDTH
WINDOW_HEIGHT = GRID_SIZE + 80  # extra for timeline + controls
PANEL_X = GRID_SIZE
TIMELINE_Y = GRID_SIZE
TIMELINE_H = 30
CONTROLS_Y = TIMELINE_Y + TIMELINE_H

BEHAVIOR_MAP = {b.value: b for b in BehaviorType}
BEHAVIOR_LABELS = {
    BehaviorType.HUNTER: "Hunter",
    BehaviorType.CAMPER: "Camper",
    BehaviorType.SCAVENGER: "Scavenger",
    BehaviorType.NOMAD: "Nomad",
}


class ReplayViewer:
    def __init__(self, replay_data: dict, fps: int = 60):
        self.replay = replay_data
        self.frames = replay_data["frames"]
        self.map_data = replay_data["map"]
        self.total_frames = len(self.frames)
        self.current_frame = 0
        self.target_fps = fps

        self.map_width = self.map_data["width"]
        self.map_height = self.map_data["height"]
        self.cell_size = GRID_SIZE / self.map_width

        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(f"Battle Royale Replay (Seed: {replay_data.get('seed', '?')})")
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("consolas", 14)
        self.font_large = pygame.font.SysFont("consolas", 18)
        self.font_title = pygame.font.SysFont("consolas", 22, bold=True)

        self.paused = True
        self.speed = 3
        self.last_advance = 0.0
        self.dragging_timeline = False

        self._build_map_surface()

    def _build_map_surface(self):
        """Pre-render the static map."""
        self.map_surface = pygame.Surface((GRID_SIZE, GRID_SIZE))
        self.map_surface.fill(GRID_BG)
        cs = self.cell_size

        for wx, wy in self.map_data.get("water", []):
            pygame.draw.rect(self.map_surface, WATER,
                             (wx * cs, wy * cs, max(cs, 1), max(cs, 1)))
        for gx, gy in self.map_data.get("grass", []):
            pygame.draw.rect(self.map_surface, TALL_GRASS,
                             (gx * cs, gy * cs, max(cs, 1), max(cs, 1)))
        for hx, hy in self.map_data.get("high_ground", []):
            pygame.draw.rect(self.map_surface, HIGH_GROUND,
                             (hx * cs, hy * cs, max(cs, 1), max(cs, 1)))
        for ox, oy in self.map_data.get("obstacles", []):
            pygame.draw.rect(self.map_surface, OBSTACLE,
                             (ox * cs, oy * cs, max(cs, 1), max(cs, 1)))

        self.danger_surface = pygame.Surface((GRID_SIZE, GRID_SIZE), pygame.SRCALPHA)

    def run(self):
        import time
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                elif event.type == KEYDOWN:
                    if event.key in (K_ESCAPE, K_q):
                        running = False
                    elif event.key == K_SPACE:
                        self.paused = not self.paused
                    elif event.key == K_UP:
                        self.speed = min(self.speed + 1, 30)
                    elif event.key == K_DOWN:
                        self.speed = max(self.speed - 1, 1)
                    elif event.key == K_RIGHT:
                        self.current_frame = min(self.current_frame + 1, self.total_frames - 1)
                    elif event.key == K_LEFT:
                        self.current_frame = max(self.current_frame - 1, 0)
                    elif event.key == K_HOME:
                        self.current_frame = 0
                    elif event.key == K_END:
                        self.current_frame = self.total_frames - 1
                elif event.type == MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    if TIMELINE_Y <= my <= TIMELINE_Y + TIMELINE_H and mx < GRID_SIZE:
                        self.dragging_timeline = True
                        self.current_frame = int((mx / GRID_SIZE) * (self.total_frames - 1))

            # Mouse drag on timeline
            if self.dragging_timeline:
                if pygame.mouse.get_pressed()[0]:
                    mx, _ = pygame.mouse.get_pos()
                    mx = max(0, min(mx, GRID_SIZE))
                    self.current_frame = int((mx / GRID_SIZE) * (self.total_frames - 1))
                else:
                    self.dragging_timeline = False

            # Auto-advance
            if not self.paused and self.current_frame < self.total_frames - 1:
                now = time.time()
                if now - self.last_advance >= 1.0 / max(self.speed, 1):
                    self.current_frame += 1
                    self.last_advance = now

            self._render()
            pygame.display.flip()
            self.clock.tick(self.target_fps)

        pygame.quit()

    def _render(self):
        frame = self.frames[self.current_frame]
        self.screen.fill(BACKGROUND)

        # Map
        self.screen.blit(self.map_surface, (0, 0))

        cs = self.cell_size

        # Zone
        zone = frame["zone"]
        self.danger_surface.fill((0, 0, 0, 0))
        zone_rect = pygame.Rect(
            zone[0] * cs, zone[1] * cs,
            (zone[2] - zone[0] + 1) * cs,
            (zone[3] - zone[1] + 1) * cs,
        )
        alpha = min(60 + frame.get("zone_phase", 0) * 8, 120)
        self.danger_surface.fill((100, 20, 20, alpha))
        pygame.draw.rect(self.danger_surface, (0, 0, 0, 0), zone_rect)
        self.screen.blit(self.danger_surface, (0, 0))
        pygame.draw.rect(self.screen, ZONE_BORDER, zone_rect, 2)

        # Supply drops
        for drop in frame.get("supply_drops", []):
            if not drop["collected"]:
                dcx = drop["x"] * cs + cs / 2
                dcy = drop["y"] * cs + cs / 2
                pygame.draw.circle(self.screen, SUPPLY_DROP, (dcx, dcy), max(2, cs * 0.8))

        # Agents
        agent_r = max(2, cs / 2.5)
        for a in frame["agents"]:
            if not a["alive"]:
                continue
            bt = BEHAVIOR_MAP.get(a["behavior"], BehaviorType.NOMAD)
            color = AGENT_COLORS[bt]
            acx = a["x"] * cs + cs / 2
            acy = a["y"] * cs + cs / 2
            pygame.draw.circle(self.screen, color, (acx, acy), agent_r)

            # HP bar
            hp_frac = a["hp"] / a["max_hp"] if a["max_hp"] > 0 else 0
            bar_w = cs * 0.9
            bar_h = max(1, cs / 5)
            bar_x = acx - bar_w / 2
            bar_y = acy - agent_r - bar_h - 1
            pygame.draw.rect(self.screen, HP_BAR_BG, (bar_x, bar_y, bar_w, bar_h))
            hp_color = HP_BAR_HIGH if hp_frac > 0.5 else (HP_BAR_MID if hp_frac > 0.25 else HP_BAR_LOW)
            pygame.draw.rect(self.screen, hp_color, (bar_x, bar_y, bar_w * hp_frac, bar_h))

        # Kill flashes this frame
        for k in frame.get("kills", []):
            kcx = k["x"] * cs + cs / 2
            kcy = k["y"] * cs + cs / 2
            flash_surf = pygame.Surface((20, 20), pygame.SRCALPHA)
            pygame.draw.circle(flash_surf, (*KILL_FLASH, 180), (10, 10), 10)
            self.screen.blit(flash_surf, (kcx - 10, kcy - 10))

        # Panel
        self._render_panel(frame)

        # Timeline
        self._render_timeline()

        # Controls bar
        self._render_controls()

    def _render_panel(self, frame: dict):
        panel_rect = pygame.Rect(PANEL_X, 0, PANEL_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, PANEL_BG, panel_rect)
        pygame.draw.line(self.screen, PANEL_BORDER, (PANEL_X, 0), (PANEL_X, WINDOW_HEIGHT), 2)

        x = PANEL_X + 15
        y = 15

        title = self.font_title.render("REPLAY", True, TITLE_COLOR)
        self.screen.blit(title, (x, y))
        y += 35

        lbl = self.font.render(f"Turn: {frame['turn']}", True, TEXT_COLOR)
        self.screen.blit(lbl, (x, y)); y += 20
        lbl = self.font.render(f"Alive: {frame['alive_count']}", True, TEXT_COLOR)
        self.screen.blit(lbl, (x, y)); y += 20
        lbl = self.font.render(f"Phase: {frame.get('zone_phase', 0)}", True, TEXT_COLOR)
        self.screen.blit(lbl, (x, y)); y += 20
        lbl = self.font.render(f"Speed: {self.speed} t/s", True, TEXT_COLOR)
        self.screen.blit(lbl, (x, y)); y += 20
        lbl = self.font.render(f"Frame: {self.current_frame + 1}/{self.total_frames}", True, TEXT_DIM)
        self.screen.blit(lbl, (x, y)); y += 30

        # Status
        if self.current_frame == self.total_frames - 1:
            self.screen.blit(self.font_large.render("GAME OVER", True, GAMEOVER_COLOR), (x, y))
            y += 25
        elif self.paused:
            self.screen.blit(self.font_large.render("PAUSED", True, PAUSED_COLOR), (x, y))
            y += 25
        else:
            y += 25

        # Legend
        pygame.draw.line(self.screen, PANEL_BORDER, (x, y), (PANEL_X + PANEL_WIDTH - 15, y))
        y += 10
        for bt in BehaviorType:
            color = AGENT_COLORS[bt]
            count = sum(1 for a in frame["agents"] if a["alive"] and a["behavior"] == bt.value)
            pygame.draw.circle(self.screen, color, (x + 6, y + 6), 5)
            txt = self.font.render(f"{BEHAVIOR_LABELS[bt]}: {count}", True, TEXT_COLOR)
            self.screen.blit(txt, (x + 18, y))
            y += 20

        # Kill events this frame
        y += 10
        pygame.draw.line(self.screen, PANEL_BORDER, (x, y), (PANEL_X + PANEL_WIDTH - 15, y))
        y += 10
        self.screen.blit(self.font.render("EVENTS THIS TURN", True, TITLE_COLOR), (x, y))
        y += 20
        for k in frame.get("kills", []):
            killer_a = frame["agents"][k["killer"]]
            victim_a = frame["agents"][k["victim"]]
            txt = f"#{k['killer']} ({killer_a['behavior'][:1]}) > #{k['victim']} ({victim_a['behavior'][:1]})"
            self.screen.blit(self.font.render(txt, True, TEXT_DIM), (x, y))
            y += 16
        for d in frame.get("deaths", []):
            if d["cause"] == "zone":
                txt = f"Zone > #{d['agent']}"
                self.screen.blit(self.font.render(txt, True, ZONE_BORDER), (x, y))
                y += 16

    def _render_timeline(self):
        """Draw the scrubable timeline bar."""
        bar_rect = pygame.Rect(0, TIMELINE_Y, GRID_SIZE, TIMELINE_H)
        pygame.draw.rect(self.screen, (15, 15, 25), bar_rect)
        pygame.draw.rect(self.screen, PANEL_BORDER, bar_rect, 1)

        # Progress fill
        progress = self.current_frame / max(self.total_frames - 1, 1)
        fill_w = int(GRID_SIZE * progress)
        pygame.draw.rect(self.screen, (60, 60, 100), (0, TIMELINE_Y, fill_w, TIMELINE_H))

        # Playhead
        px = int(GRID_SIZE * progress)
        pygame.draw.rect(self.screen, TEXT_COLOR, (px - 1, TIMELINE_Y, 3, TIMELINE_H))

        # Turn label
        turn = self.frames[self.current_frame]["turn"]
        lbl = self.font.render(f"Turn {turn}", True, TEXT_COLOR)
        self.screen.blit(lbl, (5, TIMELINE_Y + 7))

    def _render_controls(self):
        bar_rect = pygame.Rect(0, CONTROLS_Y, GRID_SIZE, 50)
        pygame.draw.rect(self.screen, PANEL_BG, bar_rect)
        controls = "SPACE: Play/Pause | LEFT/RIGHT: Step | HOME/END: Jump | UP/DN: Speed | Drag timeline"
        self.screen.blit(self.font.render(controls, True, TEXT_DIM), (15, CONTROLS_Y + 8))
        seed_txt = f"Seed: {self.replay.get('seed', '?')}  |  Total turns: {self.replay.get('total_turns', '?')}"
        self.screen.blit(self.font.render(seed_txt, True, TEXT_DIM), (15, CONTROLS_Y + 28))


def run_replay_viewer(path: str, fps: int = 60) -> None:
    """Load and play a replay file."""
    print(f"Loading replay: {path}")
    data = load_replay(path)
    print(f"Loaded: {len(data['frames'])} frames, seed {data.get('seed', '?')}")
    viewer = ReplayViewer(data, fps=fps)
    viewer.run()
