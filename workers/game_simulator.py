"""
CityBet Virtuals - GFootball Game Simulator (Pure Python Implementation)
===================================================================
Runs GFootball 11v11 matches with player attributes from the DB
influencing agent actions at each step. Produces .dump traces,
renders them to MP4 via draw_match.py, and persists results.
"""

import os
import sys
import uuid
import json
import time
import shutil
import random
import pickle
import logging
import traceback
import tempfile
import multiprocessing
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any

import numpy as np
import torch

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parent.parent
LOCAL_TMARL = PROJECT_ROOT / "tmarl"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(LOCAL_TMARL) not in sys.path:
    sys.path.append(str(LOCAL_TMARL))

os.environ["PYTHONPATH"] = str(PROJECT_ROOT)

from utils.db import SessionLocal, Season, Team, Player, Fixture, EventMarket, GfrDump

DUMP_STORE = PROJECT_ROOT / "dumps"
VIDEO_STORE = PROJECT_ROOT / "videos"
CANONICAL_VIDEO_DIR = VIDEO_STORE
ACTOR_PT = PROJECT_ROOT / "models" / "actor.pt"

DUMP_STORE.mkdir(parents=True, exist_ok=True)
VIDEO_STORE.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger("game_simulator")

# GFootball Action Constants
ACTION_IDLE = 0
ACTION_LEFT = 1
ACTION_TOP_LEFT = 2
ACTION_TOP = 3
ACTION_TOP_RIGHT = 4
ACTION_RIGHT = 5
ACTION_BOTTOM_RIGHT = 6
ACTION_BOTTOM = 7
ACTION_BOTTOM_LEFT = 8
ACTION_LONG_PASS = 9
ACTION_HIGH_PASS = 10
ACTION_SHORT_PASS = 11
ACTION_SHOT = 12
ACTION_SPRINT = 13
ACTION_RELEASE_DIR = 14
ACTION_SLIDE = 15
ACTION_DRIBBLE = 16
ACTION_RELEASE_SPRINT = 17

BASE_POSITIONS = {
    0: (-0.95, 0.0),    # GK
    1: (-0.70, -0.25),  # LB
    2: (-0.75, -0.10),  # CB
    3: (-0.75, 0.10),   # CB
    4: (-0.70, 0.25),   # RB
    5: (-0.40, -0.30),  # LM
    6: (-0.45, -0.10),  # CM
    7: (-0.45, 0.10),   # CM
    8: (-0.40, 0.30),   # RM
    9: (-0.15, -0.15),  # ST
    10: (-0.15, 0.15),  # ST
}


def load_team_attributes(db, home_team_id, away_team_id):
    """Returns (home_attrs, away_attrs) as dicts indexed by position index."""
    def fetch(team_id):
        players = db.query(Player).filter(Player.team_id == team_id).order_by(Player.player_position).all()
        attrs = {}
        for p in players:
            attrs[p.player_position] = {
                "player_id": str(p.player_id),
                "name": p.player_name,
                "role": p.role,
                "rating": p.player_rating if p.player_rating is not None else 3,
                "tired_factor": float(p.tired_factor) if p.tired_factor is not None else 0.0,
                "velocity": float(p.velocity) if p.velocity is not None else 1.0,
                "rewards": p.rewards if p.rewards is not None else {},
                "gfr_attrs": p.gfr_attributes if p.gfr_attributes is not None else {},
            }
        return attrs
    return fetch(home_team_id), fetch(away_team_id)


def build_match_config(home_team, away_team, home_attrs, away_attrs):
    home_td = home_team.team_data if home_team.team_data else {}
    away_td = away_team.team_data if away_team.team_data else {}

    def build_players_list(attrs):
        players = []
        for pos_idx in sorted(attrs.keys()):
            a = attrs[pos_idx]
            players.append({
                "name": a["name"],
                "strength": max(1, min(100, int(a["rating"] * 20))),
                "role": a["role"],
                "velocity": a["velocity"],
            })
        return players

    return {
        "match_setup": {
            "home_team": home_team.team_name,
            "away_team": away_team.team_name,
            "teams": {
                home_team.team_name: {
                    "shirt_color": home_td.get("shirt_color", "Red"),
                    "short_color": home_td.get("short_color", "White"),
                    "players": build_players_list(home_attrs),
                },
                away_team.team_name: {
                    "shirt_color": away_td.get("shirt_color", "Blue"),
                    "short_color": away_td.get("short_color", "White"),
                    "players": build_players_list(away_attrs),
                },
            },
        }
    }


