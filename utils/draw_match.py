"""
Match trace renderer and visualization tool.
Visualizes GFootball .dump trace files into MP4 video and GIF clips.
"""

import os
import sys
import json
import math
import argparse
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

import numpy as np

# Color name mapping to RGB tuples
COLOR_MAP = {
    'red': (220, 38, 38),
    'blue': (37, 99, 235),
    'white': (255, 255, 255),
    'black': (15, 23, 42),
    'yellow': (234, 179, 8),
    'green': (22, 163, 74),
    'navy': (30, 58, 138),
    'skyblue': (14, 165, 233),
    'orange': (249, 115, 22),
    'brown': (120, 53, 15),
}


def get_color_rgb(name: str, default: Tuple[int, int, int] = (128, 128, 128)) -> Tuple[int, int, int]:
    if not name:
        return default
    clean = str(name).strip().lower()
    return COLOR_MAP.get(clean, default)


def get_latest_dump() -> Optional[str]:
    d = os.path.expanduser('~/projects/TiKick_OLD/results/11_vs_11_kaggle/replay')
    if os.path.isdir(d):
        files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith('.dump')]
        if files:
            return max(files, key=os.path.getmtime)
    return None


class GameReplayVisualizer:
    def __init__(self, config_path: Optional[str] = None, width: int = 1280, height: int = 720, headless: bool = True):
        self.width = width
        self.height = height
        self.headless = headless
        
        if self.headless:
            os.environ['SDL_VIDEODRIVER'] = 'dummy'
            
        self._load_config(config_path)
        
        import pygame
        pygame.init()
        pygame.font.init()
        
        self.screen = pygame.display.set_mode((self.width, self.height))
        
        try:
            self.font_xlarge = pygame.font.SysFont('Outfit', 44, bold=True)
            self.font_large = pygame.font.SysFont('Inter', 28, bold=True)
            self.font_medium = pygame.font.SysFont('Inter', 22, bold=True)
            self.font_small = pygame.font.SysFont('Inter', 18)
            self.font_tiny = pygame.font.SysFont('monospace', 13)
        except Exception:
            self.font_xlarge = pygame.font.Font(None, 44)
            self.font_large = pygame.font.Font(None, 28)
            self.font_medium = pygame.font.Font(None, 22)
            self.font_small = pygame.font.Font(None, 18)
            self.font_tiny = pygame.font.Font(None, 13)

    def _load_config(self, config_path: Optional[str]):
        root = os.path.expanduser('~/projects/TiKick_OLD')
        candidates = [config_path, 'match_config.json', 'match.json', './match_config.json', './match.json']
        if config_path:
            candidates.insert(0, os.path.join(root, config_path))
            
        cfg = None
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        cfg = json.load(f)
                    print(f"[+] Config loaded: {path}")
                    break
                except Exception:
                    pass
                    
        if not cfg:
            print("[-] No config found – using defaults.")
            cfg = {}
            
        setup = cfg.get('match_setup', {})
        teams = setup.get('teams', {})
        
        self.home_name = setup.get('home_team', 'Home')
        self.away_name = setup.get('away_team', 'Away')
        
        home_cfg = teams.get(self.home_name, {})
        away_cfg = teams.get(self.away_name, {})
        
        self.home_shirt = get_color_rgb(home_cfg.get('shirt_color', 'Red'), (220, 38, 38))
        self.home_short = get_color_rgb(home_cfg.get('short_color', 'White'), (255, 255, 255))
        self.away_shirt = get_color_rgb(away_cfg.get('shirt_color', 'Blue'), (37, 99, 235))
        self.away_short = get_color_rgb(away_cfg.get('short_color', 'White'), (255, 255, 255))
        
        self.home_players = home_cfg.get('players', [])
        self.away_players = away_cfg.get('players', [])

    def to_screen(self, x: float, y: float) -> Tuple[int, int]:
        """Normalised pitch coords [-1..1, -0.42..0.42] -> pixel coords."""
        sx = int((x + 1.0) / 2.0 * self.width)
        sy = int((y + 0.42) / 0.84 * self.height)
        return sx, sy

    def draw_aa_circle(self, cx: int, cy: int, radius: int, color: Tuple[int, int, int], ring_width: int = 1):
        import pygame
        import pygame.gfxdraw
        radius = max(1, int(radius))
        for r in range(radius - ring_width + 1, radius + 1):
            if r > 0:
                pygame.gfxdraw.aacircle(self.screen, cx, cy, r, color)
                pygame.gfxdraw.filled_circle(self.screen, cx, cy, r, color)

    def _draw_pitch(self):
        import pygame
        self.screen.fill((26, 77, 46)) # Field green
        
        line_color = (220, 225, 230)
        
        # Outer boundary
        sx1, sy1 = self.to_screen(-1.0, -0.42)
        sx2, sy2 = self.to_screen(1.0, 0.42)
        pygame.draw.rect(self.screen, line_color, (sx1, sy1, sx2 - sx1, sy2 - sy1), 2)
        
        # Halfway line
        cx1, cy1 = self.to_screen(0.0, -0.42)
        cx2, cy2 = self.to_screen(0.0, 0.42)
        pygame.draw.line(self.screen, line_color, (cx1, cy1), (cx2, cy2), 2)
        
        # Center circle
        ccx, ccy = self.to_screen(0.0, 0.0)
        r_pixel = int(0.15 / 2.0 * self.width)
        pygame.draw.circle(self.screen, line_color, (ccx, ccy), r_pixel, 2)
        pygame.draw.circle(self.screen, line_color, (ccx, ccy), 4)

    def load_dump(self, dump_path: str) -> List[dict]:
        import six.moves.cPickle as cPickle
        frames = []
        with open(dump_path, 'rb') as f:
            while True:
                try:
                    frames.append(cPickle.load(f))
                except (EOFError, Exception):
                    break
        return frames

    def _validate_obs(self, obs: dict) -> None:
        """Validate positions for players and ball.
        Logs warnings if data is missing or out of expected bounds.
        """
        left = obs.get('left_team', [])
        right = obs.get('right_team', [])
        if len(left) != 11:
            print(f"[WARN] left_team has {len(left)} players (expected 11)")
        if len(right) != 11:
            print(f"[WARN] right_team has {len(right)} players (expected 11)")
        # Check bounds (allow normal sideline/endline run-off margin)
        for side, name in [(left, 'left'), (right, 'right')]:
            for idx, pos in enumerate(side):
                if not (-1.2 <= pos[0] <= 1.2) or not (-0.55 <= pos[1] <= 0.55):
                    print(f"[WARN] {name}_team player {idx} out of bounds: {pos}")
        ball = obs.get('ball', [0.0, 0.0, 0.0])
        if not (-1.2 <= ball[0] <= 1.2) or not (-0.55 <= ball[1] <= 0.55):
            print(f"[WARN] ball out of bounds: {ball}")

    def _draw_frame(self, obs: dict) -> np.ndarray:
        import pygame
        import pygame.gfxdraw

        self._draw_pitch()
        self._validate_obs(obs)

        left_team = obs.get('left_team', [])
        right_team = obs.get('right_team', [])
        ball = obs.get('ball', [0.0, 0.0, 0.0])

        # Draw left team (Home)
        for i, pos in enumerate(left_team):
            px, py = self.to_screen(pos[0], pos[1])
            pygame.draw.circle(self.screen, self.home_shirt, (px, py), 9)
            pygame.draw.circle(self.screen, (0, 0, 0), (px, py), 9, 1)

        # Draw right team (Away)
        for i, pos in enumerate(right_team):
            px, py = self.to_screen(pos[0], pos[1])
            pygame.draw.circle(self.screen, self.away_shirt, (px, py), 9)
            pygame.draw.circle(self.screen, (255, 255, 255), (px, py), 9, 1)

        # Draw ball
        bx, by = self.to_screen(ball[0], ball[1])
        pygame.draw.circle(self.screen, (255, 255, 200), (bx, by), 6)
        pygame.draw.circle(self.screen, (0, 0, 0), (bx, by), 6, 1)

        # Score header
        score = obs.get('score', [0, 0])
        score_txt = f"{self.home_name}  {score[0]} - {score[1]}  {self.away_name}"
        txt_surf = self.font_large.render(score_txt, True, (255, 255, 255))
        rect = txt_surf.get_rect(center=(self.width // 2, 25))
        self.screen.blit(txt_surf, rect)

        raw = pygame.image.tostring(self.screen, 'RGB')
        return np.frombuffer(raw, dtype=np.uint8).reshape((self.height, self.width, 3))

    def render_dump(self, dump_path: str, output_path: str, limit: Optional[int] = None, fps: int = 10) -> List[Tuple[int, str]]:
        import cv2

        print(f"[+] Loading dump: {dump_path} …")
        dump_data = self.load_dump(dump_path)
        total = len(dump_data)
        if limit:
            total = min(total, limit)

        print(f"[+] Rendering {total} frames → {output_path}")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(output_path, fourcc, fps, (self.width, self.height))

        goal_events = []
        prev_score = [0, 0]

        for idx in range(total):
            frame = dump_data[idx]
            obs = frame
            if isinstance(obs, dict) and 'observation' in obs:
                obs = obs['observation']
            if isinstance(obs, (list, tuple)) and obs:
                obs = obs[0]

            current_score = obs.get('score', [0, 0])
            if current_score != prev_score:
                scorer = "home" if current_score[0] > prev_score[0] else "away"
                goal_events.append((idx, scorer))
                print(f"    ⚽ GOAL at frame {idx} – score now {current_score[0]}:{current_score[1]}")
                prev_score = list(current_score)

            rgb = self._draw_frame(obs)
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            out_writer.write(bgr)

        out_writer.release()
        print(f"[+] Video saved: {output_path}")
        return goal_events

    def quit(self):
        import pygame
        pygame.quit()


def mp4_to_gif(mp4_path: str, gif_path: str, fps: int = 10, scale: float = 0.75):
    """Convert MP4 to GIF using FFmpeg."""
    cmd = [
        'ffmpeg', '-y', '-i', mp4_path,
        '-vf', f'fps={fps},scale=iw*{scale}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=256[p];[s1][p]paletteuse=dither=bayer',
        '-loop', '0', gif_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print(f"    GIF saved: {gif_path}")
    else:
        print(f"    FFmpeg error: {res.stderr[-300:]}")
