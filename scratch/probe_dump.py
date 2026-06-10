#!/usr/bin/env python3
import pickle
import sys
from pathlib import Path

dump = Path(sys.argv[1])
prev = None
goals = []
with open(dump, "rb") as f:
    i = 0
    while True:
        try:
            step = pickle.load(f)
        except EOFError:
            break
        obs = step
        if isinstance(step, dict) and "observation" in step:
            obs = step["observation"]
        if isinstance(obs, (list, tuple)) and obs:
            obs = obs[0]
        score = obs.get("score") if isinstance(obs, dict) else None
        if score and score != prev:
            if prev is not None:
                side = "home" if score[0] > (prev[0] if prev else 0) else "away"
                goals.append({"step": i, "side": side, "score": list(score)})
            prev = list(score)
        i += 1
print("steps", i, "goals", goals[:10])