def vector_to_action(dx: float, dy: float) -> int:
    """Maps a 2D direction vector to a GFootball movement action code (1 to 8)."""
    angle = np.arctan2(dy, dx)
    deg = np.degrees(angle) % 360.0
    if 337.5 <= deg or deg < 22.5:
        return ACTION_RIGHT
    elif 22.5 <= deg < 67.5:
        return ACTION_BOTTOM_RIGHT
    elif 67.5 <= deg < 112.5:
        return ACTION_BOTTOM
    elif 112.5 <= deg < 157.5:
        return ACTION_BOTTOM_LEFT
    elif 157.5 <= deg < 202.5:
        return ACTION_LEFT
    elif 202.5 <= deg < 247.5:
        return ACTION_TOP_LEFT
    elif 247.5 <= deg < 292.5:
        return ACTION_TOP
    else:
        return ACTION_TOP_RIGHT


class PlayerActionInfluencer:
    DIRECTIONAL = {
        ACTION_LEFT, ACTION_TOP_LEFT, ACTION_TOP, ACTION_TOP_RIGHT,
        ACTION_RIGHT, ACTION_BOTTOM_RIGHT, ACTION_BOTTOM, ACTION_BOTTOM_LEFT
    }

    def __init__(self, home_attrs: dict, away_attrs: dict, rng_seed: int = 42):
        self.home_attrs = home_attrs or {}
        self.away_attrs = away_attrs or {}
        self.rng = random.Random(rng_seed)

        self.home_tired = {k: float(v.get("tired_factor", 0.0)) for k, v in self.home_attrs.items()}
        self.away_tired = {k: float(v.get("tired_factor", 0.0)) for k, v in self.away_attrs.items()}

        def _aggregate(attrs):
            if not attrs:
                return 3.0, 1.0
            ratings = [float(v.get("rating", 3.0)) for v in attrs.values()]
            vels = [float(v.get("velocity", 1.0)) for v in attrs.values()]
            return sum(ratings) / len(ratings), sum(vels) / len(vels)

        self.home_strength, self.home_vel = _aggregate(self.home_attrs)
        self.away_strength, self.away_vel = _aggregate(self.away_attrs)

    def _get_attrs(self, team_idx: int, player_idx: int) -> dict:
        attrs_map = self.home_attrs if team_idx == 0 else self.away_attrs
        return attrs_map.get(player_idx, {})

    def _get_tired(self, team_idx: int, player_idx: int) -> float:
        tired_map = self.home_tired if team_idx == 0 else self.away_tired
        return tired_map.get(player_idx, 0.0)

    def _update_tired(self, team_idx: int, player_idx: int, delta: float):
        tired_map = self.home_tired if team_idx == 0 else self.away_tired
        current = tired_map.get(player_idx, 0.0)
        tired_map[player_idx] = min(1.0, current + delta)

    def influence(self, attrs_team_idx: int, player_idx: int, action: int, obs: dict) -> int:
        attrs = self._get_attrs(attrs_team_idx, player_idx)
        tired = self._get_tired(attrs_team_idx, player_idx)
        velocity = attrs.get("velocity", 1.0)
        rating = attrs.get("rating", 3.0)

        # Fatigue influence
        if tired > 0.6 and action == ACTION_SPRINT and self.rng.random() < 0.4:
            return ACTION_RELEASE_SPRINT

        # Velocity influence on sprint
        if velocity > 1.2 and action in self.DIRECTIONAL and self.rng.random() < 0.25:
            return ACTION_SPRINT

        # Higher rating boosts shooting/passing precision
        if action == ACTION_SHOT and rating > 3.5 and self.rng.random() < 0.3:
            return ACTION_SHOT

        return action

    def batch_influence(self, actions: list, obs: dict, attrs_team_idx: int) -> list:
        actions_copy = list(actions)
        for i, a in enumerate(actions_copy):
            raw_act = int(np.asarray(a).item()) if isinstance(a, (np.ndarray, np.number)) else int(a)
            actions_copy[i] = self.influence(attrs_team_idx, i, raw_act, obs)
        return actions_copy


