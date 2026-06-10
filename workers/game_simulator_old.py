"""
CityBet Virtuals - GFootball Game Simulator
============================================
Runs GFootball 11v11 matches with player attributes from the DB
influencing agent actions at each step. Produces .dump traces,
renders them to MP4/GIF via draw_match.py, and persists results.

Sequential queue: 1 match at a time (easy to scale later with Celery).
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
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import torch

# ─── workspace paths ───────────────────────────────────────────────
"""PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIKICK_ROOT  = Path("/home/Warta/projects/TiKick_OLD")
DRAWS_SCRIPT = TIKICK_ROOT / "scripts" / "football" / "draw_match.py"
ACTOR_PT     = TIKICK_ROOT / "models" / "11_vs_11_kaggle" / "actor.pt"
DUMP_STORE   = PROJECT_ROOT / "dumps"
VIDEO_STORE  = PROJECT_ROOT / "videos"
DUMP_STORE.mkdir(parents=True, exist_ok=True)
VIDEO_STORE.mkdir(parents=True, exist_ok=True)

# ─── Python path bootstrap ──────────────────────────────────────────
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(TIKICK_ROOT))"""

# ─── workspace paths ───────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DUMP_STORE   = PROJECT_ROOT / "dumps"
VIDEO_STORE  = PROJECT_ROOT / "videos"

# Point directly to your new local project copies
ACTOR_PT     = PROJECT_ROOT / "models" / "11_vs_11_kaggle" / "actor.pt"

DUMP_STORE.mkdir(parents=True, exist_ok=True)
VIDEO_STORE.mkdir(parents=True, exist_ok=True)

# ─── Python path bootstrap ──────────────────────────────────────────
sys.path.insert(0, str(PROJECT_ROOT))
# This lets Python find your local 'tmarl' folder immediately
sys.path.insert(0, str(PROJECT_ROOT / "tmarl"))

from utils.db import SessionLocal, Season, Team, Player, Fixture, EventMarket, GfrDump

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("game_simulator")


# ════════════════════════════════════════════════════════════════════
#  GFR action codes (matches gfootball action_set_full indices)
# ════════════════════════════════════════════════════════════════════
ACTION_IDLE        = 0
ACTION_LEFT        = 1
ACTION_TOP_LEFT    = 2
ACTION_TOP         = 3
ACTION_TOP_RIGHT   = 4
ACTION_RIGHT       = 5
ACTION_BOTTOM_RIGHT= 6
ACTION_BOTTOM      = 7
ACTION_BOTTOM_LEFT = 8
ACTION_LONG_PASS   = 9
ACTION_HIGH_PASS   = 10
ACTION_SHORT_PASS  = 11
ACTION_SHOT        = 12
ACTION_SPRINT      = 13
ACTION_RELEASE_DIR = 14
ACTION_SLIDE       = 15
ACTION_DRIBBLE     = 16
ACTION_RELEASE_SPRINT = 17


# ════════════════════════════════════════════════════════════════════
#  Player attribute loader
# ════════════════════════════════════════════════════════════════════

def load_team_attributes(db, home_team_id, away_team_id):
    """
    Returns (home_attrs, away_attrs) as dicts indexed by position index.
    Each entry: {name, role, rating, tired_factor, velocity, rewards, gfr_attributes}
    """
    def fetch(team_id):
        players = db.query(Player).filter(Player.team_id == team_id).order_by(Player.player_position).all()
        attrs = {}
        for p in players:
            attrs[p.player_position] = {
                "player_id":    str(p.player_id),
                "name":         p.player_name,
                "role":         p.role,
                "rating":       p.player_rating or 3,
                "tired_factor": float(p.tired_factor or 0.0),
                "velocity":     float(p.velocity or 1.0),
                "rewards":      p.rewards or {},
                "gfr_attrs":    p.gfr_attributes or {},
            }
        return attrs

    return fetch(home_team_id), fetch(away_team_id)


# ════════════════════════════════════════════════════════════════════
#  Player Action Influencer
# ════════════════════════════════════════════════════════════════════

class PlayerActionInfluencer:
    """
    Intercepts the policy's raw action for each agent and adjusts it
    based on the player's skill attributes fetched from the DB.

    Influencer rules:
      1. Tiredness  – if tired_factor > 0.7, there's a (tired_factor * 40)%
                      chance to cancel a sprint and revert to idle.
      2. Velocity   – if player's velocity > 1.15 and ball is nearby,
                      inject ACTION_SPRINT after a non-sprint directional move.
      3. Shooting   – if shooting_reward > 1.0 and action is SHOT, there is
                      an additional probability (rating/5) of keeping the shot;
                      weaker shooters with low shooting_reward may divert to pass.
      4. Defense    – if defense_reward > 1.0 and the ball is in this team's
                      half and an opponent is close, inject a slide tackle.
      5. Passing    – if passing_reward > 1.2 and role is CM/AM/LM/RM,
                      substitute long_pass → short_pass for better accuracy.
    """

    def __init__(self, home_attrs: dict, away_attrs: dict, rng_seed: int = 42):
        self.home_attrs = home_attrs
        self.away_attrs = away_attrs
        self.rng = random.Random(rng_seed)
        # Rolling tired_factor that accumulates during the game
        self.home_tired = {k: v["tired_factor"] for k, v in home_attrs.items()}
        self.away_tired = {k: v["tired_factor"] for k, v in away_attrs.items()}

    def _get_attrs(self, team_idx: int, player_idx: int) -> Optional[dict]:
        attrs_map = self.home_attrs if team_idx == 0 else self.away_attrs
        return attrs_map.get(player_idx)

    def _get_tired(self, team_idx: int, player_idx: int) -> float:
        tired_map = self.home_tired if team_idx == 0 else self.away_tired
        return tired_map.get(player_idx, 0.0)

    def _update_tired(self, team_idx: int, player_idx: int, delta: float):
        tired_map = self.home_tired if team_idx == 0 else self.away_tired
        current = tired_map.get(player_idx, 0.0)
        tired_map[player_idx] = min(1.0, current + delta)

    def influence(self, team_idx: int, player_idx: int, action: int, obs: dict) -> int:
        """
        Main influencer entry point. Returns the (possibly overridden) action.
        """
        attrs = self._get_attrs(team_idx, player_idx)
        if not attrs:
            return action

        tired = self._get_tired(team_idx, player_idx)
        rewards = attrs.get("rewards", {})
        velocity = attrs.get("velocity", 1.0)
        rating = attrs.get("rating", 3)
        role = attrs.get("role", "CM")

        # ── 1. Tiredness: cancel sprints ──────────────────────────────
        if action == ACTION_SPRINT and tired > 0.7:
            cancel_prob = (tired - 0.7) * 3.33  # 0→33% at 0.8, ~100% at 1.0
            if self.rng.random() < cancel_prob:
                self._update_tired(team_idx, player_idx, 0.002)
                return ACTION_IDLE

        # Accumulate tiredness on sprint actions
        if action == ACTION_SPRINT:
            self._update_tired(team_idx, player_idx, 0.003)

        # ── 2. Velocity boost: inject sprint on directional moves ──────
        directional = {ACTION_LEFT, ACTION_TOP_LEFT, ACTION_TOP, ACTION_TOP_RIGHT,
                       ACTION_RIGHT, ACTION_BOTTOM_RIGHT, ACTION_BOTTOM, ACTION_BOTTOM_LEFT}
        if action in directional and velocity > 1.15 and tired < 0.6:
            if self.rng.random() < 0.55:
                return ACTION_SPRINT

        # ── 3. Shooting influence ─────────────────────────────────────
        shooting_reward = rewards.get("shooting_reward", 0.0)
        if action == ACTION_SHOT:
            if shooting_reward >= 1.0:
                # Good shooters keep their shot intent
                if self.rng.random() > (rating / 5.0) * 0.2:
                    return ACTION_SHOT
            elif shooting_reward < 0.5:
                # Poor shooters (deep midfielders) might switch to pass
                if self.rng.random() < 0.45:
                    return ACTION_SHORT_PASS

        # ── 4. Defense intercept: slide if defending well ─────────────
        defense_reward = rewards.get("defense_reward", 0.0)
        if action == ACTION_IDLE and defense_reward > 1.0:
            # ball from GFR raw obs is a numpy array [x, y, z]
            ball = obs.get("ball", None)
            ball_x = float(ball[0]) if ball is not None and len(ball) > 0 else 0.0
            is_home = team_idx == 0
            # If ball is in own half
            in_own_half = ball_x < 0 if is_home else ball_x > 0
            if in_own_half and self.rng.random() < defense_reward * 0.25:
                return ACTION_SLIDE

        # ── 5. Passing quality: CM/AM prefers short over long ─────────
        passing_reward = rewards.get("passing_reward", 0.0)
        if action == ACTION_LONG_PASS and passing_reward > 1.2:
            if role in ("CM", "AM", "LM", "RM") and self.rng.random() < 0.6:
                return ACTION_SHORT_PASS

        return action

    def batch_influence(self, actions: np.ndarray, obs: dict, team_idx: int) -> np.ndarray:
        """
        Applies influence to a full team's action array of shape [n_players].
        """
        influenced = actions.copy()
        for player_idx, raw_action in enumerate(actions):
            influenced[player_idx] = self.influence(team_idx, player_idx, int(np.asarray(raw_action).item()), obs)
        return influenced


    # ════════════════════════════════════════════════════════════════════
    # DUAL-CONTROL MECHANICAL FEASIBILITY RUN
    # ════════════════════════════════════════════════════════════════════
    print("[Verification] Running precision probe for 10v10 dual-control architecture...", flush=True)
    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Test 1: Can we map the brain file cleanly?
        try:
            from tmarl.models.actor import Actor
            test_model = Actor()
            state_dict = torch.load(str(ACTOR_PT), map_location=device)
            test_model.load_state_dict(state_dict)
            test_model.to(device)
            test_model.eval()
            print("[Verification] [+] Brain file weights initialized successfully.", flush=True)
        except Exception as load_err:
            raise RuntimeError(f"Failed to build Actor architecture with state_dict: {load_err}")

        # Test 2: Does the underlying C++ engine spin up a 10-vs-10 manual slice?
        test_env = football_env.create_environment(
            env_name="11_vs_11_kaggle",
            stacked=False, representation="raw", rewards="scoring",
            write_full_episode_dumps=False, write_goal_dumps=False, write_video=False, render=False,
            number_of_left_players_agent_controls=10,
            number_of_right_players_agent_controls=10,
            other_config_options={"action_set": "full", "render_hud": False, "display_game_stats": False}
        )
        
        # Test 3: Do we get 20 clean data arrays back?
        test_obs = test_env.reset()
        test_obs_list = list(test_obs) if isinstance(test_obs, (list, tuple)) else [test_obs]
        print(f"[Verification] [+] GFR observation data profiles returned: {len(test_obs_list)} agents.", flush=True)
        
        if len(test_obs_list) != 20:
            raise ValueError(f"Target count mismatch. Expected 20 active agent slices, got {len(test_obs_list)}")

        # Test 4: Can the network evaluate all 20 streams in a single batch matrix pass?
        with torch.no_grad():
            test_tensor = torch.FloatTensor(test_obs_list).to(device)
            test_tokens, _ = test_model(test_tensor)
            test_actions = test_tokens.cpu().numpy().astype(np.int32).flatten()
        
        # Test 5: Does the simulator accept the combined action stream?
        test_env.step(test_actions)
        test_env.close()
        print("[Verification] SUCCESS: 10v10 dual-control matrix parameters verified. Proceeding to main match execution.\n", flush=True)
        
    except Exception as e:
        print(f"\n[Verification] CRITICAL ARCHITECTURE FAULT: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    # ════════════════════════════════════════════════════════════════════

    step = 0

    def flush_sidecar():
        stats["steps"] = step
        tmp = sidecar.with_suffix(".tmp")
        tmp.write_text(json.dumps(stats))
        tmp.replace(sidecar)   # atomic rename

    flush_sidecar()   # write initial state immediately

    env = football_env.create_environment(
        env_name="11_vs_11_kaggle",
        stacked=False,
        representation="raw",
        rewards="scoring",
        logdir=str(dump_dir),
        write_full_episode_dumps=True,
        write_goal_dumps=False,
        write_video=False,
        render=False,
        number_of_left_players_agent_controls=10,
        number_of_right_players_agent_controls=0,
        other_config_options={
            "action_set": "full",
            "render_hud": False,
            "display_game_stats": False,
        }
    )

    influencer = PlayerActionInfluencer(
        home_attrs, away_attrs,
        rng_seed=int(match_id_str.replace("-", "")[:8], 16)
    )
    # ─── OPEN THE TIKICK BRAIN FILE ─────────────────────────────────
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    actor_model = None
    
    try:
        from tmarl.models.actor import Actor
        # 1. Build the empty structural skeleton of the network
        actor_model = Actor()
        
        # 2. Read the raw weight dictionary matrices from your file
        weights = torch.load(str(ACTOR_PT), map_location=device)
        
        # 3. Map those weights directly onto the empty skeleton
        actor_model.load_state_dict(weights)
        
        # 4. Push the model to your hardware and lock it in evaluation mode
        actor_model.to(device)
        actor_model.eval()
        
        print(f"[child] Perfect! Loaded and mapped TiKick brain weights on {device}", flush=True)
        
    except Exception as e:
        print(f"[child] CRITICAL ERROR: Could not map actor.pt onto Actor structure: {e}", flush=True)
        sys.exit(1)
    # ─────────────────────────────────────────────────────────────────

    MAX_STEPS = 3001
    obs = env.reset()
    done = False
    score = [0, 0]
    prev_score = [0, 0]
    prev_game_mode = None

    while step < MAX_STEPS and not done:
        if isinstance(obs, (list, tuple)):
            obs_list = list(obs)
        else:
            obs_list = [obs]

        n_agents = len(obs_list)
        if n_agents == 0:
            break

        # Sample actions: GFR MultiDiscrete.sample() → shape (N,) already
        """try:
            sampled = np.asarray(env.action_space.sample(), dtype=np.int32).flatten()
            raw_actions = sampled if sampled.shape[0] == n_agents else np.array(
                [random.randint(0, 18) for _ in range(n_agents)], dtype=np.int32
            )
        except Exception:
            raw_actions = np.array(
                [random.randint(0, 18) for _ in range(n_agents)], dtype=np.int32
            )"""
        # ─── USE THE BRAIN TO CHOOSE ACTIONS COMPETITIVELY ────────────
        if actor_model is not None:
            with torch.no_grad():
                # Turn the pitch observations into data the brain understands
                obs_tensor = torch.FloatTensor(obs_list).to(device)
                # Ask the brain what the players should do
                action_tokens, _ = actor_model(obs_tensor)
                raw_actions = action_tokens.cpu().numpy().astype(np.int32).flatten()
        else:
            # Emergency fallback to random buttons if brain failed to open
            raw_actions = np.array([random.randint(0, 18) for _ in range(n_agents)], dtype=np.int32)
        # ──────────────────────────────────────────────────────────────

        # Fetch obs dict for influencer ball-position checks
        try:
            main_obs = env.unwrapped.observation()
            main_obs = (main_obs[0] if main_obs else {}) if isinstance(main_obs, list) else main_obs
        except Exception:
            main_obs = {}

        for agent_idx in range(n_agents):
            raw_actions[agent_idx] = influencer.influence(
                team_idx=0,
                player_idx=agent_idx,
                action=int(np.asarray(raw_actions[agent_idx]).item()),
                obs=main_obs,
            )

        try:
            step_result = env.step(raw_actions)
        except Exception as e:
            print(f"[child] env.step() error at step {step}: {e}", flush=True)
            break

        if len(step_result) == 5:
            obs, reward, done, info, _ = step_result
        elif len(step_result) == 4:
            obs, reward, done, info = step_result
        else:
            obs = step_result[0]
            done = step_result[2] if len(step_result) > 2 else False
            info = step_result[3] if len(step_result) > 3 else {}

        if isinstance(done, (list, np.ndarray)):
            done = bool(done[0])

        # Extract score & game mode
        try:
            raw_obs_list = env.unwrapped.observation()
            raw_obs_0 = (raw_obs_list[0] if raw_obs_list else {}) if isinstance(raw_obs_list, list) else raw_obs_list
            current_score = [int(x) for x in raw_obs_0.get("score", [0, 0])]
            game_mode = int(raw_obs_0.get("game_mode", 0))
        except Exception:
            current_score = list(score)  # keep last known
            game_mode = 0

        if current_score != prev_score:
            score = current_score[:]
            if current_score[0] > prev_score[0]:
                stats["goals_home"] += 1
                print(f"[child] ⚽ Home goal! {score[0]}:{score[1]} step={step}", flush=True)
            elif current_score[1] > prev_score[1]:
                stats["goals_away"] += 1
                print(f"[child] ⚽ Away goal! {score[0]}:{score[1]} step={step}", flush=True)
            prev_score = current_score[:]
            # Flush score to disk immediately after every goal
            stats["score"] = f"{score[0]}-{score[1]}"
            flush_sidecar()

        if game_mode != prev_game_mode:
            mode_name = {
                0: "normal", 2: "goal_kick", 3: "free_kick",
                4: "corner",  6: "penalty"
            }.get(game_mode, f"mode_{game_mode}")
            stats["game_modes"][mode_name] = stats["game_modes"].get(mode_name, 0) + 1
            if game_mode == 4:
                stats["corners"] += 1
            elif game_mode == 3:
                stats["free_kicks"] += 1
            prev_game_mode = game_mode

        if step % 100 == 0:
            flush_sidecar()

        step += 1

    # Graceful close attempt
    try:
        env.close()
    except Exception:
        pass

    stats["steps"] = step
    stats["score"] = f"{score[0]}-{score[1]}"

    # Find the dump file written by GFR
    dump_files = sorted(dump_dir.glob("*.dump"), key=os.path.getmtime, reverse=True)
    if dump_files:
        named_dump = dump_dir / f"{match_id_str}.dump"
        try:
            shutil.move(str(dump_files[0]), str(named_dump))
            stats["dump_file"] = str(named_dump)
        except Exception:
            stats["dump_file"] = str(dump_files[0])
    flush_sidecar()   # final write with complete stats


def run_simulation(
    fixture: Fixture, home_team: Team, away_team: Team,
    home_attrs: dict, away_attrs: dict,
    match_config: dict,
    dump_dir: Path,
    timeout: int = 600,
) -> dict:
    """
    Runs _run_simulation_child in an isolated subprocess.
    If the C++ engine segfaults (SIGSEGV), the child dies but the
    parent reads whatever the sidecar captured before the crash,
    then looks for any partially-written .dump file and salvages it.
    """
    import multiprocessing as mp

    # Write match config for draw_match.py later
    config_path = dump_dir / f"match_{fixture.match_id}.json"
    with open(config_path, "w") as f:
        json.dump(match_config, f, indent=2)

    sidecar_path = dump_dir / "_stats.json"

    log.info(f"  Creating GFR environment for match {fixture.match_id}...")

    proc = mp.Process(
        target=_run_simulation_child,
        args=(
            str(fixture.match_id),
            home_team.team_name,
            away_team.team_name,
            home_attrs,
            away_attrs,
            str(dump_dir),
            str(sidecar_path),
        ),
        daemon=True,
    )
    proc.start()
    proc.join(timeout=timeout)

    if proc.is_alive():
        log.warning(f"  [Timeout] Child process exceeded {timeout}s — killing.")
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()

    exit_code = proc.exitcode
    if exit_code is not None and exit_code < 0:   # negative = killed by signal
        log.warning(f"  [SIGSEGV/Signal] Child exited with signal {-exit_code}. Salvaging partial results...")
    elif exit_code not in (0, None):
        log.warning(f"  [Child Error] Child exited with code {exit_code}.")

    # Read whatever the child wrote before dying
    stats: dict = {
        "score": "0-0",
        "goals_home": 0, "goals_away": 0,
        "corners": 0, "free_kicks": 0,
        "game_modes": {}, "steps": 0,
        "dump_file": None, "crashed": exit_code not in (0, None),
    }
    if sidecar_path.exists():
        try:
            stats.update(json.loads(sidecar_path.read_text()))
        except Exception:
            pass

    # Salvage any dump file the child may have left
    if not stats.get("dump_file"):
        dump_files = sorted(dump_dir.glob("*.dump"), key=os.path.getmtime, reverse=True)
        if dump_files:
            named_dump = dump_dir / f"{fixture.match_id}.dump"
            try:
                if not named_dump.exists():
                    shutil.move(str(dump_files[0]), str(named_dump))
                stats["dump_file"] = str(named_dump)
                log.info(f"  [+] Salvaged partial dump: {named_dump}")
            except Exception as e:
                log.warning(f"  Could not salvage dump: {e}")
                stats["dump_file"] = str(dump_files[0])

    stats["match_config_path"] = str(config_path)
    score_str = stats.get("score", "0-0")
    log.info(f"  [+] Match result: {home_team.team_name} {score_str} {away_team.team_name} | steps={stats.get('steps', '?')}")
    return stats


# ════════════════════════════════════════════════════════════════════
#  Video + GIF rendering via draw_match.py
# ════════════════════════════════════════════════════════════════════

def render_dump_to_video(dump_path: str, match_config_path: str, output_dir: Path, match_id: str) -> dict:
    """
    Imports GameReplayVisualizer from draw_match.py and renders the dump
    to an MP4 and GIF. Returns paths to generated files.
    """
    sys.path.insert(0, str(TIKICK_ROOT / "scripts" / "football"))

    try:
        from draw_match import GameReplayVisualizer
    except ImportError as e:
        log.error(f"Could not import draw_match.py: {e}")
        return {"mp4": None, "gif": None}

    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"

    mp4_path = str(output_dir / f"{match_id}_full.mp4")
    gif_path = mp4_path.replace(".mp4", ".gif")

    try:
        viz = GameReplayVisualizer(config_path=match_config_path, headless=True)
        log.info(f"  Rendering {dump_path} → {mp4_path}...")
        viz.render_dump(dump_path, mp4_path, fps=10)
        viz.quit()

        # Convert to GIF
        log.info(f"  Converting MP4 → GIF...")
        GameReplayVisualizer.mp4_to_gif(mp4_path, gif_path, fps=8, scale=0.75)

        return {"mp4": mp4_path, "gif": gif_path}
    except Exception as e:
        log.error(f"  Video rendering failed: {e}")
        traceback.print_exc()
        return {"mp4": None, "gif": None}


# ════════════════════════════════════════════════════════════════════
#  DB write-back helpers
# ════════════════════════════════════════════════════════════════════

def settle_fixture(db, fixture: Fixture, stats: dict):
    """Updates fixture row with score, outcome, and completion status."""
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
        "home_goals": home_g,
        "away_goals": away_g,
        "corners": stats.get("corners", 0),
        "free_kicks": stats.get("free_kicks", 0),
        "game_modes": stats.get("game_modes", {}),
        "simulated_at": datetime.utcnow().isoformat()
    }
    db.commit()
    log.info(f"  [DB] Fixture {fixture.match_id} settled: {score_str} ({result})")

    # Settle betting markets
    markets = db.query(EventMarket).filter(EventMarket.match_id == fixture.match_id).all()
    total_over_25 = home_g + away_g > 2
    both_scored = home_g > 0 and away_g > 0

    for m in markets:
        m.status = "settled"
        winning = False
        if m.market_name == "1X2":
            winning = (
                (m.selection_name == "Home" and result == "home_win") or
                (m.selection_name == "Draw" and result == "draw") or
                (m.selection_name == "Away" and result == "away_win")
            )
        elif m.market_name == "Over/Under 2.5":
            winning = (
                (m.selection_name == "Over 2.5" and total_over_25) or
                (m.selection_name == "Under 2.5" and not total_over_25)
            )
        elif m.market_name == "GG/NG":
            winning = (
                (m.selection_name == "GG" and both_scored) or
                (m.selection_name == "NG" and not both_scored)
            )
        m.winning_selection = winning
    db.commit()
    log.info(f"  [DB] {len(markets)} event markets settled for match {fixture.match_id}")


def persist_dump(db, fixture: Fixture, stats: dict, video_paths: dict):
    """Saves a GfrDump record including binary video data."""
    dump_file = stats.get("dump_file")
    mp4_path = video_paths.get("mp4")
    gif_path = video_paths.get("gif")

    # Read video binary for DB storage
    video_binary = None
    if mp4_path and os.path.exists(mp4_path):
        with open(mp4_path, "rb") as f:
            video_binary = f.read()

    # Choose video_url: prefer the GIF path for lightweight streaming
    video_url = gif_path if (gif_path and os.path.exists(gif_path)) else mp4_path

    gfr_stats = {
        "score": stats.get("score", "0-0"),
        "home_goals": stats.get("goals_home", 0),
        "away_goals": stats.get("goals_away", 0),
        "corners": stats.get("corners", 0),
        "free_kicks": stats.get("free_kicks", 0),
        "total_steps": stats.get("steps", 0),
        "game_modes": stats.get("game_modes", {}),
    }

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
        match_video=video_binary
    )
    db.add(dump)
    db.commit()
    log.info(f"  [DB] GfrDump persisted for match {fixture.match_id} (video: {video_url})")


def update_season_gameweek(db, season_id, gameweek: int):
    """Advances the season's current_gwk tracker."""
    season = db.query(Season).filter(Season.season_id == season_id).first()
    if season and season.current_gwk < gameweek:
        season.current_gwk = gameweek
        db.commit()
        log.info(f"  [DB] Season {season_id} → current_gwk={gameweek}")


