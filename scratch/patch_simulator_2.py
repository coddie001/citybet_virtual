import sys
from pathlib import Path

FILE_PATH = Path("/home/Warta/projects/citybet_virtuals/workers/game_simulator.py")
code = FILE_PATH.read_text()

# 1. Fix the velocity scaling loop
bad_scaling = """                                raw_obs[agent_idx]["left_team_direction"] = [
                                    dir_val * p_attrs["velocity"] 
                                    for dir_val in raw_obs[agent_idx]["left_team_direction"]
                                ]"""
good_scaling = """                                raw_obs[agent_idx]["left_team_direction"] = [
                                    [float(dir_val[0] * p_attrs["velocity"]), float(dir_val[1] * p_attrs["velocity"])] 
                                    for dir_val in raw_obs[agent_idx]["left_team_direction"]
                                ]"""
code = code.replace(bad_scaling, good_scaling)

# 2. Fix the feature extractor call to use the modified raw_obs
bad_extract = "match_features = feature_extractor.extract(env.unwrapped.observation() if hasattr(env, 'unwrapped') else obs_list)"
good_extract = "match_features = feature_extractor.extract(raw_obs)"
code = code.replace(bad_extract, good_extract)

# 3. Add available_actions masking
bad_eval = """                # Use recurrent states and masks
                action_tokens, _, rnn_states = actor_model(obs_tensor, rnn_states, masks)"""
good_eval = """                # Provide available actions mask so the network ignores actions >= 19
                avail_actions = torch.ones(n_agents, 33).to(device)
                avail_actions[:, 19:] = 0
                
                # Use recurrent states and masks
                action_tokens, _, rnn_states = actor_model(obs_tensor, rnn_states, masks, available_actions=avail_actions)"""
code = code.replace(bad_eval, good_eval)

FILE_PATH.write_text(code)
print("game_simulator.py patched successfully!")
