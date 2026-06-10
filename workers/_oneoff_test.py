"""
Standalone ONE-OFF match runner for validating game_simulator.py changes.
=========================================================================
Runs a single full match with synthetic teams through the SAME engine +
brain + PlayerActionInfluencer used in production, WITHOUT touching the
Postgres queue, the .worker.pid, or the live worker. Writes a dump + a
match_config json into a temp dir and renders an MP4 so the new movement
behaviour can be watched.

Usage (from project root):
    venv/bin/python -m workers._oneoff_test
"""
import os
import sys
import json
import uuid
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(1, str(PROJECT_ROOT / "tmarl"))

from workers.game_simulator import _run_simulation_child, render_dump_to_video, VIDEO_STORE

ROLES = {0: "GK", 1: "LB", 2: "CB", 3: "CB", 4: "RB",
         5: "LM", 6: "CM", 7: "CM", 8: "RM", 9: "ST", 10: "ST"}


def synth_attrs(seed_rating: float):
    attrs = {}
    for pos in range(11):
        role = ROLES[pos]
        attrs[pos] = {
            "player_id": str(uuid.uuid4()),
            "name": f"{role}{pos}",
            "role": role,
            "rating": seed_rating,
            "tired_factor": 0.0,
            "velocity": 1.05,
            "rewards": {
                "shooting_reward": 1.2 if pos in (9, 10) else 0.3,
                "passing_reward": 1.0,
                "defense_reward": 1.0 if pos in (1, 2, 3, 4) else 0.4,
            },
            "gfr_attrs": {},
        }
    return attrs


def build_cfg(home_name, away_name, home_attrs, away_attrs):
    def plist(attrs):
        return [{"name": attrs[p]["name"],
                 "strength": max(1, min(100, int(attrs[p]["rating"] * 20))),
                 "role": attrs[p]["role"],
                 "velocity": attrs[p]["velocity"]} for p in sorted(attrs)]
    return {"match_setup": {
        "home_team": home_name, "away_team": away_name,
        "teams": {
            home_name: {"shirt_color": "Red", "short_color": "White", "players": plist(home_attrs)},
            away_name: {"shirt_color": "Blue", "short_color": "Blue", "players": plist(away_attrs)},
        }}}


def main():
    match_id = str(uuid.uuid4())
    home_name, away_name = "TestHome", "TestAway"
    home_attrs = synth_attrs(3.4)   # slightly stronger
    away_attrs = synth_attrs(3.0)

    work = Path(tempfile.mkdtemp(prefix="oneoff_"))
    dump_dir = work / match_id
    dump_dir.mkdir(parents=True, exist_ok=True)
    sidecar = dump_dir / "_stats.json"

    cfg_path = dump_dir / f"match_{match_id}.json"
    cfg_path.write_text(json.dumps(build_cfg(home_name, away_name, home_attrs, away_attrs), indent=2))

    print(f"[oneoff] match_id={match_id}", flush=True)
    print(f"[oneoff] dump_dir={dump_dir}", flush=True)

    _run_simulation_child(match_id, home_name, away_name, home_attrs, away_attrs,
                          str(dump_dir), str(sidecar))

    stats = {}
    if sidecar.exists():
        stats = json.loads(sidecar.read_text())
    print(f"[oneoff] RESULT score={stats.get('score')} steps={stats.get('steps')} "
          f"possession={stats.get('possession')} corners={stats.get('corners')}", flush=True)

    dump_file = stats.get("dump_file")
    if dump_file and os.path.exists(dump_file):
        out = render_dump_to_video(dump_path=dump_file, match_config_path=str(cfg_path),
                                   output_dir=VIDEO_STORE, match_id=f"_oneoff_{match_id[:8]}")
        print(f"[oneoff] VIDEO={out.get('mp4')}", flush=True)
    else:
        print("[oneoff] No dump file produced — cannot render.", flush=True)


if __name__ == "__main__":
    main()