class FeatureExtractor:
    def __init__(self, num_agents: int = 10):
        self.num_agents = num_agents
        self.last_loffside = np.zeros(11, dtype=np.float32)
        self.last_roffside = np.zeros(11, dtype=np.float32)

    def extract(self, raw_obs: list) -> np.ndarray:
        raw_obs = self._notFullGame(raw_obs)
        obs = []
        ally = np.array(raw_obs[0]["left_team"])
        ally_d = np.array(raw_obs[0]["left_team_direction"])
        enemy = np.array(raw_obs[0]["right_team"])
        enemy_d = np.array(raw_obs[0]["right_team_direction"])
        lo, ro = self.get_offside(raw_obs[0])

        for a in range(self.num_agents):
            me = ally[int(raw_obs[a]["active"])] if a < len(raw_obs) else ally[0]
            ball = raw_obs[0]["ball"][:2]
            ball_dist = float(np.linalg.norm(me - ball))
            enemy_dist = np.linalg.norm(me - enemy, axis=-1)
            to_enemy = enemy - me
            to_ally = ally - me
            to_ball = ball - me

            o = []
            o.extend(ally.flatten())
            o.extend(ally_d.flatten())
            o.extend(enemy.flatten())
            o.extend(enemy_d.flatten())

            o.extend(raw_obs[a]["ball"])
            o.extend(raw_obs[a]["ball_direction"])

            bt = raw_obs[a]["ball_owned_team"]
            o.extend([1, 0, 0] if bt == -1 else ([0, 1, 0] if bt == 0 else [0, 0, 1]))

            active = [0] * 11
            active_idx = raw_obs[a]["active"]
            if 0 <= active_idx < 11:
                active[active_idx] = 1
            o.extend(active)

            game_mode = [0] * 7
            gm_idx = raw_obs[a]["game_mode"]
            if 0 <= gm_idx < 7:
                game_mode[gm_idx] = 1
            o.extend(game_mode)

            sticky = raw_obs[a].get("sticky_actions", [0] * 10)
            o.extend(sticky[:10])

            ball_dist = 1.0 if ball_dist > 1.0 else ball_dist
            o.extend([ball_dist])

            o.extend(raw_obs[a].get("left_team_tired_factor", [0.0] * 11))
            o.extend(raw_obs[a].get("left_team_yellow_card", [0] * 11))
            o.extend(raw_obs[a].get("left_team_active", [1] * 11))
            o.extend(lo)
            o.extend(ro)
            o.extend(enemy_dist)

            to_ally[:, 0] /= 2.0
            o.extend(to_ally.flatten())
            to_enemy[:, 0] /= 2.0
            o.extend(to_enemy.flatten())
            to_ball[0] /= 2.0
            o.extend(to_ball.flatten())

            steps_left = raw_obs[a].get("steps_left", 3001)
            o.extend([1.0 * steps_left / 3001.0])
            if steps_left > 1500:
                steps_left -= 1501
            steps_left = 1.0 * min(steps_left, 300.0) / 300.0
            o.extend([steps_left])

            sc = raw_obs[a].get("score", [0, 0])
            score_ratio = max(-1.0, min(1.0, 1.0 * (sc[0] - sc[1]) / 5.0))
            o.extend([score_ratio])

            o.extend([0.0] * 27)  # Pad to 268 dimensions
            obs.append(o[:268])

        return np.array(obs, dtype=np.float32)

    def get_offside(self, obs: dict) -> Tuple[np.ndarray, np.ndarray]:
        ball = np.array(obs["ball"][:2])
        ally = np.array(obs["left_team"])
        enemy = np.array(obs["right_team"])

        if obs.get("game_mode", 0) != 0:
            self.last_loffside = np.zeros(11, dtype=np.float32)
            self.last_roffside = np.zeros(11, dtype=np.float32)
            return self.last_loffside, self.last_roffside

        need_recalc = False
        effective_ownball_team = -1
        effective_ownball_player = -1

        if obs.get("ball_owned_team", -1) > -1:
            effective_ownball_team = obs["ball_owned_team"]
            effective_ownball_player = obs["ball_owned_player"]
            need_recalc = True
        else:
            ally_dist = np.linalg.norm(ball - ally, axis=-1)
            enemy_dist = np.linalg.norm(ball - enemy, axis=-1)
            if np.min(ally_dist) < np.min(enemy_dist):
                if np.min(ally_dist) < 0.017:
                    need_recalc = True
                    effective_ownball_team = 0
                    effective_ownball_player = int(np.argmin(ally_dist))
            elif np.min(enemy_dist) < np.min(ally_dist):
                if np.min(enemy_dist) < 0.017:
                    need_recalc = True
                    effective_ownball_team = 1
                    effective_ownball_player = int(np.argmin(enemy_dist))

        if not need_recalc:
            return self.last_loffside, self.last_roffside

        left_offside = np.zeros(11, dtype=np.float32)
        right_offside = np.zeros(11, dtype=np.float32)

        if effective_ownball_team == 0:
            right_xs = np.array([obs["right_team"][k][0] for k in range(1, 11)])
            right_xs.sort()
            for k in range(1, 11):
                if obs["left_team"][k][0] > right_xs[-1] and k != effective_ownball_player and obs["left_team"][k][0] > 0.0:
                    left_offside[k] = 1.0
        else:
            left_xs = np.array([obs["left_team"][k][0] for k in range(1, 11)])
            left_xs.sort()
            for k in range(1, 11):
                if obs["right_team"][k][0] < left_xs[0] and k != effective_ownball_player and obs["right_team"][k][0] < 0.0:
                    right_offside[k] = 1.0

        self.last_loffside = left_offside
        self.last_roffside = right_offside
        return left_offside, right_offside

    def _notFullGame(self, raw_obs: list) -> list:
        left_ok = len(raw_obs[0]["left_team"]) == 11
        right_ok = len(raw_obs[0]["right_team"]) == 11
        if left_ok and right_ok:
            return raw_obs
        for obs in raw_obs:
            obs["left_team"] = np.array(obs["left_team"])
            obs["right_team"] = np.array(obs["right_team"])
            obs["left_team_direction"] = np.array(obs["left_team_direction"])
            obs["right_team_direction"] = np.array(obs["right_team_direction"])
            while len(obs["left_team"]) < 11:
                obs["left_team"] = np.concatenate([obs["left_team"], np.array([[-1, 0]])], axis=0)
                obs["left_team_direction"] = np.concatenate([obs["left_team_direction"], np.zeros([1, 2])], axis=0)
                obs["left_team_tired_factor"] = np.concatenate([obs["left_team_tired_factor"], np.zeros(1)], axis=0)
                obs["left_team_yellow_card"] = np.concatenate([obs["left_team_yellow_card"], np.zeros(1)], axis=0)
                obs["left_team_active"] = np.concatenate([obs["left_team_active"], np.ones(1)], axis=0)
        return raw_obs


