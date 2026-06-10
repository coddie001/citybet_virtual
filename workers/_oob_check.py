"""Scan a .dump for vanished players: team-array shrink, inactive flags,
red/yellow cards, and far out-of-bounds positions."""
import sys
import glob
import os
import six.moves.cPickle as pickle
import numpy as np

dump = sys.argv[1] if len(sys.argv) > 1 else sorted(
    glob.glob("/tmp/oneoff_*/*/*.dump"), key=os.path.getmtime)[-1]
print(f"[chk] dump={dump}")

frames = []
with open(dump, "rb") as f:
    while True:
        try:
            frames.append(pickle.load(f))
        except Exception:
            break
print(f"[chk] frames={len(frames)}")

prev_lcount = prev_rcount = None
for idx, fr in enumerate(frames):
    obs = fr.get("observation", {})
    lt = np.array(obs.get("left_team", []), dtype=float)
    rt = np.array(obs.get("right_team", []), dtype=float)
    lc, rc = len(lt), len(rt)
    if lc != prev_lcount or rc != prev_rcount:
        print(f"   frame {idx:5d}: left_team={lc} right_team={rc}")
        prev_lcount, prev_rcount = lc, rc

# card / active summary at end
last = frames[-1].get("observation", {})
for side in ("left", "right"):
    yc = np.array(last.get(f"{side}_team_yellow_card", []), dtype=float)
    ac = np.array(last.get(f"{side}_team_active", []), dtype=float)
    print(f"[chk] {side}: active={ac.tolist()} yellow={yc.tolist()}")

# far OOB (truly off screen): |x|>1.1 or |y|>0.48
far = 0
for idx, fr in enumerate(frames):
    obs = fr.get("observation", {})
    for side in ("left_team", "right_team"):
        arr = np.array(obs.get(side, []), dtype=float)
        for pi, p in enumerate(arr):
            if abs(p[0]) > 1.1 or abs(p[1]) > 0.48:
                far += 1
                if far <= 10:
                    print(f"   FAR {side}[{pi}] frame {idx} pos=({p[0]:+.3f},{p[1]:+.3f})")
print(f"[chk] far-oob occurrences={far}")
