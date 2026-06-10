"""Auto-find a player's longest off-pitch streak and print it with context."""
import sys
import six.moves.cPickle as pickle
import numpy as np

dump = sys.argv[1]
side = sys.argv[2]          # L or R
pi = int(sys.argv[3])
NF = int(sys.argv[4]) if len(sys.argv) > 4 else 1300
key = "left_team" if side == "L" else "right_team"


def off(p):
    return abs(p[1]) > 0.42 or p[0] > 1.0 or p[0] < -1.0


frames = []
with open(dump, "rb") as f:
    while True:
        try:
            frames.append(pickle.load(f))
        except Exception:
            break
NF = min(NF, len(frames))

# find longest off streak
best = (0, 0)  # (len, start)
cur = 0
start = 0
for idx in range(NF):
    p = np.array(frames[idx]["observation"][key][pi], dtype=float)
    if off(p):
        if cur == 0:
            start = idx
        cur += 1
        if cur > best[0]:
            best = (cur, start)
    else:
        cur = 0
print(f"[trace] {side}[{pi}] longest off-pitch streak len={best[0]} start={best[1]}")

s = max(0, best[1] - 3)
e = min(NF, best[1] + best[0] + 3)
for idx in range(s, e):
    obs = frames[idx]["observation"]
    p = np.array(obs[key][pi], dtype=float)
    ball = np.array(obs.get("ball", [0, 0, 0])[:2], dtype=float)
    bot = obs.get("ball_owned_team", -1)
    bop = obs.get("ball_owned_player", -1)
    gm = obs.get("game_mode", 0)
    # rank of this player by distance to ball within own team (markers = closest)
    team = obs[key]
    d_self = np.linalg.norm(p - ball)
    rank = sum(1 for k in range(1, len(team))
               if k != pi and np.linalg.norm(np.array(team[k], dtype=float) - ball) < d_self)
    flag = "OFF" if off(p) else "   "
    print(f"f{idx:5d} gm{gm} {flag} pos=({p[0]:+.3f},{p[1]:+.3f}) "
          f"ball=({ball[0]:+.3f},{ball[1]:+.3f}) own=({bot},{bop}) "
          f"dball={d_self:.3f} ballrank={rank}")