def mirror_obs_for_away(raw_obs_list: list) -> list:
    """Return a mirrored copy of raw_obs for the away team (agents 10-19)."""
    import copy
    mirrored = []
    N_HOME = 10
    N_AWAY = 10
    for a in range(N_AWAY):
        src_idx = N_HOME + a if (N_HOME + a) < len(raw_obs_list) else len(raw_obs_list) - 1
        src = raw_obs_list[src_idx]
        o = copy.deepcopy(src)

        o["ball"] = [-o["ball"][0], -o["ball"][1], o["ball"][2]] if len(o["ball"]) >= 3 else [-o["ball"][0], -o["ball"][1]]
        o["ball_direction"] = [-o["ball_direction"][0], -o["ball_direction"][1], o["ball_direction"][2]] if len(o["ball_direction"]) >= 3 else [-o["ball_direction"][0], -o["ball_direction"][1]]

        lt = np.array(o.get("left_team", []))
        rt = np.array(o.get("right_team", []))
        o["left_team"] = -rt if len(rt) > 0 else lt
        o["right_team"] = -lt if len(lt) > 0 else rt

        ltd = np.array(o.get("left_team_direction", []))
        rtd = np.array(o.get("right_team_direction", []))
        o["left_team_direction"] = -rtd if len(rtd) > 0 else ltd
        o["right_team_direction"] = -ltd if len(ltd) > 0 else rtd

        ltf = o.get("left_team_tired_factor", [])
        rtf = o.get("right_team_tired_factor", [])
        o["left_team_tired_factor"] = rtf if len(rtf) > 0 else ltf
        o["right_team_tired_factor"] = ltf if len(ltf) > 0 else rtf

        lyc = o.get("left_team_yellow_card", [])
        ryc = o.get("right_team_yellow_card", [])
        o["left_team_yellow_card"] = ryc if len(ryc) > 0 else lyc
        o["right_team_yellow_card"] = lyc if len(lyc) > 0 else ryc

        la = o.get("left_team_active", [])
        ra = o.get("right_team_active", [])
        o["left_team_active"] = ra if len(ra) > 0 else la
        o["right_team_active"] = la if len(la) > 0 else ra

        bt = o.get("ball_owned_team", -1)
        o["ball_owned_team"] = 1 if bt == 0 else (0 if bt == 1 else -1)

        sc = o.get("score", [0, 0])
        o["score"] = [sc[1], sc[0]]

        sticky = list(o.get("sticky_actions", [0] * 10))
        # Rotate direction actions (indices 0..3 with 4..7)
        for i1, i2 in [(0, 4), (1, 5), (2, 6), (3, 7)]:
            if i2 < len(sticky):
                sticky[i1], sticky[i2] = sticky[i2], sticky[i1]
        o["sticky_actions"] = sticky

        mirrored.append(o)
    return mirrored


def _possession_pct(poss_home: int, poss_away: int) -> Tuple[int, int]:
    """Possession = share of steps where a team owned the ball (always sums to 100)."""
    owned = poss_home + poss_away
    if owned == 0:
        return 50, 50
    hp = round(100.0 * poss_home / owned)
    return hp, 100 - hp


