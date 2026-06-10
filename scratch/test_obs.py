import gfootball.env as football_env
import json

env = football_env.create_environment(
    env_name="11_vs_11_kaggle",
    stacked=False, representation="raw", rewards="scoring",
    number_of_left_players_agent_controls=10,
    number_of_right_players_agent_controls=10,
)
obs = env.reset()
print(f"Number of observations: {len(obs)}")
print(f"Is left for obs 0: {obs[0].get('is_left', 'missing')}")
print(f"Is left for obs 10: {obs[10].get('is_left', 'missing')}")

with open("scratch/obs_0.json", "w") as f:
    json.dump({k: v for k, v in obs[0].items() if type(v) in [int, bool, float, str]}, f, indent=2)

with open("scratch/obs_10.json", "w") as f:
    json.dump({k: v for k, v in obs[10].items() if type(v) in [int, bool, float, str]}, f, indent=2)
