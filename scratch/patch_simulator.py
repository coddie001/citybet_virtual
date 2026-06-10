import re
import sys
from pathlib import Path

FILE_PATH = Path("/home/Warta/projects/citybet_virtuals/workers/game_simulator.py")
code = FILE_PATH.read_text()

# 1. Inject FeatureExtractor class right after PlayerActionInfluencer
feature_extractor_code = """

# ════════════════════════════════════════════════════════════════════
#  Observation Matrix Feature Extractor
# ════════════════════════════════════════════════════════════════════

class FeatureExtractor:
    def __init__(self, num_agents):
        self.num_agents = num_agents
        self.last_loffside = np.zeros(11, np.float32)
        self.last_roffside = np.zeros(11, np.float32)

    def extract(self, raw_obs):
        if not raw_obs:
            return np.zeros((self.num_agents, 268), dtype=np.float32)
        
        raw_obs = self._notFullGame(raw_obs)
        obs = []
        ally = np.array(raw_obs[0]['left_team'])
        ally_d = np.array(raw_obs[0]['left_team_direction'])
        enemy = np.array(raw_obs[0]['right_team'])
        enemy_d = np.array(raw_obs[0]['right_team_direction'])
        lo, ro = self.get_offside(raw_obs[0])
        
        for a in range(self.num_agents):
            if a >= len(raw_obs):
                break
            me = ally[int(raw_obs[a]['active'])]
            ball = raw_obs[a]['ball'][:2]
            ball_dist = np.linalg.norm(me - ball)
            enemy_dist = np.linalg.norm(me - enemy, axis=-1)
            to_enemy = enemy - me
            to_ally = ally - me
            to_ball = ball - me

            o = []
            o.extend(ally.flatten())
            o.extend(ally_d.flatten())
            o.extend(enemy.flatten())
            o.extend(enemy_d.flatten())
            
            o.extend(raw_obs[a]['ball'])
            o.extend(raw_obs[a]['ball_direction'])
            
            if raw_obs[a]['ball_owned_team'] == -1: o.extend([1, 0, 0])
            elif raw_obs[a]['ball_owned_team'] == 0: o.extend([0, 1, 0])
            elif raw_obs[a]['ball_owned_team'] == 1: o.extend([0, 0, 1])
            else: o.extend([0, 0, 0])
            
            active = [0] * 11
            active[raw_obs[a]['active']] = 1
            o.extend(active)
            
            game_mode = [0] * 7
            game_mode[raw_obs[a]['game_mode']] = 1
            o.extend(game_mode)
            
            o.extend(raw_obs[a]['sticky_actions'][:10])
            
            ball_dist = 1 if ball_dist > 1 else ball_dist
            o.extend([ball_dist])
            o.extend(raw_obs[a]['left_team_tired_factor'])
            o.extend(raw_obs[a]['left_team_yellow_card'])
            o.extend(raw_obs[a]['left_team_active'])
            o.extend(lo)
            o.extend(ro)
            o.extend(enemy_dist)
            
            to_ally_copy = to_ally.copy()
            to_ally_copy[:, 0] /= 2
            o.extend(to_ally_copy.flatten())
            
            to_enemy_copy = to_enemy.copy()
            to_enemy_copy[:, 0] /= 2
            o.extend(to_enemy_copy.flatten())
            
            to_ball_copy = to_ball.copy()
            to_ball_copy[0] /= 2
            o.extend(to_ball_copy.flatten())
            
            steps_left = raw_obs[a]['steps_left']
            o.extend([1.0 * steps_left / 3001])
            if steps_left > 1500: steps_left -= 1501
            steps_left = 1.0 * min(steps_left, 300.0) / 300.0
            o.extend([steps_left])
            
            score_ratio = 1.0 * (raw_obs[a]['score'][0] - raw_obs[a]['score'][1]) / 5.0
            score_ratio = max(-1.0, min(score_ratio, 1.0))
            o.extend([score_ratio])
            
            o.extend([0.0] * 27)
            obs.append(o)
            
        return np.array(obs, dtype=np.float32)

    def get_offside(self, obs):
        if obs['game_mode'] != 0:
            self.last_loffside = np.zeros(11, np.float32)
            self.last_roffside = np.zeros(11, np.float32)
            return self.last_loffside, self.last_roffside

        ball = np.array(obs['ball'][:2])
        ally = np.array(obs['left_team'])
        enemy = np.array(obs['right_team'])

        need_recalc = False
        effective_ownball_team = -1
        effective_ownball_player = -1

        if obs['ball_owned_team'] > -1:
            effective_ownball_team = obs['ball_owned_team']
            effective_ownball_player = obs['ball_owned_player']
            need_recalc = True
        else:
            ally_dist = np.linalg.norm(ball - ally, axis=-1)
            enemy_dist = np.linalg.norm(ball - enemy, axis=-1)
            if np.min(ally_dist) < np.min(enemy_dist) and np.min(ally_dist) < 0.017:
                need_recalc = True
                effective_ownball_team = 0
                effective_ownball_player = np.argmin(ally_dist)
            elif np.min(enemy_dist) < np.min(ally_dist) and np.min(enemy_dist) < 0.017:
                need_recalc = True
                effective_ownball_team = 1
                effective_ownball_player = np.argmin(enemy_dist)

        if not need_recalc:
            return self.last_loffside, self.last_roffside

        left_offside = np.zeros(11, np.float32)
        right_offside = np.zeros(11, np.float32)

        if effective_ownball_team == 0:
            right_xs = np.sort(np.array([obs['right_team'][k][0] for k in range(1, 11)]))
            for k in range(1, 11):
                if obs['left_team'][k][0] > right_xs[-1] and k != effective_ownball_player and obs['left_team'][k][0] > 0.0:
                    left_offside[k] = 1.0
        else:
            left_xs = np.sort(np.array([obs['left_team'][k][0] for k in range(1, 11)]))
            for k in range(1, 11):
                if obs['right_team'][k][0] < left_xs[0] and k != effective_ownball_player and obs['right_team'][k][0] < 0.0:
                    right_offside[k] = 1.0

        self.last_loffside = left_offside
        self.last_roffside = right_offside
        return left_offside, right_offside

    def _notFullGame(self, raw_obs):
        left_ok = len(raw_obs[0]['left_team']) == 11
        right_ok = len(raw_obs[0]['right_team']) == 11
        if left_ok and right_ok:
            return raw_obs
        
        for obs in raw_obs:
            obs['left_team'] = np.array(obs['left_team'])
            obs['right_team'] = np.array(obs['right_team'])
            obs['left_team_direction'] = np.array(obs['left_team_direction'])
            obs['right_team_direction'] = np.array(obs['right_team_direction'])
            while len(obs['left_team']) < 11:
                obs['left_team'] = np.concatenate([obs['left_team'], np.array([[-1,0]])], axis=0)
                obs['left_team_direction'] = np.concatenate([obs['left_team_direction'], np.zeros([1,2])], axis=0)
                obs['left_team_tired_factor'] = np.concatenate([obs['left_team_tired_factor'], np.zeros(1)], axis=0)
                obs['left_team_yellow_card'] = np.concatenate([obs['left_team_yellow_card'], np.zeros(1)], axis=0)
                obs['left_team_active'] = np.concatenate([obs['left_team_active'], np.ones(1)], axis=0)
            while len(obs['right_team']) < 11:
                obs['right_team'] = np.concatenate([obs['right_team'], np.array([[-1,0]])], axis=0)
                obs['right_team_direction'] = np.concatenate([obs['right_team_direction'], np.zeros([1,2])], axis=0)
        return raw_obs
"""
code = code.replace(
    "# ════════════════════════════════════════════════════════════════════\n#  Isolated Subprocess Engine Loop",
    feature_extractor_code + "\n\n# ════════════════════════════════════════════════════════════════════\n#  Isolated Subprocess Engine Loop"
)