def update_player_tiredness(db, team_id, influencer: PlayerActionInfluencer, team_idx: int):
    """Persists end-of-match tiredness back to the player table."""
    tired_map = influencer.home_tired if team_idx == 0 else influencer.away_tired
    players = db.query(Player).filter(Player.team_id == team_id).all()
    for p in players:
        new_tired = tired_map.get(p.player_position, float(p.tired_factor or 0.0))
        p.tired_factor = round(min(1.0, new_tired), 3)
    db.commit()


# ════════════════════════════════════════════════════════════════════
#  Sequential Match Queue Runner
# ════════════════════════════════════════════════════════════════════

def simulate_next_fixture(db):
    """
    Finds the next upcoming fixture (ordered by game_date, game_time),
    simulates it, renders it, and settles the DB records.
    Returns True if a fixture was processed, False if the queue is empty.
    """
    fixture = db.query(Fixture).filter(
        Fixture.status == "upcoming"
    ).order_by(Fixture.game_date.asc(), Fixture.game_time.asc()).first()

    if not fixture:
        log.info("[Queue] No upcoming fixtures in the queue.")
        return False

    log.info(f"\n{'='*60}")
    log.info(f"[Queue] Processing Match {fixture.match_id}")

    home_team = db.query(Team).filter(Team.team_id == fixture.home_team_id).first()
    away_team = db.query(Team).filter(Team.team_id == fixture.away_team_id).first()

    if not home_team or not away_team:
        log.error("  [Error] Team not found for this fixture.")
        fixture.status = "error"
        db.commit()
        return True

    log.info(f"  {home_team.team_name} vs {away_team.team_name} | GWK {fixture.gameweek}")

    # Mark as live
    fixture.status = "live"
    db.commit()

    # Load player attributes
    home_attrs, away_attrs = load_team_attributes(db, fixture.home_team_id, fixture.away_team_id)

    # Build match config for rendering
    match_config = build_match_config(home_team, away_team, home_attrs, away_attrs)

    # Per-match dump directory
    dump_dir = DUMP_STORE / str(fixture.match_id)
    dump_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Simulate the match
        stats = run_simulation(fixture, home_team, away_team, home_attrs, away_attrs, match_config, dump_dir)

        # 2. Render dump → video/GIF
        video_paths = {"mp4": None, "gif": None}
        if stats.get("dump_file") and os.path.exists(stats["dump_file"]):
            video_paths = render_dump_to_video(
                dump_path=stats["dump_file"],
                match_config_path=stats["match_config_path"],
                output_dir=VIDEO_STORE,
                match_id=str(fixture.match_id)
            )

        # 3. Settle fixture & markets
        settle_fixture(db, fixture, stats)

        # 4. Persist GFR dump record
        persist_dump(db, fixture, stats, video_paths)

        # 5. Update season gameweek tracker
        update_season_gameweek(db, fixture.season_id, fixture.gameweek)

        # 6. Persist player tiredness
        influencer = PlayerActionInfluencer(home_attrs, away_attrs)
        update_player_tiredness(db, fixture.home_team_id, influencer, 0)
        update_player_tiredness(db, fixture.away_team_id, influencer, 1)

        log.info(f"[Queue] ✅ Match complete: {home_team.team_name} {stats['score']} {away_team.team_name}")

    except Exception as e:
        log.error(f"  [Error] Simulation failed: {e}")
        traceback.print_exc()
        fixture.status = "error"
        db.commit()

    return True


