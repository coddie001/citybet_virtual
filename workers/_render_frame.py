"""Render specific frames of a dump to PNG to verify players are on the pitch."""
import sys
import os
import cv2
import six.moves.cPickle as pickle
sys.path.insert(0, os.path.expanduser("~/projects/citybet_virtuals/utils"))
from draw_match import GameReplayVisualizer

dump = sys.argv[1]
idxs = [int(a) for a in sys.argv[2:]] or [200, 500, 905]

frames = []
with open(dump, "rb") as f:
    while True:
        try:
            frames.append(pickle.load(f))
        except Exception:
            break

viz = GameReplayVisualizer(headless=True)
out_dir = os.path.expanduser("~/projects/citybet_virtuals/videos")
os.makedirs(out_dir, exist_ok=True)
for i in idxs:
    obs = frames[i].get("observation", {})
    rgb = viz._draw_frame(obs)
    p = os.path.join(out_dir, f"_frame_{i}.png")
    cv2.imwrite(p, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    print(f"saved {p}")
viz.quit()