# 2. Modify influence() to scale velocity dynamically (if not already there)
# Actually, the prompt says: "scale their underlying physical velocity vectors within the raw input vector before the tensor is fed into actor_model."
# So I'll do this in the `_run_simulation_child` instead, right before `actor_model(obs_tensor)`

# 3. Modify the _run_simulation_child
# We need to initialize rnn_states and masks
rnn_init_code = """
    MAX_STEPS = 3001
    obs = env.reset()
    done = False
    score = [0, 0]
    prev_score = [0, 0]
    prev_game_mode = None

    # Recurrent State Consistency Control
    n_agents = 10
    rnn_states = torch.zeros(n_agents, 1, 256).to(device)
    masks = torch.ones(n_agents, 1).to(device)
    
    feature_extractor = FeatureExtractor(n_agents)
    
    # Custom Analytics Storage
    stats["player_metrics"] = {
        "velocity_reward_increments": {i: 0.0 for i in range(n_agents)},
        "shooting_accuracy_indexes": {i: 0.0 for i in range(n_agents)},
    }
"""
code = code.replace(
"""    MAX_STEPS = 3001
    obs = env.reset()
    done = False
    score = [0, 0]
    prev_score = [0, 0]
    prev_game_mode = None""", rnn_init_code)

# 4. In the while loop, update feature extraction, velocity scaling, and reward tracking
while_loop_old = """
        if actor_model is not None:
            with torch.no_grad():
                # Convert multi-agent dictionary elements to a structured matrix space pass
                match_features = np.zeros((n_agents, 268), dtype=np.float32)
                obs_tensor = torch.FloatTensor(match_features).to(device)
                
                action_tokens, _ = actor_model(obs_tensor)
                raw_actions = action_tokens.cpu().numpy().astype(np.int32).flatten()
        else:
            raw_actions = np.array([random.randint(0, 18) for _ in range(n_agents)], dtype=np.int32)
"""

