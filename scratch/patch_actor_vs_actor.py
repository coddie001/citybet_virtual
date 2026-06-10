"""
Patch: Upgrade game_simulator.py to full 10v10 actor.pt vs actor.pt mode.

Changes:
1. Enable number_of_right_players_agent_controls=10
2. Expand rnn_states/masks to 20 agents
3. Add mirror_obs_for_away() to rotate the field for the away team
4. Add flip_action_for_away() to reverse directional actions for away team
5. Apply PlayerActionInfluencer for BOTH teams
6. Split velocity scaling per team
"""

from pathlib import Path

SIM = Path("/home/Warta/projects/citybet_virtuals/workers/game_simulator.py")
code = SIM.read_text()

# ── 1. Enable right player controls ──────────────────────────────────────────
old_env_create = """    env = football_env.create_environment(
        env_name=\"11_vs_11_kaggle\",
        stacked=False, representation=\"raw\", rewards=\"scoring\",
        logdir=str(dump_dir), write_full_episode_dumps=True, write_goal_dumps=False, write_video=False, render=False,
        number_of_left_players_agent_controls=10,
        number_of_right_players_agent_controls=0,
        other_config_options={\"action_set\": \"full\", \"render_hud\": False, \"display_game_stats\": False}
    )"""

new_env_create = """    env = football_env.create_environment(
        env_name=\"11_vs_11_kaggle\",
        stacked=False, representation=\"raw\", rewards=\"scoring\",
        logdir=str(dump_dir), write_full_episode_dumps=True, write_goal_dumps=False, write_video=False, render=False,
        number_of_left_players_agent_controls=10,
        number_of_right_players_agent_controls=10,
        other_config_options={\"action_set\": \"full\", \"render_hud\": False, \"display_game_stats\": False}
    )"""

assert old_env_create in code, "FAIL: env create block not found"
code = code.replace(old_env_create, new_env_create)

# ── 2. Expand rnn_states, masks and FeatureExtractor to 20 agents ─────────────
old_rnn_init = """    # Recurrent State Consistency Control
    n_agents = 10
    rnn_states = torch.zeros(n_agents, 1, 256).to(device)
    masks = torch.ones(n_agents, 1).to(device)
    
    feature_extractor = FeatureExtractor(n_agents)
    
    # Custom Analytics Storage
    stats[\"player_metrics\"] = {
        \"velocity_reward_increments\": {i: 0.0 for i in range(n_agents)},
        \"shooting_accuracy_indexes\": {i: 0.0 for i in range(n_agents)},
    }"""