def run_gameweek(gameweek: int):
    """Simulates all fixtures in a specific gameweek sequentially."""
    db = SessionLocal()
    try:
        fixtures = db.query(Fixture).filter(
            Fixture.gameweek == gameweek,
            Fixture.status == "upcoming"
        ).order_by(Fixture.game_date.asc(), Fixture.game_time.asc()).all()

        if not fixtures:
            log.info(f"[Gameweek {gameweek}] No upcoming fixtures found.")
            return

        log.info(f"[Gameweek {gameweek}] Processing {len(fixtures)} matches...")
        for fix in fixtures:
            # Switch to per-fixture session for isolation
            db.expunge(fix)
        db.close()

        for _ in fixtures:
            db2 = SessionLocal()
            try:
                simulate_next_fixture(db2)
            finally:
                db2.close()

        log.info(f"[Gameweek {gameweek}] ✅ All matches complete.")
    finally:
        if db.is_active:
            db.close()


def run_queue_continuously(max_matches: int = None):
    """
    Runs the simulation queue continuously until it's exhausted or max_matches reached.
    This is the primary entrypoint for the background worker daemon.
    """
    count = 0
    log.info("[Worker] Starting CityBet Virtuals simulation queue worker...")
    while True:
        db = SessionLocal()
        try:
            processed = simulate_next_fixture(db)
        finally:
            db.close()

        if not processed:
            log.info("[Worker] Queue exhausted. Worker sleeping 60s...")
            time.sleep(60)
            continue

        count += 1
        if max_matches is not None and count >= max_matches:
            log.info(f"[Worker] Reached max_matches={max_matches}. Stopping.")
            break

        # Brief cooldown between matches
        time.sleep(2)


# ════════════════════════════════════════════════════════════════════
#  CLI Entry Points
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CityBet Virtuals GFR Simulator")
    parser.add_argument("--mode", choices=["one", "gameweek", "all"], default="one",
                        help="one=next fixture, gameweek=full GWK, all=continuous queue")
    parser.add_argument("--gameweek", type=int, default=1, help="Gameweek number (used with --mode=gameweek)")
    parser.add_argument("--max", type=int, default=None, help="Max matches to run (continuous mode)")
    args = parser.parse_args()

    if args.mode == "one":
        db = SessionLocal()
        try:
            simulate_next_fixture(db)
        finally:
            db.close()
    elif args.mode == "gameweek":
        run_gameweek(args.gameweek)
    elif args.mode == "all":
        run_queue_continuously(max_matches=args.max)
