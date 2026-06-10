"""Report players genuinely off the pitch across the whole match."""
import sys, glob, os
import six.moves.cPickle as pickle
import numpy as np

dump = sys.argv[1] if len(sys.argv) > 1 else sorted(
    glob.glob("/tmp/oneoff_*/*/*.dump"), key=os.path.getmtime)[-1]
frames = []
with open(dump, "rb") as f:
    while True:
        try:
            frames.append(pickle.load(f))
        except Exception:
            break
NF = len(frames)
print(f"[edge] dump={dump} frames={NF}")

def off(p):
    return abs(p[1]) > 0.42 or p[0] > 1.0 or p[0] < -1.0

rec = {}
worst_frame = (0, 0)
for idx in range(NF):
    obs = frames[idx]["observation"]
    n_off = 0
    for side, key in (("L", "left_team"), ("R", "right_team")):
        for pi, p in enumerate(np.array(obs.get(key, []), dtype=float)):
            if off(p):
                r = rec.setdefault((side, pi), [0, 0, 0])
                r[0] += 1; r[1] += 1; r[2] = max(r[2], r[1]); n_off += 1
            else:
                r = rec.get((side, pi))
                if r: r[1] = 0
    if n_off > worst_frame[1]:
        worst_frame = (idx, n_off)

print("[edge] players ever off-pitch (count / longest streak):")
for k in sorted(rec):
    c, _, mx = rec[k]
    if c > 0:
        print(f"   {k[0]}[{k[1]:2d}] off={c:5d}/{NF}  longest_streak={mx}")
print(f"[edge] worst single frame: idx={worst_frame[0]} players_off={worst_frame[1]}")