new_rnn_init = """    # Recurrent State Consistency Control – 10 home + 10 away = 20 total agents
    N_HOME = 10
    N_AWAY = 10
    n_agents = N_HOME + N_AWAY
    rnn_states = torch.zeros(n_agents, 1, 256).to(device)
    masks = torch.ones(n_agents, 1).to(device)
    
    # Separate feature extractors so each team's offside cache doesn't bleed
    home_extractor = FeatureExtractor(N_HOME)
    away_extractor = FeatureExtractor(N_AWAY)

    # ─── Action direction mirror table (for Away team) ────────────────────
    # actor.pt was trained attacking left→right.
    # Away team attacks right→left, so we flip horizontal directions.
    AWAY_ACTION_MIRROR = {
        1: 5,  # LEFT -> RIGHT
        2: 6,  # TOP_LEFT -> BOTTOM_RIGHT
        3: 7,  # TOP -> BOTTOM
        4: 8,  # TOP_RIGHT -> BOTTOM_LEFT
        5: 1,  # RIGHT -> LEFT
        6: 2,  # BOTTOM_RIGHT -> TOP_LEFT
        7: 3,  # BOTTOM -> TOP
        8: 4,  # BOTTOM_LEFT -> TOP_RIGHT
    }

    def mirror_obs_for_away(raw_obs_list):
        \"\"\"Return a mirrored copy of raw_obs for the away team (agents 10-19).
        Flips X coordinates, swaps left/right arrays and score/possession flags
        so actor.pt perceives itself as always attacking left-to-right.\"\"\"
        import copy
        mirrored = []
        for a in range(N_AWAY):
            src = raw_obs_list[N_HOME + a] if (N_HOME + a) < len(raw_obs_list) else raw_obs_list[N_HOME - 1]
            o = copy.deepcopy(src)
            # Flip ball X (negate x only, y stays)
            ball = list(o["ball"])
            ball[0] = -ball[0]
            o["ball"] = ball
            ball_d = list(o["ball_direction"])
            ball_d[0] = -ball_d[0]
            o["ball_direction"] = ball_d
            # Swap and negate X for left/right team arrays
            lt = [[-p[0], p[1]] for p in o["right_team"]]
            rt = [[-p[0], p[1]] for p in o["left_team"]]
            o["left_team"] = lt
            o["right_team"] = rt
            ltd = [[-d[0], d[1]] for d in o["right_team_direction"]]
            rtd = [[-d[0], d[1]] for d in o["left_team_direction"]]
            o["left_team_direction"] = ltd
            o["right_team_direction"] = rtd
            # Swap tired/cards/active arrays too (left = us now)
            o["left_team_tired_factor"] = list(src["right_team_tired_factor"])
            o["left_team_yellow_card"] = list(src["right_team_yellow_card"])
            o["left_team_active"] = list(src["right_team_active"])
            # Flip ball possession
            if o["ball_owned_team"] == 0:
                o["ball_owned_team"] = 1
            elif o["ball_owned_team"] == 1:
                o["ball_owned_team"] = 0
            # Flip score ratio so we see our own goals first
            o["score"] = [src["score"][1], src["score"][0]]
            # active player index stays same (player within team)
            mirrored.append(o)
        return mirrored

    # Custom Analytics Storage
    stats[\"player_metrics\"] = {
        \"velocity_reward_increments\": {i: 0.0 for i in range(n_agents)},
        \"shooting_accuracy_indexes\": {i: 0.0 for i in range(n_agents)},
    }"""

assert old_rnn_init in code, "FAIL: rnn init block not found"
code = code.replace(old_rnn_init, new_rnn_init)

