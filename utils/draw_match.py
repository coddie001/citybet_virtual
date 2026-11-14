import os
import sys
import json
import math
import argparse
import six.moves.cPickle
import pkgutil

# Python 3.13 compatibility monkeypatch for pkg_resources/setuptools
if not hasattr(pkgutil, "ImpImporter"):
    class ImpImporter:
        pass
    pkgutil.ImpImporter = ImpImporter

import numpy as np
import cv2
import pygame
import pygame.gfxdraw

# ─────────────────────── constants ─────────────────────────────────────────
COLOR_MAP = {
    "green":  (40, 167, 69),
    "blue":   (0,  123, 255),
    "white":  (240, 240, 240),
    "red":    (220, 53,  69),
    "yellow": (255, 193, 7),
    "black":  (30,  30,  30),
    "navy":   (0,   0,  128),
    "orange": (253, 126, 20),
}

GAME_MODES = {
    0: "NORMAL",
    1: "KICK OFF",
    2: "GOAL KICK",
    3: "FREE KICK",
    4: "CORNER KICK",
    5: "THROW IN",
    6: "PENALTY",
}

def get_color_rgb(name, default=(128, 128, 128)):
    return COLOR_MAP.get(str(name).lower(), default)


# ─────────────────────── main class ────────────────────────────────────────
class GameReplayVisualizer:
    """
    Importable, reusable replay renderer.

    Usage from another script:
        from draw_match import GameReplayVisualizer
        viz = GameReplayVisualizer(config_path="match.json")
        viz.render_dump("trace.dump", "out.mp4")
        viz.quit()
    """

    def __init__(self, config_path=None, width=1200, height=750, headless=True):
        self.width   = width
        self.height  = height
        self.headless = headless

        self.config = self._load_config(config_path)
        setup = self.config.get("match_setup", {})
        self.home_name = setup.get("home_team", "Home")
        self.away_name = setup.get("away_team", "Away")
        teams = setup.get("teams", {})

        home_cfg = teams.get(self.home_name, {})
        away_cfg = teams.get(self.away_name, {})

        self.home_shirt  = get_color_rgb(home_cfg.get("shirt_color", "Green"))
        self.home_short  = get_color_rgb(home_cfg.get("short_color", "White"))
        self.away_shirt  = get_color_rgb(away_cfg.get("shirt_color", "Blue"))
        self.away_short  = get_color_rgb(away_cfg.get("short_color", "Blue"))

        self.home_players = home_cfg.get("players", [])
        self.away_players = away_cfg.get("players", [])

        if self.headless:
            os.environ["SDL_VIDEODRIVER"] = "dummy"

        pygame.init()
        pygame.font.init()
        self.screen = pygame.display.set_mode((self.width, self.height))

        self.font_xlarge = pygame.font.SysFont("Outfit",    44, bold=True)
        self.font_large  = pygame.font.SysFont("Outfit",    28, bold=True)
        self.font_small  = pygame.font.SysFont("Outfit",    22, bold=True)
        self.font_medium = pygame.font.SysFont("Inter",     18, bold=True)
        self.font_tiny   = pygame.font.SysFont("monospace", 13, bold=True)

    # ── config ──────────────────────────────────────────────────────────────
    def _load_config(self, config_path):
        root = os.path.expanduser("~/projects/TiKick_OLD")
        candidates = [config_path] if config_path else [
            os.path.join(root, "match_config.json"),
            os.path.join(root, "match.json"),
            "./match_config.json",
            "./match.json",
        ]
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    with open(path) as f:
                        print(f"[+] Config loaded: {path}")
                        return json.load(f)
                except Exception:
                    pass
        print("[-] No config found – using defaults.")
        return {"match_setup": {"home_team": "Home", "away_team": "Away", "teams": {}}}

    # ── drawing helpers ──────────────────────────────────────────────────────
    def draw_text_outlined(self, text, font, color, outline, pos):
        txt = font.render(text, True, color)
        shadow = font.render(text, True, outline)
        x, y = pos
        for dx in (-2, -1, 1, 2):
            self.screen.blit(shadow, (x + dx, y))
            self.screen.blit(shadow, (x, y + dx))
        self.screen.blit(txt, pos)

    def to_screen(self, x, y):
        """Normalised pitch coords → pixel coords."""
        sx = int((x + 1.0) / 2.0 * self.width)
        sy = int((y + 0.42) / 0.84 * self.height)
        return sx, sy

    def draw_aa_circle(self, cx, cy, radius, color, ring_width=0):
        radius = max(1, radius)
        if ring_width == 0:
            pygame.gfxdraw.aacircle(self.screen, cx, cy, radius, color)
            pygame.gfxdraw.filled_circle(self.screen, cx, cy, radius, color)
        else:
            for r in range(max(1, radius - ring_width), radius + 1):
                pygame.gfxdraw.aacircle(self.screen, cx, cy, r, color)

    # ── pitch ────────────────────────────────────────────────────────────────
    def _draw_pitch(self):
        self.screen.fill((26, 77, 46))
        for s in range(10):
            if s % 2 == 0:
                sx1, _ = self.to_screen(-1.0 + s * 0.2, 0)
                sx2, _ = self.to_screen(-1.0 + (s + 1) * 0.2, 0)
                pygame.draw.rect(self.screen, (30, 86, 52), (sx1, 0, sx2 - sx1, self.height))

        W = (220, 225, 230)
        pygame.draw.rect(self.screen, W, (0, 0, self.width, self.height), 3)
        pygame.draw.line(self.screen, W, (self.width // 2, 0), (self.width // 2, self.height), 3)
        pygame.draw.circle(self.screen, W,
                           (self.width // 2, self.height // 2),
                           int(0.15 * self.width / 2), 3)

        def sc(x, y):
            return self.to_screen(x, y)

        # Penalty areas, 6-yard boxes, spots, arcs
        for sign in (-1, 1):
            ax1, ay1 = sc(sign * 1.0, -0.2)
            ax2, ay2 = sc(sign * 0.7, 0.2)
            pygame.draw.rect(self.screen, W, (min(ax1, ax2), ay1, abs(ax2 - ax1), ay2 - ay1), 3)
            bx1, by1 = sc(sign * 1.0, -0.1)
            bx2, by2 = sc(sign * 0.88, 0.1)
            pygame.draw.rect(self.screen, W, (min(bx1, bx2), by1, abs(bx2 - bx1), by2 - by1), 3)
            spx, spy = sc(sign * 0.78, 0.0)
            pygame.draw.circle(self.screen, W, (spx, spy), 4)
            # penalty arc (the part outside the box)
            arc_r = int(0.15 * self.width / 2)
            rect = pygame.Rect(spx - arc_r, spy - arc_r, arc_r * 2, arc_r * 2)
            if sign < 0:
                pygame.draw.arc(self.screen, W, rect, -0.9, 0.9, 3)
            else:
                pygame.draw.arc(self.screen, W, rect, 3.14159 - 0.9, 3.14159 + 0.9, 3)
        # centre spot
        pygame.draw.circle(self.screen, W, (self.width // 2, self.height // 2), 4)
        # corner arcs
        for cx, cy, a0, a1 in ((0, 0, -1.5708, 0), (self.width, 0, 3.14159, 4.7124),
                               (0, self.height, 0, 1.5708), (self.width, self.height, 1.5708, 3.14159)):
            r = 18
            pygame.draw.arc(self.screen, W, pygame.Rect(cx - r, cy - r, 2 * r, 2 * r), a0, a1, 3)

        # Goals: net behind the line, hatch, back bar and two white posts
        GOAL_HALF = 0.044
        net_depth = 26
        for sign in (-1, 1):
            _, gy1 = sc(0, -GOAL_HALF)
            _, gy2 = sc(0, GOAL_HALF)
            if sign < 0:
                net = pygame.Rect(0, gy1, net_depth, gy2 - gy1)
                line_x = net_depth
                back_x = 0
            else:
                net = pygame.Rect(self.width - net_depth, gy1, net_depth, gy2 - gy1)
                line_x = self.width - net_depth
                back_x = self.width
            pygame.draw.rect(self.screen, (14, 40, 26), net)
            for k in range(net.left, net.right + 1, 6):
                pygame.draw.line(self.screen, (170, 185, 175), (k, net.top), (k, net.bottom), 1)
            for k in range(net.top, net.bottom + 1, 6):
                pygame.draw.line(self.screen, (170, 185, 175), (net.left, k), (net.right, k), 1)
            pygame.draw.line(self.screen, (255, 255, 255), (back_x, gy1), (back_x, gy2), 4)
            pygame.draw.line(self.screen, (255, 255, 255), (line_x, gy1), (line_x, gy2), 2)
            for py_ in (gy1, gy2):
                pygame.draw.line(self.screen, (255, 255, 255), (net.left, py_), (net.right, py_), 4)
                pygame.draw.circle(self.screen, (255, 255, 255), (line_x, py_), 6)
                pygame.draw.circle(self.screen, (120, 120, 120), (line_x, py_), 6, 1)

    # ── single frame ─────────────────────────────────────────────────────────
    def _draw_frame(self, obs):
        """Draw one observation dict onto self.screen, return np RGB array."""
        self._draw_pitch()

        left_team        = obs.get("left_team", [])
        right_team       = obs.get("right_team", [])
        ball_owned_team  = obs.get("ball_owned_team", -1)
        ball_owned_player= obs.get("ball_owned_player", -1)
        score            = obs.get("score", [0, 0])
        game_mode        = obs.get("game_mode", 0)

        active_px = active_py = 0
        active_name = active_str = active_team_name = None

        def draw_player(pos, team_idx, p_idx, shirt, short):
            nonlocal active_px, active_py, active_name, active_str, active_team_name
            # If goalkeeper, use a special high-contrast jersey color
            if p_idx == 0:
                choices = [(34, 197, 94), (249, 115, 22), (234, 179, 8)]
                best_color = choices[0]
                max_dist = -1
                for c in choices:
                    dist = np.linalg.norm(np.array(c) - np.array(shirt))
                    if dist > max_dist:
                        max_dist = dist
                        best_color = c
                shirt = best_color
                short = (30, 30, 30)  # Dark/neutral shorts for GK

            px, py = self.to_screen(pos[0], pos[1])
            px = min(max(px, 14), self.width - 14)
            py = min(max(py, 14), self.height - 14)
            is_active = (team_idx == ball_owned_team and p_idx == ball_owned_player)

            if is_active:
                self.draw_aa_circle(px, py, 16, (251, 191, 36), 3)
                self.draw_aa_circle(px, py, 21, (245, 158, 11), 1)
                active_px, active_py = px, py
                roster = self.home_players if team_idx == 0 else self.away_players
                tname  = self.home_name    if team_idx == 0 else self.away_name
                active_name      = roster[p_idx]["name"]       if p_idx < len(roster) else f"#{p_idx}"
                active_str       = roster[p_idx].get("strength", 80) if p_idx < len(roster) else 80
                active_team_name = tname

            is_gk = (p_idx == 0)
            body_r = 12 if is_gk else 10
            # shadow
            self.draw_aa_circle(px + 2, py + 2, body_r, (0, 0, 0))
            # body
            self.draw_aa_circle(px, py, body_r, shirt)
            self.draw_aa_circle(px, py, body_r, short, 2)
            # Goalkeepers get a bright outer ring so they're always visible.
            if is_gk:
                self.draw_aa_circle(px, py, body_r + 3, (255, 255, 255), 1)
            # number
            num_txt = self.font_tiny.render(str(p_idx), True,
                      (255, 255, 255) if sum(shirt) < 380 else (0, 0, 0))
            self.screen.blit(num_txt, (px - num_txt.get_width() // 2,
                                       py - num_txt.get_height() // 2))

        for i, pos in enumerate(left_team):
            draw_player(pos, 0, i, self.home_shirt, self.home_short)
        for i, pos in enumerate(right_team):
            draw_player(pos, 1, i, self.away_shirt, self.away_short)

        # ── Ball ──
        ball = obs.get("ball", [0.0, 0.0, 0.0])
        bx, by = self.to_screen(ball[0], ball[1])
        bz = float(ball[2])

        # Ball shrinks slightly as it rises (perspective) – cap so it never disappears
        # bz=0 → r=8, bz=9.6 (max) → r=4 (subtle size change, not huge)
        ball_r = max(4, int(8 - bz * 0.45))

        # Shadow on the ground: grows / fades as ball rises
        shadow_alpha = max(40, int(180 - bz * 14))
        shadow_r     = min(14, int(8 + bz * 0.7))
        # We draw shadow at ground-level position (bx, by)
        shadow_surf = pygame.Surface((shadow_r * 2 + 2, shadow_r + 2), pygame.SRCALPHA)
        pygame.gfxdraw.filled_ellipse(shadow_surf, shadow_r, shadow_r // 2,
                                      shadow_r, shadow_r // 2,
                                      (0, 0, 0, shadow_alpha))
        self.screen.blit(shadow_surf, (bx - shadow_r, by - shadow_r // 2))

        # Ball rendered above ground (rises upward on screen as bz grows)
        ball_screen_y = by - int(bz * 12)
        self.draw_aa_circle(bx, ball_screen_y, ball_r, (255, 255, 255))
        self.draw_aa_circle(bx, ball_screen_y, ball_r, (30, 30, 30), 1)
        # highlight spot
        self.draw_aa_circle(bx - max(1, ball_r // 3),
                            ball_screen_y - max(1, ball_r // 3),
                            max(1, ball_r // 4), (255, 255, 255))

        # ── Active player tag ──
        if active_name:
            tag_text = active_name
            lbl = self.font_medium.render(tag_text, True, (255, 255, 255))
            w = lbl.get_width() + 18
            tag_rect = pygame.Rect(active_px - w // 2, active_py - 38, w, 24)
            pygame.draw.rect(self.screen, (15, 23, 42), tag_rect, 0, 5)
            pygame.draw.rect(self.screen, (245, 158, 11), tag_rect, 1, 5)
            self.screen.blit(lbl, (active_px - lbl.get_width() // 2, active_py - 36))

        # ── Scoreboard ──
        # Wider panel with three fixed zones: [home name][score][away name].
        # Names are shrunk/truncated to fit their zone so they never overlap
        # the score, no matter how long the club name is.
        PANEL_X, PANEL_W, PANEL_Y, PANEL_H = 300, 600, 16, 66
        BADGE = 14
        EDGE_PAD = 16          # padding inside the panel edges
        SCORE_GAP = 18         # min gap between a name and the score
        pygame.draw.rect(self.screen, (10, 18, 36), (PANEL_X, PANEL_Y, PANEL_W, PANEL_H), 0, 10)
        pygame.draw.rect(self.screen, (200, 210, 220), (PANEL_X, PANEL_Y, PANEL_W, PANEL_H), 2, 10)

        panel_cx = PANEL_X + PANEL_W // 2

        # Center score rendering
        score_txt = f"{score[0]}  :  {score[1]}"
        score_w, score_h = self.font_xlarge.size(score_txt)
        score_x = panel_cx - score_w // 2
        score_y = PANEL_Y + (PANEL_H - score_h) // 2
        self.draw_text_outlined(score_txt, self.font_xlarge,
                                (251, 191, 36), (0, 0, 0),
                                (score_x, score_y))

        # Each name zone reserves room for its colour badge (BADGE + 10px).
        home_zone_left  = PANEL_X + EDGE_PAD + BADGE + 10
        home_zone_right = score_x - SCORE_GAP
        away_zone_left  = score_x + score_w + SCORE_GAP
        away_zone_right = PANEL_X + PANEL_W - EDGE_PAD - BADGE - 10
        home_max_w = max(10, home_zone_right - home_zone_left)
        away_max_w = max(10, away_zone_right - away_zone_left)

        def fit_name(name, max_w):
            """Pick the largest font that fits; truncate with '..' as a last resort."""
            name_up = (name or "").upper()
            for font in (self.font_large, self.font_small, self.font_medium):
                if font.size(name_up)[0] <= max_w:
                    return font, name_up
            font = self.font_medium
            truncated = name_up
            while len(truncated) > 3:
                truncated = truncated[:-1]
                if font.size(truncated + "..")[0] <= max_w:
                    return font, truncated + ".."
            return font, name_up[:3]

        home_font, home_disp = fit_name(self.home_name, home_max_w)
        away_font, away_disp = fit_name(self.away_name, away_max_w)

        home_w, home_h = home_font.size(home_disp)
        away_w, away_h = away_font.size(away_disp)

        # Home: right-aligned against the score; Away: left-aligned against it.
        home_name_x = home_zone_right - home_w
        home_y = PANEL_Y + (PANEL_H - home_h) // 2
        self.draw_text_outlined(home_disp, home_font, (255, 255, 255), (0, 0, 0), (home_name_x, home_y))

        away_name_x = away_zone_left
        away_y = PANEL_Y + (PANEL_H - away_h) // 2
        self.draw_text_outlined(away_disp, away_font, (255, 255, 255), (0, 0, 0), (away_name_x, away_y))

        # Colour badges (squares) clamped just inside the panel edges.
        badge_y = PANEL_Y + (PANEL_H - BADGE) // 2
        home_badge_x = max(PANEL_X + EDGE_PAD, home_name_x - BADGE - 10)
        away_badge_x = min(PANEL_X + PANEL_W - EDGE_PAD - BADGE, away_name_x + away_w + 10)
        pygame.draw.rect(self.screen, self.home_shirt, (home_badge_x, badge_y, BADGE, BADGE), 0, 3)
        pygame.draw.rect(self.screen, self.away_shirt, (away_badge_x, badge_y, BADGE, BADGE), 0, 3)

        # ── Game mode banner ──
        mode_str = GAME_MODES.get(game_mode, "NORMAL")
        if mode_str != "NORMAL" and not getattr(self, "_banner", None):
            bw = 320
            pygame.draw.rect(self.screen, (180, 28, 28), (600 - bw // 2, 90, bw, 36), 0, 8)
            pygame.draw.rect(self.screen, (255, 255, 255), (600 - bw // 2, 90, bw, 36), 2, 8)
            self.draw_text_outlined(mode_str, self.font_large, (255, 255, 255), (0, 0, 0),
                                    (600 - self.font_large.size(mode_str)[0] // 2, 93))

        # ── Possession bar ──
        pygame.draw.rect(self.screen, (10, 18, 36), (220, 688, 760, 44), 0, 7)
        pygame.draw.rect(self.screen, (200, 210, 220), (220, 688, 760, 44), 2, 7)
        if active_name:
            db = f"IN POSSESSION: {active_name.upper()}  |  STR {active_str}  |  {active_team_name.upper()}"
            self.draw_text_outlined(db, self.font_medium, (251, 191, 36), (0, 0, 0),
                                    (600 - self.font_medium.size(db)[0] // 2, 698))
        else:
            db = "BALL IS LOOSE"
            self.draw_text_outlined(db, self.font_medium, (148, 163, 184), (0, 0, 0),
                                    (600 - self.font_medium.size(db)[0] // 2, 698))

        # ── Event banner (GOAL / CORNER / FREE KICK ...) ──
        banner = getattr(self, "_banner", None)
        if banner:
            text, color, strength = banner
            if text == "GOAL!":
                flash = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                flash.fill((255, 220, 0, int(90 * strength)))
                self.screen.blit(flash, (0, 0))
            bw, bh = 520, 84
            bx0, by0 = self.width // 2 - bw // 2, self.height // 2 - bh // 2 - 120
            pygame.draw.rect(self.screen, (10, 18, 36), (bx0, by0, bw, bh), 0, 14)
            pygame.draw.rect(self.screen, color, (bx0, by0, bw, bh), 4, 14)
            tw = self.font_xlarge.size(text)[0]
            self.draw_text_outlined(text, self.font_xlarge, color, (0, 0, 0), (self.width // 2 - tw // 2, by0 + 16))

        # Return raw pixel array (RGB)
        frame_data = pygame.image.tostring(self.screen, "RGB")
        return np.frombuffer(frame_data, dtype=np.uint8).reshape((self.height, self.width, 3))

    # ── event banners ────────────────────────────────────────────────────────
    _MODE_BANNERS = {2: "GOAL KICK", 3: "FREE KICK", 4: "CORNER!", 5: "THROW IN", 6: "PENALTY!"}

    def _reset_events(self):
        self._banner = None
        self._banner_until = -1
        self._banner_start = -1
        self._banner_color = (255, 255, 255)
        self._prev_mode = 0
        self._prev_score_ev = None

    def _update_events(self, obs, idx):
        """Set self._banner for goals and set pieces (called once per frame, in order)."""
        if not hasattr(self, "_banner_until"):
            self._reset_events()
        score = tuple(obs.get("score", [0, 0]))
        mode = obs.get("game_mode", 0)
        if self._prev_score_ev is not None and score != self._prev_score_ev:
            scorer = self.home_name if score[0] > self._prev_score_ev[0] else self.away_name
            self._banner_text = "GOAL!"
            self._banner_start, self._banner_until = idx, idx + 40
            self._banner_color = (251, 191, 36)
        elif mode != self._prev_mode and mode in self._MODE_BANNERS and idx > self._banner_until:
            self._banner_text = self._MODE_BANNERS[mode]
            self._banner_start, self._banner_until = idx, idx + 25
            self._banner_color = (239, 68, 68)
        self._prev_score_ev = score
        self._prev_mode = mode
        if idx <= self._banner_until:
            span = max(1, self._banner_until - self._banner_start)
            self._banner = (self._banner_text, self._banner_color, 1.0 - (idx - self._banner_start) / span)
        else:
            self._banner = None

    # ── load dump ────────────────────────────────────────────────────────────
    @staticmethod
    def load_dump(dump_path):
        frames = []
        with open(dump_path, "rb") as f:
            while True:
                try:
                    frames.append(six.moves.cPickle.load(f))
                except EOFError:
                    break
                except Exception:
                    break
        return frames

    @staticmethod
    def _extract_obs(frame):
        obs = frame.get("observation", {}) if isinstance(frame, dict) else frame
        if isinstance(obs, (list, tuple)) and obs:
            obs = obs[0]
        return obs if isinstance(obs, dict) else {}

    # ── render full replay ───────────────────────────────────────────────────
    def render_dump(self, dump_path, output_path, limit=-1, fps=10):
        """
        Render a .dump to MP4 and return list of (frame_idx, scorer_team) goal events.
        """
        print(f"[+] Loading dump: {dump_path} …")
        dump_data = self.load_dump(dump_path)
        total = len(dump_data) if (limit is None or limit <= 0) else min(len(dump_data), limit)
        print(f"[+] Rendering {total} frames → {output_path}")

        fourcc     = cv2.VideoWriter_fourcc(*"mp4v")
        out_writer = cv2.VideoWriter(output_path, fourcc, fps, (self.width, self.height))

        prev_score  = None
        goal_events = []   # list of (frame_idx, scorer_team)
        self._reset_events()

        for idx in range(total):
            if idx % 100 == 0:
                print(f"    frame {idx}/{total} …")
            frame = dump_data[idx]
            obs   = self._extract_obs(frame)
            if not obs:
                continue

            self._update_events(obs, idx)
            rgb = self._draw_frame(obs)

            # detect goal
            score = tuple(obs.get("score", [0, 0]))
            if prev_score is not None and score != prev_score:
                scorer = 0 if score[0] > prev_score[0] else 1
                goal_events.append((idx, scorer))
                print(f"    ⚽ GOAL at frame {idx} – score now {score[0]}:{score[1]}")
            prev_score = score

            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            out_writer.write(bgr)

        out_writer.release()
        print(f"[+] Video saved: {output_path}")
        return goal_events

    # ── render goal highlights ────────────────────────────────────────────────
    def render_goal_highlights(self, dump_path, out_dir, window_before=50,
                                window_after=80, fps=10):
        """
        Extract ±window frames around every goal and save as individual MP4 clips.
        """
        print("[+] Extracting goal highlight clips …")
        dump_data = self.load_dump(dump_path)
        total     = len(dump_data)
        os.makedirs(out_dir, exist_ok=True)

        prev_score  = None
        goal_events = []
        for idx, frame in enumerate(dump_data):
            obs = self._extract_obs(frame)
            if not obs:
                continue
            score = tuple(obs.get("score", [0, 0]))
            if prev_score is not None and score != prev_score:
                scorer = 0 if score[0] > prev_score[0] else 1
                goal_events.append((idx, scorer, score))
            prev_score = score

        if not goal_events:
            print("[-] No goals found in this trace.")
            return []

        mp4_paths = []
        for g_num, (goal_idx, scorer, final_score) in enumerate(goal_events, 1):
            start = max(0, goal_idx - window_before)
            end   = min(total, goal_idx + window_after)
            scorer_name = self.home_name if scorer == 0 else self.away_name
            mp4_path = os.path.join(out_dir, f"goal_{g_num}_{scorer_name.replace(' ','_')}.mp4")
            print(f"  Goal {g_num} by {scorer_name} at frame {goal_idx} → frames {start}–{end}")

            fourcc     = cv2.VideoWriter_fourcc(*"mp4v")
            out_writer = cv2.VideoWriter(mp4_path, fourcc, fps, (self.width, self.height))

            self._reset_events()
            for i in range(max(0, start - 1), end):
                obs = self._extract_obs(dump_data[i])
                if not obs:
                    continue
                self._update_events(obs, i)
                if i < start:
                    continue
                rgb = self._draw_frame(obs)
                out_writer.write(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))

            out_writer.release()
            print(f"    MP4 saved: {mp4_path}")
            mp4_paths.append(mp4_path)

        return mp4_paths

    def quit(self):
        pygame.quit()


# ──────────────────── CLI entry-point ──────────────────────────────────────
def get_latest_dump():
    d = os.path.expanduser("~/projects/TiKick_OLD/results/11_vs_11_kaggle/replay")
    if os.path.isdir(d):
        files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".dump")]
        return max(files, key=os.path.getmtime) if files else None
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="TiKick Game Replay Visualizer")
    ap.add_argument("--dump",      default=None, help="Path to .dump file")
    ap.add_argument("--config",    default=None, help="Path to match.json")
    ap.add_argument("--output",    default=None, help="Output .mp4 path")
    ap.add_argument("--limit",     type=int, default=-1,
                    help="Max frames (-1 = full episode)")
    ap.add_argument("--fps",       type=int, default=10)
    ap.add_argument("--highlights", action="store_true",
                    help="Extract and save goal highlight clips")
    ap.add_argument("--headless",  default="true", choices=["true", "false"])
    args = ap.parse_args()

    print("=" * 70)
    print("              TIKICK MATCH REPLAY ENGINE  v2")
    print("=" * 70)

    dump_path = args.dump or get_latest_dump()
    if not dump_path:
        sys.exit("[-] No .dump file found.")

    out_dir = os.path.expanduser("~/projects/TiKick_OLD/results/replays")
    os.makedirs(out_dir, exist_ok=True)

    base = os.path.basename(dump_path).replace(".dump", "")
    output_path = args.output or os.path.join(out_dir, f"full_{base}.mp4")

    viz = GameReplayVisualizer(
        config_path=args.config,
        headless=(args.headless.lower() == "true"),
    )

    # Render full episode MP4
    goal_events = viz.render_dump(
        dump_path,
        output_path,
        limit=args.limit,
        fps=args.fps,
    )

    # Render goal highlight clips
    if args.highlights:
        highlights_dir = os.path.join(out_dir, "goal_highlights")
        os.makedirs(highlights_dir, exist_ok=True)
        viz.render_goal_highlights(dump_path, highlights_dir, fps=args.fps)

    viz.quit()
    print("[+] ALL DONE.")