while_loop_new = """
        if actor_model is not None:
            with torch.no_grad():
                # Database Attribute Synchronization: scale underlying physical velocity vectors
                try:
                    raw_obs = env.unwrapped.observation()
                    for agent_idx in range(n_agents):
                        if agent_idx < len(raw_obs):
                            p_attrs = influencer._get_attrs(0, agent_idx)
                            if p_attrs and "velocity" in p_attrs:
                                raw_obs[agent_idx]["left_team_direction"] = [
                                    dir_val * p_attrs["velocity"] 
                                    for dir_val in raw_obs[agent_idx]["left_team_direction"]
                                ]
                except Exception:
                    pass

                # Convert multi-agent dictionary elements to a structured matrix space pass
                match_features = feature_extractor.extract(env.unwrapped.observation() if hasattr(env, 'unwrapped') else obs_list)
                
                # Check for feature shape mismatches and pad/truncate to 268 if necessary
                if match_features.shape[1] < 268:
                    pad = np.zeros((match_features.shape[0], 268 - match_features.shape[1]), dtype=np.float32)
                    match_features = np.hstack([match_features, pad])
                elif match_features.shape[1] > 268:
                    match_features = match_features[:, :268]

                obs_tensor = torch.FloatTensor(match_features).to(device)
                
                # Use recurrent states and masks
                action_tokens, _, rnn_states = actor_model(obs_tensor, rnn_states, masks)
                raw_actions = action_tokens.cpu().numpy().astype(np.int32).flatten()
        else:
            raw_actions = np.array([random.randint(0, 18) for _ in range(n_agents)], dtype=np.int32)
"""
code = code.replace(while_loop_old, while_loop_new)

# 5. Reward Tracking:
reward_tracking_old = """
        for agent_idx in range(n_agents):
            # Safe boundary array slicing mapping the network's 33 tokens down to GFR actions
            clamped_action = int(np.asarray(raw_actions[agent_idx]).item())
            clamped_action = min(max(clamped_action, 0), 18)
            
            raw_actions[agent_idx] = influencer.influence(
                team_idx=0, player_idx=agent_idx,
                action=clamped_action, obs=main_obs,
            )
"""
reward_tracking_new = """
        for agent_idx in range(n_agents):
            # Safe boundary array slicing mapping the network's 33 tokens down to GFR actions
            clamped_action = int(np.asarray(raw_actions[agent_idx]).item())
            clamped_action = min(max(clamped_action, 0), 18)
            
            raw_actions[agent_idx] = influencer.influence(
                team_idx=0, player_idx=agent_idx,
                action=clamped_action, obs=main_obs,
            )
            
            # Custom Attribute Reward Evaluation
            try:
                p_attrs = influencer._get_attrs(0, agent_idx)
                if p_attrs:
                    vel = p_attrs.get("velocity", 1.0)
                    rating = p_attrs.get("rating", 3)
                    shooting_reward = p_attrs.get("rewards", {}).get("shooting_reward", 0.0)
                    
                    ball = main_obs.get("ball", [0,0,0])
                    left_team = main_obs.get("left_team", [])
                    if len(left_team) > agent_idx:
                        me = left_team[agent_idx]
                        dist = np.linalg.norm(np.array(me) - np.array(ball[:2]))
                        prox = 1.0 / (1.0 + dist)
                        
                        inc = prox * vel
                        stats["player_metrics"]["velocity_reward_increments"][agent_idx] += inc
                        
                        if raw_actions[agent_idx] == 12: # ACTION_SHOT
                            sai = rating * shooting_reward
                            stats["player_metrics"]["shooting_accuracy_indexes"][agent_idx] += sai
            except Exception as e:
                pass
"""
code = code.replace(reward_tracking_old, reward_tracking_new)

# 6. GfrDump stats appending
dump_stats_old = """
    gfr_stats = {
        "score": stats.get("score", "0-0"), "home_goals": stats.get("goals_home", 0),
        "away_goals": stats.get("goals_away", 0), "corners": stats.get("corners", 0),
        "free_kicks": stats.get("free_kicks", 0), "total_steps": stats.get("steps", 0),
        "game_modes": stats.get("game_modes", {}),
    }
"""
dump_stats_new = """
    gfr_stats = {
        "score": stats.get("score", "0-0"), "home_goals": stats.get("goals_home", 0),
        "away_goals": stats.get("goals_away", 0), "corners": stats.get("corners", 0),
        "free_kicks": stats.get("free_kicks", 0), "total_steps": stats.get("steps", 0),
        "game_modes": stats.get("game_modes", {}),
        "player_metrics": stats.get("player_metrics", {})
    }
"""
code = code.replace(dump_stats_old, dump_stats_new)

FILE_PATH.write_text(code)
print("game_simulator.py updated successfully!")