# ── 3. Rewrite the inference + step block ────────────────────────────────────
old_inference = """    while step < MAX_STEPS and not done:
        if isinstance(obs, (list, tuple)):
            obs_list = list(obs)
        else:
            obs_list = [obs]

        n_agents = len(obs_list)
        if n_agents == 0:
            break

        if actor_model is not None:
            with torch.no_grad():
                # Database Attribute Synchronization: scale underlying physical velocity vectors
                try:
                    raw_obs = env.unwrapped.observation()
                    for agent_idx in range(n_agents):
                        if agent_idx < len(raw_obs):
                            p_attrs = influencer._get_attrs(0, agent_idx)
                            if p_attrs and \"velocity\" in p_attrs:
                                raw_obs[agent_idx][\"left_team_direction\"] = [
                                    [float(dir_val[0] * p_attrs[\"velocity\"]), float(dir_val[1] * p_attrs[\"velocity\"])] 
                                    for dir_val in raw_obs[agent_idx][\"left_team_direction\"]
                                ]
                except Exception:
                    pass

                # Convert multi-agent dictionary elements to a structured matrix space pass
                match_features = feature_extractor.extract(raw_obs)
                
                # Check for feature shape mismatches and pad/truncate to 268 if necessary
                if match_features.shape[1] < 268:
                    pad = np.zeros((match_features.shape[0], 268 - match_features.shape[1]), dtype=np.float32)
                    match_features = np.hstack([match_features, pad])
                elif match_features.shape[1] > 268:
                    match_features = match_features[:, :268]

                obs_tensor = torch.FloatTensor(match_features).to(device)
                
                # Provide available actions mask so the network ignores actions >= 19
                avail_actions = torch.ones(n_agents, 33).to(device)
                avail_actions[:, 19:] = 0
                
                # Use recurrent states and masks
                action_tokens, _, rnn_states = actor_model(obs_tensor, rnn_states, masks, available_actions=avail_actions)
                raw_actions = action_tokens.cpu().numpy().astype(np.int32).flatten()
        else:
            raw_actions = np.array([random.randint(0, 18) for _ in range(n_agents)], dtype=np.int32)

        try:
            main_obs = env.unwrapped.observation()
            main_obs = (main_obs[0] if main_obs else {}) if isinstance(main_obs, list) else main_obs
        except Exception:
            main_obs = {}

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
                    vel = p_attrs.get(\"velocity\", 1.0)
                    rating = p_attrs.get(\"rating\", 3)
                    shooting_reward = p_attrs.get(\"rewards\", {}).get(\"shooting_reward\", 0.0)
                    
                    ball = main_obs.get(\"ball\", [0,0,0])
                    left_team = main_obs.get(\"left_team\", [])
                    if len(left_team) > agent_idx:
                        me = left_team[agent_idx]
                        dist = np.linalg.norm(np.array(me) - np.array(ball[:2]))
                        prox = 1.0 / (1.0 + dist)
                        
                        inc = prox * vel
                        stats[\"player_metrics\"][\"velocity_reward_increments\"][agent_idx] += inc
                        
                        if raw_actions[agent_idx] == 12: # ACTION_SHOT
                            sai = rating * shooting_reward
                            stats[\"player_metrics\"][\"shooting_accuracy_indexes\"][agent_idx] += sai
            except Exception as e:
                pass

        try:
            # Scale down the output tracking sequence to match the active player targets
            step_result = env.step(raw_actions[:n_agents])"""