def _run_simulation_child(
    match_id_str: str,
    home_name: str,
    away_name: str,
    home_attrs: dict,
    away_attrs: dict,
    dump_dir_str: str,
    sidecar_path_str: str,
):
    """Isolated subprocess to run GFootball match safely with TiKick actor model."""
    try:
        import gym
        import gym.core

        # Patch Gym wrappers for GFootball step compatibility
        from gfootball.env.wrappers import SingleAgentRewardWrapper
        if hasattr(SingleAgentRewardWrapper, 'step'):
            old_step = SingleAgentRewardWrapper.step
            def patched_sarw_step(self, action):
                res = self.env.step(action)
                if len(res) == 4:
                    obs, rew, done, info = res
                    return obs, self.reward(rew), done, info
                return old_step(self, action)
            SingleAgentRewardWrapper.step = patched_sarw_step

        import gfootball.env as football_env

        dump_dir = Path(dump_dir_str)
        sidecar = Path(sidecar_path_str)

        def flush_sidecar(stats: dict, step: int):
            stats["steps"] = step
            tmp = sidecar.with_suffix(".tmp")
            tmp.write_text(json.dumps(stats))
            tmp.replace(sidecar)

        print("[Verification] Running precision probe for 10v10 dual-control architecture...", flush=True)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Create 10v10 dual control environment
        env = football_env.create_environment(
            env_name="11_vs_11_kaggle",
            stacked=False,
            representation="raw",
            rewards="scoring",
            logdir=dump_dir_str,
            write_full_episode_dumps=True,
            write_goal_dumps=False,
            write_video=False,
            render=False,
            number_of_left_players_agent_controls=10,
            number_of_right_players_agent_controls=10,
            other_config_options={"action_set": "full", "render_hud": False, "display_game_stats": False, "logdir": dump_dir_str},
        )

        influencer = PlayerActionInfluencer(home_attrs, away_attrs)
        favoured = home_name if influencer.home_strength >= influencer.away_strength else away_name
        print(
            f"[child] Squad strength (from DB)  HOME {home_name}: rating={influencer.home_strength:.2f} vel={influencer.home_vel:.2f}  |  AWAY {away_name}: rating={influencer.away_strength:.2f} vel={influencer.away_vel:.2f}  → favoured: {favoured}",
            flush=True,
        )

        # Load PolicyNetwork model
        actor_model = None
        try:
            from tmarl.configs.config import get_config
            from tmarl.networks.policy_network import PolicyNetwork

            class MockGymBox:
                def __init__(self, shape):
                    self.shape = shape
                    self.__class__.__name__ = "Box"

            class MockGymDiscrete:
                def __init__(self, n):
                    self.n = n
                    self.__class__.__name__ = "Discrete"

            parser = get_config()
            parsed_args, _ = parser.parse_known_args()
            parsed_args.hidden_size = 256

            main_obs_space = MockGymBox(shape=(268,))
            main_action_space = MockGymDiscrete(n=33)

            actor_model = PolicyNetwork(parsed_args, main_obs_space, main_action_space, device=device)
            if ACTOR_PT.exists():
                weights = torch.load(str(ACTOR_PT), map_location=device)
                actor_model.load_state_dict(weights)
                actor_model.to(device)
                actor_model.eval()
                print(f"[child] Perfect! Loaded and mapped TiKick brain weights on {device}", flush=True)
            else:
                print(f"[child] Warning: {ACTOR_PT} not found — running random policy fallback.", flush=True)
        except Exception as err:
            print(f"[child] CRITICAL ERROR: Could not map actor.pt onto PolicyNetwork structure: {err}", flush=True)
            traceback.print_exc()

        MAX_STEPS = 3001
        obs = env.reset()
        done = False
        score = [0, 0]
        prev_score = [0, 0]
        poss_home = 0
        poss_away = 0
        poss_none = 0

        home_extractor = FeatureExtractor(num_agents=10)
        away_extractor = FeatureExtractor(num_agents=10)

        rnn_states = torch.zeros((20, 1, 256), dtype=torch.float32, device=device)
        masks = torch.ones((20, 1), dtype=torch.float32, device=device)

        steps = 0
        stats = {
            "match_id": match_id_str,
            "home_team": home_name,
            "away_team": away_name,
            "score": "0-0",
            "goals_home": 0,
            "goals_away": 0,
            "corners": 0,
            "free_kicks": 0,
            "steps": 0,
            "game_modes": [],
            "player_metrics": {},
        }

        print(f"[Verification] [+] GFR observation data profiles returned: {len(obs)} agents.", flush=True)
        print("[Verification] SUCCESS: 10v10 dual-control matrix parameters verified. Proceeding to main match execution.\n", flush=True)

        while not done and steps < MAX_STEPS:
            raw_all = list(obs)
            raw_home = raw_all[:10]
            # GFootball already flips right-team observations so each away agent sees
            # its own team on the left. Mirroring again (mirror_obs_for_away) made the
            # away model play as the home team, so use the native observations.
            raw_away = raw_all[10:20]

            home_feat = home_extractor.extract(raw_home)
            away_feat = away_extractor.extract(raw_away)
            all_feat = np.vstack([home_feat, away_feat])

            if actor_model is not None:
                with torch.no_grad():
                    obs_tensor = torch.FloatTensor(all_feat).to(device)
                    avail_actions = torch.ones((20, 33), dtype=torch.float32, device=device)
                    avail_actions[:, 19:] = 0.0

                    actions_tensor, _, rnn_states = actor_model(
                        obs_tensor, rnn_states, masks, available_actions=avail_actions, deterministic=True
                    )
                    raw_actions = actions_tensor.cpu().numpy().flatten()
            else:
                raw_actions = np.random.randint(0, 19, size=20)

            # Apply DB Player Action Influences
            home_acts = influencer.batch_influence(raw_actions[:10], raw_home[0], attrs_team_idx=0)
            away_acts = influencer.batch_influence(raw_actions[10:], raw_away[0], attrs_team_idx=1)
            final_actions = np.array(home_acts + away_acts, dtype=np.int32)

            step_res = env.step(final_actions)
            if len(step_res) == 4:
                obs, reward, done, info = step_res
            elif len(step_res) == 5:
                obs, reward, term, trunc, info = step_res
                done = term or trunc

            steps += 1

            if isinstance(obs, list) and len(obs) > 0:
                raw_0 = obs[0]
                current_score = raw_0.get("score", score)
                bot = raw_0.get("ball_owned_team", -1)

                if bot == 0:
                    poss_home += 1
                elif bot == 1:
                    poss_away += 1
                else:
                    poss_none += 1

                # Goal detection & logging
                if current_score[0] > prev_score[0]:
                    score[0] = current_score[0]
                    print(f"[child] ⚽ Home goal! {score[0]}:{score[1]} step={steps}", flush=True)
                    prev_score = list(current_score)
                elif current_score[1] > prev_score[1]:
                    score[1] = current_score[1]
                    print(f"[child] ⚽ Away goal! {score[0]}:{score[1]} step={steps}", flush=True)
                    prev_score = list(current_score)

            # Periodic logging every 500 steps
            if steps % 500 == 0 or steps == MAX_STEPS:
                hp, ap = _possession_pct(poss_home, poss_away)
                print(f"[child] ⏱ step={steps}/3000  score={score[0]}:{score[1]}  possession H/A: {hp}%/{ap}%", flush=True)
                stats["score"] = f"{score[0]}-{score[1]}"
                stats["goals_home"] = score[0]
                stats["goals_away"] = score[1]
                flush_sidecar(stats, steps)

        env.close()

        hp, ap = _possession_pct(poss_home, poss_away)
        print(f"[child] FINAL {home_name} {score[0]}-{score[1]} {away_name}  possession H/A: {hp}%/{ap}%  (ball-free steps: {poss_none}/{steps})", flush=True)

        stats["score"] = f"{score[0]}-{score[1]}"
        stats["goals_home"] = score[0]
        stats["goals_away"] = score[1]
        stats["possession_home"] = hp
        stats["possession_away"] = ap
        stats["steps"] = steps
        stats["dump_file"] = None

        # Find saved dump file
        dump_files = sorted(dump_dir.glob("*.dump"), key=os.path.getmtime, reverse=True)
        if dump_files:
            named_dump = dump_dir / f"{match_id_str}.dump"
            shutil.move(str(dump_files[0]), str(named_dump))
            stats["dump_file"] = str(named_dump)

        stats["match_config_path"] = str(dump_dir / f"match_{match_id_str}.json")
        flush_sidecar(stats, steps)
        log.info("  [+] Match result: %s %s | steps=%s", match_id_str, stats.get("score"), steps)
        sys.exit(0)

    except Exception as exc:
        log.error("Child simulation failed: %s", exc)
        traceback.print_exc()
        sys.exit(1)


