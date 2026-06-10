import gfootball.env as football_env
import json

env = football_env.create_environment(
    env_name="11_vs_11_kaggle",
    stacked=False, representation="raw", rewards="scoring",
    number_of_left_players_agent_controls=10,
    number_of_right_players_agent_controls=10,
)
obs = env.reset()
print("obs 0 active:", obs[0]["active"])
print("obs 0 team?", "left_team" in obs[0], "right_team" in obs[0])
print("obs 10 active:", obs[10]["active"])