new_inference = """    while step < MAX_STEPS and not done:
        # ── Fetch raw observations ──────────────────────────────────────
        try:
            raw_all = env.unwrapped.observation()
        except Exception:
            raw_all = []

        if not raw_all:
            break

        raw_home = raw_all[:N_HOME]
        raw_away_mirrored = mirror_obs_for_away(raw_all)

        # ── Database Attribute Velocity Scaling ─────────────────────────
        try:
            for i in range(N_HOME):
                attrs = influencer._get_attrs(0, i)
                if attrs and "velocity" in attrs:
                    v = attrs["velocity"]
                    raw_home[i]["left_team_direction"] = [
                        [float(d[0] * v), float(d[1] * v)] for d in raw_home[i]["left_team_direction"]
                    ]
            for i in range(N_AWAY):
                attrs = influencer._get_attrs(1, i)
                if attrs and "velocity" in attrs:
                    v = attrs["velocity"]
                    raw_away_mirrored[i]["left_team_direction"] = [
                        [float(d[0] * v), float(d[1] * v)] for d in raw_away_mirrored[i]["left_team_direction"]
                    ]
        except Exception:
            pass

        if actor_model is not None:
            with torch.no_grad():
                # Build 268-dim features for all 20 agents (home then away)
                home_feat = home_extractor.extract(raw_home)
                away_feat = away_extractor.extract(raw_away_mirrored)

                for feat in [home_feat, away_feat]:
                    pass  # shape guard happens below

                all_feat = np.vstack([home_feat, away_feat]).astype(np.float32)
                if all_feat.shape[1] < 268:
                    pad = np.zeros((all_feat.shape[0], 268 - all_feat.shape[1]), dtype=np.float32)
                    all_feat = np.hstack([all_feat, pad])
                elif all_feat.shape[1] > 268:
                    all_feat = all_feat[:, :268]

                obs_tensor = torch.FloatTensor(all_feat).to(device)

                avail_actions = torch.ones(n_agents, 33).to(device)
                avail_actions[:, 19:] = 0

                action_tokens, _, rnn_states = actor_model(
                    obs_tensor, rnn_states, masks, available_actions=avail_actions
                )
                raw_actions = action_tokens.cpu().numpy().astype(np.int32).flatten()
        else:
            raw_actions = np.array([random.randint(0, 18) for _ in range(n_agents)], dtype=np.int32)

        # ── Get main obs dict for influencer ───────────────────────────
        try:
            main_obs_list = env.unwrapped.observation()
            main_obs_home = main_obs_list[0] if main_obs_list else {}
            main_obs_away = main_obs_list[N_HOME] if len(main_obs_list) > N_HOME else {}
        except Exception:
            main_obs_home = {}
            main_obs_away = {}

        final_actions = np.zeros(n_agents, dtype=np.int32)

        # ── Home team (agents 0-9): apply influencer + no flip ─────────
        for i in range(N_HOME):
            action = int(np.asarray(raw_actions[i]).item())
            action = min(max(action, 0), 18)
            action = influencer.influence(team_idx=0, player_idx=i, action=action, obs=main_obs_home)
            final_actions[i] = action

            # Analytics
            try:
                attrs = influencer._get_attrs(0, i)
                if attrs:
                    vel = attrs.get("velocity", 1.0)
                    rating = attrs.get("rating", 3)
                    sr = attrs.get("rewards", {}).get("shooting_reward", 0.0)
                    lt = main_obs_home.get("left_team", [])
                    ball = main_obs_home.get("ball", [0, 0, 0])
                    if len(lt) > i:
                        dist = np.linalg.norm(np.array(lt[i]) - np.array(ball[:2]))
                        stats["player_metrics"]["velocity_reward_increments"][i] += (1.0 / (1.0 + dist)) * vel
                        if action == 12:
                            stats["player_metrics"]["shooting_accuracy_indexes"][i] += rating * sr
            except Exception:
                pass

        # ── Away team (agents 10-19): flip directions then apply influencer ──
        for i in range(N_AWAY):
            action = int(np.asarray(raw_actions[N_HOME + i]).item())
            action = min(max(action, 0), 18)
            # Mirror directional actions so Away team attacks correctly
            action = AWAY_ACTION_MIRROR.get(action, action)
            action = influencer.influence(team_idx=1, player_idx=i, action=action, obs=main_obs_away)
            final_actions[N_HOME + i] = action

            # Analytics
            try:
                attrs = influencer._get_attrs(1, i)
                global_idx = N_HOME + i
                if attrs:
                    vel = attrs.get("velocity", 1.0)
                    rating = attrs.get("rating", 3)
                    sr = attrs.get("rewards", {}).get("shooting_reward", 0.0)
                    rt = main_obs_away.get("right_team", [])
                    ball = main_obs_away.get("ball", [0, 0, 0])
                    if len(rt) > i:
                        dist = np.linalg.norm(np.array(rt[i]) - np.array(ball[:2]))
                        stats["player_metrics"]["velocity_reward_increments"][global_idx] += (1.0 / (1.0 + dist)) * vel
                        if action == 12:
                            stats["player_metrics"]["shooting_accuracy_indexes"][global_idx] += rating * sr
            except Exception:
                pass

        try:
            # Pass all 20 actions (10 home + 10 away) to the engine
            step_result = env.step(final_actions)"""

assert old_inference in code, "FAIL: inference block not found"
code = code.replace(old_inference, new_inference)

# ── 4. Fix the env.step call at the end since we renamed raw_actions → final_actions ──
old_step = "            step_result = env.step(raw_actions[:n_agents])"
# Already replaced above inside the block, but check for any remaining orphan
if old_step in code:
    code = code.replace(old_step, "            step_result = env.step(final_actions)")

SIM.write_text(code)
print("game_simulator.py upgraded to 10v10 actor vs actor mode!")