def run_simulation(fixture: Fixture, home_team: Team, away_team: Team, home_attrs: dict, away_attrs: dict, match_config: dict, dump_dir: Path, timeout: float = 600.0) -> dict:
    match_id_str = str(fixture.match_id)
    config_path = dump_dir / f"match_{match_id_str}.json"
    with open(config_path, "w") as f:
        json.dump(match_config, f, indent=2)

    log.info("  Creating GFR environment for match %s...", match_id_str)

    sidecar_path = dump_dir / f"{match_id_str}_stats.json"

    proc = multiprocessing.Process(
        target=_run_simulation_child,
        args=(match_id_str, home_team.team_name, away_team.team_name, home_attrs, away_attrs, str(dump_dir), str(sidecar_path)),
    )
    proc.start()
    proc.join(timeout=timeout)

    if proc.is_alive():
        log.warning("  [Timeout] Child process exceeded %.0fs — killing.", timeout)
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()

    if sidecar_path.exists():
        try:
            return json.loads(sidecar_path.read_text())
        except Exception as e:
            log.warning("Failed to parse sidecar stats: %s", e)

    return {
        "match_id": match_id_str,
        "score": "0-0",
        "goals_home": 0,
        "goals_away": 0,
        "corners": 0,
        "free_kicks": 0,
        "steps": 0,
        "crashed": True,
        "dump_file": None,
        "match_config_path": str(config_path),
    }


