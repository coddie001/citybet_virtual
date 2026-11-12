"""
Simulation checks — run with:  venv/bin/python tests/sim_checks/run_sim_checks.py
Results saved to tests/sim_checks/results/<timestamp>/

PROBE  : verifies whether gfootball already flips right-team observations
         (if yes, mirror_obs_for_away() flips them a SECOND time).
TEST 1 : full match with CURRENT logic (mirror_obs_for_away applied).
TEST 2 : same fixture, away obs passed straight from gfootball (no extra mirror).
"""
import json
import sys
import io
import contextlib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np
import workers.game_simulator as gs
from utils.db import SessionLocal, Team

HOME, AWAY = sys.argv[1] if len(sys.argv) > 1 else "Fulham", sys.argv[2] if len(sys.argv) > 2 else "Arsenal"
OUT = ROOT / "tests" / "sim_checks" / "results" / datetime.now().strftime("%Y%m%d_%H%M%S")
OUT.mkdir(parents=True, exist_ok=True)


def probe():
    import gfootball.env as football_env
    env = football_env.create_environment(
        env_name="11_vs_11_kaggle", representation="raw", rewards="scoring",
        number_of_left_players_agent_controls=10, number_of_right_players_agent_controls=10,
        other_config_options={"action_set": "full"},
    )
    obs = env.reset()
    for _ in range(30):
        obs, *_ = env.step(np.zeros(20, dtype=np.int32))
    env.close()
    home0, away0 = obs[0], obs[10]
    real_away_positions = np.array(home0["right_team"])
    away_view_left = np.array(away0["left_team"])
    gf_flips = bool(np.allclose(away_view_left, -real_away_positions, atol=1e-4))
    double = gs.mirror_obs_for_away(list(obs))[0]
    after_mirror_left = np.array(double["left_team"])
    sees_home_as_self = bool(np.allclose(after_mirror_left, np.array(home0["left_team"]), atol=1e-4))
    return {
        "gfootball_already_flips_right_obs": gf_flips,
        "after_mirror_away_agent_thinks_home_players_are_its_own": sees_home_as_self,
        "ball_real": list(map(float, home0["ball"][:2])),
        "ball_seen_by_away_from_gfootball": list(map(float, away0["ball"][:2])),
        "ball_seen_by_away_after_mirror": list(map(float, double["ball"][:2])),
        "away_ball_owned_team_gf_vs_mirrored": [int(away0["ball_owned_team"]), int(double["ball_owned_team"])],
    }


def _child(label, attrs, d):
    """Runs in its own process: _run_simulation_child ends with sys.exit()."""
    import os
    home_attrs, away_attrs = attrs
    if label == "test2_no_double_mirror":
        gs.mirror_obs_for_away = lambda raw: list(raw[10:20])
    fd = os.open(str(d / "child.log"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    sys.stdout = os.fdopen(1, "w", buffering=1, closefd=False)
    sys.stderr = os.fdopen(2, "w", buffering=1, closefd=False)
    gs._run_simulation_child(label, HOME, AWAY, home_attrs, away_attrs, str(d), str(d / "stats.json"))


def collect(label):
    d = OUT / label
    log = (d / "child.log").read_text(errors="ignore") if (d / "child.log").exists() else ""
    final = [l for l in log.splitlines() if "FINAL" in l or "goal!" in l]
    sidecar = d / "stats.json"
    stats = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    return {"final_lines": final, "score": stats.get("score"), "steps": stats.get("steps")}


def main():
    db = SessionLocal()
    h = db.query(Team).filter(Team.team_name == HOME).first()
    a = db.query(Team).filter(Team.team_name == AWAY).first()
    attrs = gs.load_team_attributes(db, h.team_id, a.team_id)
    db.close()

    summary = {"fixture": f"{HOME} vs {AWAY}",
               "db_attrs_sample": {"home": {k: {x: v[x] for x in ("name", "rating", "velocity", "tired_factor")} for k, v in list(attrs[0].items())[:3]},
                                   "away": {k: {x: v[x] for x in ("name", "rating", "velocity", "tired_factor")} for k, v in list(attrs[1].items())[:3]}},
               "home_player_positions": sorted(attrs[0].keys())}
    summary["probe"] = probe()
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("PROBE", json.dumps(summary["probe"], indent=2), flush=True)

    import multiprocessing as mp
    labels = ("test1_current_logic", "test2_no_double_mirror")
    procs = []
    for label in labels:
        (OUT / label).mkdir(exist_ok=True)
        p = mp.get_context("fork").Process(target=_child, args=(label, attrs, OUT / label))
        p.start()
        procs.append(p)
    for p in procs:
        p.join()
    for label in labels:
        summary[label] = collect(label)
        print(label, summary[label]["score"], summary[label]["final_lines"][-3:], flush=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    print("Saved to", OUT, flush=True)


if __name__ == "__main__":
    main()