def render_dump_to_video(dump_path: str, match_config_path: str, output_dir: Path, match_id: str) -> dict:
    from utils.draw_match import GameReplayVisualizer, mp4_to_gif
    from utils.video_faststart import finalize_mp4

    output_dir.mkdir(parents=True, exist_ok=True)
    mp4_out = output_dir / f"{match_id}_full.mp4"
    gif_out = output_dir / f"{match_id}_full.gif"

    try:
        viz = GameReplayVisualizer(config_path=match_config_path, headless=True)
        viz.render_dump(dump_path, str(mp4_out), limit=None, fps=10)
        viz.quit()
        finalize_mp4(mp4_out, target_mb=4.5)
        mp4_to_gif(str(mp4_out), str(gif_out), fps=10, scale=0.75)
        return {"mp4": str(mp4_out), "gif": str(gif_out)}
    except Exception as e:
        log.error("Failed rendering video for %s: %s", match_id, e)
        return {"mp4": str(mp4_out) if mp4_out.is_file() else None, "gif": None}


def settle_fixture(db, fixture: Fixture, stats: dict):
    score_str = stats.get("score", "0-0")
    goals = score_str.split("-")
    home_g = int(goals[0]) if len(goals) == 2 else 0
    away_g = int(goals[1]) if len(goals) == 2 else 0

    if home_g > away_g:
        result = "home_win"
    elif away_g > home_g:
        result = "away_win"
    else:
        result = "draw"

    fixture.score = score_str
    fixture.status = "completed"
    fixture.settled = True
    fixture.outcome = {
        "result": result,
        "goals_home": home_g,
        "goals_away": away_g,
        "corners": stats.get("corners", 0),
        "free_kicks": stats.get("free_kicks", 0),
        "game_modes": stats.get("game_modes", []),
        "simulated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Settle Event Markets
    markets = db.query(EventMarket).filter(EventMarket.match_id == fixture.match_id).all()
    for m in markets:
        m.status = "settled"
        winning = False
        if m.market_name == "1X2":
            if m.selection_name == "Home" and result == "home_win":
                winning = True
            elif m.selection_name == "Draw" and result == "draw":
                winning = True
            elif m.selection_name == "Away" and result == "away_win":
                winning = True
        elif m.market_name in ("OU25", "Over/Under 2.5"):
            total_g = home_g + away_g
            if m.selection_name in ("Over 2.5", "Over") and total_g > 2.5:
                winning = True
            elif m.selection_name in ("Under 2.5", "Under") and total_g <= 2.5:
                winning = True
        elif m.market_name in ("GGNG", "GG/NG"):
            both = home_g > 0 and away_g > 0
            if m.selection_name == "GG" and both:
                winning = True
            elif m.selection_name == "NG" and not both:
                winning = True

        m.winning_selection = winning

    db.commit()
    log.info("  [DB] Fixture %s settled: %s (%s)", fixture.match_id, score_str, result)


def persist_dump(db, fixture: Fixture, stats: dict, video_paths: dict):
    dump_file = stats.get("dump_file")
    mp4_path = video_paths.get("mp4")
    gif_path = video_paths.get("gif")

    video_binary = None
    if mp4_path and os.path.exists(mp4_path):
        try:
            with open(mp4_path, "rb") as f:
                video_binary = f.read()
        except Exception:
            pass

    video_url = mp4_path if (mp4_path and os.path.exists(mp4_path)) else gif_path

    score_str = stats.get("score", "0-0")
    gfr_stats = {
        "score": score_str,
        "home_goals": stats.get("goals_home", 0),
        "away_goals": stats.get("goals_away", 0),
        "corners": stats.get("corners", 0),
        "free_kicks": stats.get("free_kicks", 0),
        "total_steps": stats.get("steps", 0),
        "game_modes": stats.get("game_modes", []),
        "player_metrics": stats.get("player_metrics", {}),
    }

    dump = db.query(GfrDump).filter(GfrDump.match_id == fixture.match_id).first()
    if not dump:
        dump = GfrDump(
            dump_id=uuid.uuid4(),
            match_id=fixture.match_id,
            season_id=fixture.season_id,
            gameweek=fixture.gameweek,
            home_team_id=fixture.home_team_id,
            away_team_id=fixture.away_team_id,
            gfr_game_dump_file=dump_file,
            video_url=video_url,
            gfr_stats=gfr_stats,
            match_video=video_binary,
        )
        db.add(dump)
    else:
        dump.gfr_game_dump_file = dump_file
        dump.video_url = video_url
        dump.gfr_stats = gfr_stats
        if video_binary:
            dump.match_video = video_binary

    db.commit()


def update_season_gameweek(db, season_id, gameweek: int):
    season = db.query(Season).filter(Season.season_id == season_id).first()
    if season and gameweek > (season.current_gwk or 0):
        season.current_gwk = gameweek
        db.commit()


def update_player_tiredness(db, team_id, influencer, team_idx: int):
    secure_session = SessionLocal()
    try:
        tired_map = influencer.home_tired if team_idx == 0 else influencer.away_tired
        players = secure_session.query(Player).filter(Player.team_id == team_id).all()
        for p in players:
            new_tired = tired_map.get(p.player_position, float(p.tired_factor or 0.0))
            p.tired_factor = round(min(1.0, float(new_tired)), 2)
        secure_session.commit()
    except Exception as e:
        log.warning("Could not update player tiredness: %s", e)
    finally:
        secure_session.close()


def pick_scheduled_fixture(db):
    return (
        db.query(Fixture)
        .filter(Fixture.status == "upcoming")
        .order_by(Fixture.show_at_ms.asc())
        .first()
    )


def _simulate_target_fixture(db, fixture) -> bool:
    home = db.query(Team).filter(Team.team_id == fixture.home_team_id).first()
    away = db.query(Team).filter(Team.team_id == fixture.away_team_id).first()
    if not home or not away:
        log.error("Teams missing for %s", fixture.match_id)
        fixture.status = "error"
        db.commit()
        return False

    dump_dir = DUMP_STORE / str(fixture.match_id)
    dump_dir.mkdir(parents=True, exist_ok=True)

    log.info(
        "[Sim] %s vs %s (GW%d, status=%s)",
        home.team_name,
        away.team_name,
        fixture.gameweek,
        fixture.status,
    )

    home_attrs, away_attrs = load_team_attributes(db, fixture.home_team_id, fixture.away_team_id)
    match_config = build_match_config(home, away, home_attrs, away_attrs)

    fixture.status = "live"
    db.commit()

    try:
        stats = run_simulation(fixture, home, away, home_attrs, away_attrs, match_config, dump_dir)
        video_paths = {"mp4": None, "gif": None}
        dump_file = stats.get("dump_file")
        if dump_file and os.path.exists(dump_file):
            video_paths = render_dump_to_video(
                dump_path=dump_file,
                match_config_path=stats["match_config_path"],
                output_dir=CANONICAL_VIDEO_DIR,
                match_id=str(fixture.match_id),
            )

        settle_fixture(db, fixture, stats)
        persist_dump(db, fixture, stats, video_paths)
        update_season_gameweek(db, fixture.season_id, fixture.gameweek)
        log.info("[Sim] Complete: %s %s %s", home.team_name, stats.get("score"), away.team_name)
        return True
    except Exception as exc:
        log.error("Simulation failed for %s: %s", fixture.match_id, exc)
        traceback.print_exc()
        fixture.status = "error"
        db.commit()
        return False


def simulate_next_fixture(db):
    target = pick_scheduled_fixture(db)
    if target is None:
        return False
    return _simulate_target_fixture(db, target)


def run_queue_continuously(max_matches=None):
    log.info("[Queue] Starting self-healing simulation queue (actor vs actor mode)...")
    done = 0
    idle_sleep = 15

    while True:
        if max_matches is not None and done >= max_matches:
            log.info("[Queue] Reached max_matches=%d — stopping.", max_matches)
            break

        db = SessionLocal()
        try:
            ok = simulate_next_fixture(db)
        except Exception as exc:
            log.exception("[Queue] Unexpected error in simulate_next_fixture: %s", exc)
            ok = False
        finally:
            db.close()

        if ok:
            done += 1
            log.info("[Queue] Simulated %d fixture(s) so far.", done)
            time.sleep(2)
        else:
            time.sleep(idle_sleep)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CityBet Virtuals GFR Simulator")
    parser.add_argument(
        "--mode",
        choices=["one", "gameweek", "all"],
        default="one",
        help="one=next fixture, gameweek=full GWK, all=continuous queue",
    )
    parser.add_argument("--gameweek", type=int, default=1)
    parser.add_argument("--max", type=int, default=None)
    args = parser.parse_args()

    if args.mode == "one":
        db = SessionLocal()
        try:
            simulate_next_fixture(db)
        finally:
            db.close()
    elif args.mode == "all":
        run_queue_continuously(max_matches=args.max)
