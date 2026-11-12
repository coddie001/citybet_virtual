"""
BTTS + pitch-sanity test for the GFootball simulator (production code path).

Run:  venv/bin/python tests/sim_checks/test_btts_and_pitch.py
Saves to tests/sim_checks/results/btts_<timestamp>/ :
    report.md, results.json, <match>/{child.log,stats.json,*.dump,pitch.png}

What it does
  1. Plays real matches through workers.game_simulator._run_simulation_child (4 in parallel)
     until at least one finishes with BOTH teams scoring (max MAX_BATCHES batches).
  2. Re-reads every step of each saved .dump (all 22 players + ball, absolute coordinates,
     left team = home, right team = away) and checks:
        - players stay on the pitch   (x in [-1,1], y in [-0.42,0.42], small tolerance)
        - ball stays on the pitch while in play
        - goals are scored at the correct ends (home -> +x goal, away -> -x goal)
        - after every goal the match restarts from the centre spot
        - both teams keep a sensible shape (home defends -x, away defends +x)
        - no stuck outfield players, no teleporting during open play
        - possession is balanced and sums to 100% over owned steps
        - full-length game with normal turnovers and set-pieces
"""
import json
import multiprocessing as mp
import os
import pickle
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import numpy as np

PAIRS = [
    ("Fulham", "Arsenal"),
    ("Bayern Munich", "Borussia Dortmund"),
    ("Mallorca", "Barcelona"),
    ("Everton", "Southampton"),
    ("Eintracht Frankfurt", "Bayer Leverkusen"),
    ("Udinese", "Venezia"),
    ("Parma", "Como"),
    ("Las Palmas", "Espanyol"),
]
PARALLEL = 4
MAX_BATCHES = 2

X_LIM, Y_LIM = 1.0, 0.42
# How far a player may be outside the touch/goal lines (pitch units; 2.0 = full length).
OPEN_PLAY_EXCURSION_MAX = 0.12   # running slightly off the line while play is live
DEAD_BALL_EXCURSION_MAX = 0.15   # throw-in / corner / goal-kick / free-kick takers
HALFTIME_STEP = 1500
GAME_MODES = {0: "normal", 1: "kickoff", 2: "goal_kick", 3: "free_kick", 4: "corner", 5: "throw_in", 6: "penalty"}

OUT = ROOT / "tests" / "sim_checks" / "results" / ("btts_" + datetime.now().strftime("%Y%m%d_%H%M%S"))


# ----------------------------------------------------------------------------- run
def _child(label, home, away, attrs, d):
    import workers.game_simulator as gs
    fd = os.open(str(d / "child.log"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    sys.stdout = os.fdopen(1, "w", buffering=1, closefd=False)
    sys.stderr = os.fdopen(2, "w", buffering=1, closefd=False)
    gs._run_simulation_child(label, home, away, attrs[0], attrs[1], str(d), str(d / "stats.json"))


def run_batch(pairs):
    import workers.game_simulator as gs
    from utils.db import SessionLocal, Team
    db = SessionLocal()
    jobs = []
    for home, away in pairs:
        h = db.query(Team).filter(Team.team_name == home).first()
        a = db.query(Team).filter(Team.team_name == away).first()
        if not h or not a:
            print(f"skip {home} vs {away}: team not found", flush=True)
            continue
        label = f"{home}_vs_{away}".replace(" ", "_")
        d = OUT / label
        d.mkdir(parents=True, exist_ok=True)
        attrs = gs.load_team_attributes(db, h.team_id, a.team_id)
        p = mp.get_context("fork").Process(target=_child, args=(label, home, away, attrs, d))
        jobs.append((label, home, away, d, p))
    db.close()
    for *_, p in jobs:
        p.start()
    for *_, p in jobs:
        p.join()
    return [(label, home, away, d) for label, home, away, d, _ in jobs]


# ------------------------------------------------------------------------ analysis
def load_dump(path):
    steps = []
    with open(path, "rb") as f:
        while True:
            try:
                steps.append(pickle.load(f))
            except EOFError:
                break
    return steps


def analyse(dump_path, stats):
    raw = load_dump(dump_path)
    obs = []
    for t in raw:
        o = t["observation"] if isinstance(t, dict) and "observation" in t else t
        if isinstance(o, list):
            o = o[0]
        obs.append(o)
    n = len(obs)
    L = np.array([o["left_team"] for o in obs])    # (n,11,2) home
    R = np.array([o["right_team"] for o in obs])   # (n,11,2) away
    B = np.array([o["ball"] for o in obs])         # (n,3)
    score = np.array([o["score"] for o in obs])
    owner = np.array([o["ball_owned_team"] for o in obs])
    mode = np.array([o["game_mode"] for o in obs])
    res = {"dump_steps": n}
    checks = {}

    # --- 1. players on the pitch (measured as distance beyond the touch/goal lines)
    def excursion(P):
        return np.maximum(np.maximum(np.abs(P[..., 0]) - X_LIM, np.abs(P[..., 1]) - Y_LIM), 0.0)  # (n,11)
    ex = np.concatenate([excursion(L), excursion(R)], axis=1)          # (n,22)
    play = mode == 0
    ex_open = float(ex[play].max()) if play.any() else 0.0
    ex_dead = float(ex[~play].max()) if (~play).any() else 0.0
    res["players_beyond_lines"] = {
        "player_steps_strictly_on_pitch_pct": round(100.0 * float((ex == 0).mean()), 2),
        "max_excursion_open_play": round(ex_open, 3),
        "max_excursion_dead_ball": round(ex_dead, 3),
        "player_steps_beyond_lines_open_play": int((ex[play] > 0).sum()),
        "player_steps_beyond_lines_dead_ball": int((ex[~play] > 0).sum()),
        "total_player_steps": int(ex.size),
    }
    res["player_extent"] = {
        "x_min": round(float(min(L[..., 0].min(), R[..., 0].min())), 3),
        "x_max": round(float(max(L[..., 0].max(), R[..., 0].max())), 3),
        "y_min": round(float(min(L[..., 1].min(), R[..., 1].min())), 3),
        "y_max": round(float(max(L[..., 1].max(), R[..., 1].max())), 3),
    }
    checks["players_stay_on_pitch"] = ex_open <= OPEN_PLAY_EXCURSION_MAX and ex_dead <= DEAD_BALL_EXCURSION_MAX

    # --- 2. ball on the pitch while in play
    ball_out = (np.abs(B[:, 0]) > X_LIM + 0.02) | (np.abs(B[:, 1]) > Y_LIM + 0.02)
    res["ball_outside_in_open_play_steps"] = int((ball_out & play).sum())
    res["ball_max_height_z"] = round(float(B[:, 2].max()), 3)
    checks["ball_inside_pitch_in_open_play"] = int((ball_out & play).sum()) <= max(3, int(0.002 * n))

    # --- 3. goals at the right ends + centre restart
    gl = []
    for i in range(1, n):
        for side in (0, 1):
            if score[i][side] > score[i - 1][side]:
                bx = float(np.max(np.abs(B[max(0, i - 6):i, 0])))
                signed = float(B[max(0, i - 6):i, 0][np.argmax(np.abs(B[max(0, i - 6):i, 0]))])
                after = B[i:i + 120]
                centred = bool(len(after) and (np.linalg.norm(after[:, :2], axis=1).min() < 0.05))
                gl.append({"step": i, "scorer": "home" if side == 0 else "away", "score": score[i].tolist(),
                           "ball_x_before_goal": round(signed, 3), "restart_from_centre": centred})
    res["goals"] = gl
    # GFootball keeps each team's attacking direction fixed in this frame; a home goal must be at +x, away at -x
    right_end = [(g["scorer"] == "home" and g["ball_x_before_goal"] > 0.85) or
                 (g["scorer"] == "away" and g["ball_x_before_goal"] < -0.85) for g in gl]
    res["goal_end_ok"] = right_end
    res["final_score"] = score[-1].tolist()
    res["both_teams_scored"] = bool(score[-1][0] > 0 and score[-1][1] > 0)
    if gl:
        checks["goals_scored_at_correct_ends"] = all(right_end)
        checks["restart_from_centre_after_goals"] = all(g["restart_from_centre"] for g in gl)

    # --- 4. shape: home defends -x, away defends +x, teams not swapped/inverted
    out_h_x = L[:, 1:, 0]
    out_a_x = R[:, 1:, 0]
    cen_h, cen_a = out_h_x.mean(axis=1), out_a_x.mean(axis=1)
    res["mean_outfield_x"] = {"home": round(float(cen_h.mean()), 3), "away": round(float(cen_a.mean()), 3)}
    res["home_centroid_behind_away_pct"] = round(100.0 * float((cen_h < cen_a).mean()), 1)
    res["avg_team_depth_x_spread"] = {"home": round(float(out_h_x.std()), 3), "away": round(float(out_a_x.std()), 3)}
    res["avg_team_width_y_spread"] = {"home": round(float(L[:, 1:, 1].std()), 3), "away": round(float(R[:, 1:, 1].std()), 3)}
    checks["teams_in_own_halves_on_average"] = bool(cen_h.mean() < cen_a.mean() and res["home_centroid_behind_away_pct"] > 70)
    checks["both_teams_use_the_width"] = min(res["avg_team_width_y_spread"].values()) > 0.1

    # --- 5. stuck players and teleporting
    def path_len(P):
        return np.linalg.norm(np.diff(P, axis=0), axis=-1).sum(axis=0)  # (11,)
    pl_h, pl_a = path_len(L), path_len(R)
    res["distance_covered_per_player"] = {"home": [round(float(x), 1) for x in pl_h], "away": [round(float(x), 1) for x in pl_a]}
    checks["no_stuck_outfield_players"] = bool(pl_h[1:].min() > 1.0 and pl_a[1:].min() > 1.0)
    step_d = np.concatenate([np.linalg.norm(np.diff(L, axis=0), axis=-1), np.linalg.norm(np.diff(R, axis=0), axis=-1)], axis=1)
    tele = (step_d > 0.1).any(axis=1)
    tele_idx = np.where(tele)[0]
    goal_steps = [g["step"] for g in gl]
    explained = {"after_goal_reset": 0, "half_time": 0, "dead_ball_restart": 0}
    unexplained = []
    for i in tele_idx:
        j = i + 1
        if any(0 <= j - gs <= 3 for gs in goal_steps):
            explained["after_goal_reset"] += 1
        elif abs(j - HALFTIME_STEP) <= 5:
            explained["half_time"] += 1
        elif mode[i] != 0 or mode[j] != 0:
            explained["dead_ball_restart"] += 1
        else:
            unexplained.append(int(j))
    res["position_jumps"] = {"total": int(len(tele_idx)), **explained, "unexplained_steps": unexplained}
    smooth = step_d[~tele]
    res["max_player_step_speed_excluding_resets"] = round(float(smooth.max()), 4) if smooth.size else 0.0
    checks["no_unexplained_teleporting"] = len(unexplained) == 0

    # --- 6. possession over owned steps
    ph, pa = int((owner == 0).sum()), int((owner == 1).sum())
    owned = max(1, ph + pa)
    res["possession_pct_of_owned_steps"] = {"home": round(100 * ph / owned), "away": 100 - round(100 * ph / owned)}
    res["ball_free_steps"] = int((owner == -1).sum())
    res["turnovers_home_away"] = int(((owner[1:] != owner[:-1]) & (owner[1:] >= 0) & (owner[:-1] >= 0)).sum())
    checks["possession_balanced_15_85"] = 15 <= res["possession_pct_of_owned_steps"]["home"] <= 85

    # --- 7. normal game flow
    res["game_mode_steps"] = {GAME_MODES.get(int(m), str(m)): int((mode == m).sum()) for m in np.unique(mode)}
    res["ball_owner_changes_between_teams"] = res["turnovers_home_away"]
    checks["full_length_match"] = n >= 3000
    checks["normal_turnovers_and_setpieces"] = res["turnovers_home_away"] >= 20 and res["game_mode_steps"].get("normal", 0) > 0.5 * n

    res["checks"] = checks
    res["all_checks_pass"] = all(checks.values())
    res["_arrays"] = (L, R, B, score, owner)
    return res


def plot(res, path, title):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:  # matplotlib optional
        return f"plot skipped ({e})"
    L, R, B, score, owner = res["_arrays"]
    fig, ax = plt.subplots(1, 3, figsize=(21, 5.5))
    for a, (P, c, t) in zip(ax[:2], [(L, "tab:red", "Home positions (all steps)"), (R, "tab:blue", "Away positions (all steps)")]):
        a.scatter(P[::5, :, 0].ravel(), P[::5, :, 1].ravel(), s=1, alpha=0.15, color=c)
        a.set_title(t)
    a = ax[2]
    a.plot(B[:, 0], B[:, 1], lw=0.3, color="k", alpha=0.5)
    for g in res["goals"]:
        a.scatter([B[g["step"] - 1, 0]], [B[g["step"] - 1, 1]], s=120, marker="*", color="red" if g["scorer"] == "home" else "blue", zorder=5)
    a.set_title("Ball path, goals (red=home, blue=away)")
    for a in ax:
        a.plot([-1, 1, 1, -1, -1], [-0.42, -0.42, 0.42, 0.42, -0.42], color="green", lw=2)
        a.axvline(0, color="green", lw=1)
        a.set_xlim(-1.1, 1.1)
        a.set_ylim(-0.5, 0.5)
        a.set_aspect("equal")
    fig.suptitle(title)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return "pitch.png"


# ---------------------------------------------------------------------------- main
def process(d):
    sc = d / "stats.json"
    stats = json.loads(sc.read_text()) if sc.exists() else {}
    home, away = stats.get("home_team", "?"), stats.get("away_team", "?")
    dump = Path(stats["dump_file"]) if stats.get("dump_file") else None
    entry = {"match": f"{home} vs {away}", "dir": str(d), "score": stats.get("score"),
             "possession_home": stats.get("possession_home"), "possession_away": stats.get("possession_away")}
    if dump and dump.exists():
        a = analyse(dump, stats)
        entry["plot"] = plot(a, d / "pitch.png", f"{home} vs {away}  {a['final_score'][0]}-{a['final_score'][1]}")
        a.pop("_arrays")
        entry["analysis"] = a
    else:
        entry["error"] = "no dump file produced — see child.log"
    print(f"  {entry['match']}: {entry['score']}  both_scored={entry.get('analysis', {}).get('both_teams_scored')}  "
          f"pitch_checks_pass={entry.get('analysis', {}).get('all_checks_pass')}", flush=True)
    return entry


def main():
    global OUT
    results = []
    btts = None
    if "--reanalyze" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--reanalyze") + 1]).resolve()
        for d in sorted(p for p in OUT.iterdir() if p.is_dir()):
            e = process(d)
            results.append(e)
            if e.get("analysis", {}).get("both_teams_scored") and btts is None:
                btts = e
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        for b in range(MAX_BATCHES):
            pairs = PAIRS[b * PARALLEL:(b + 1) * PARALLEL]
            if not pairs:
                break
            print(f"Batch {b + 1}: {pairs}", flush=True)
            for label, home, away, d in run_batch(pairs):
                e = process(d)
                results.append(e)
                if e.get("analysis", {}).get("both_teams_scored") and btts is None:
                    btts = e
            if btts:
                break

    verdict = bool(btts and btts["analysis"]["all_checks_pass"])
    (OUT / "results.json").write_text(json.dumps({"verdict_pass": verdict, "btts_match": btts["match"] if btts else None,
                                                  "matches": results}, indent=2, default=str))
    lines = [f"# BTTS + pitch sanity test — {datetime.now():%Y-%m-%d %H:%M}", "",
             f"**Verdict: {'PASS' if verdict else 'FAIL'}**  (BTTS match: {btts['match'] if btts else 'none found'})", "",
             "| Match | Score | Both scored | Pitch/flow checks | Possession H/A |", "|---|---|---|---|---|"]
    for r in results:
        a = r.get("analysis", {})
        lines.append(f"| {r['match']} | {r['score']} | {a.get('both_teams_scored')} | "
                     f"{a.get('all_checks_pass')} | {a.get('possession_pct_of_owned_steps')} |")
    for r in results:
        a = r.get("analysis")
        if not a:
            continue
        lines += ["", f"## Detail: {r['match']} ({r['score']})", "", "| Check | Result |", "|---|---|"]
        lines += [f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in a["checks"].items()]
        lines += ["", "```json", json.dumps({k: v for k, v in a.items() if k not in ("checks",)}, indent=2, default=str), "```"]
    (OUT / "report.md").write_text("\n".join(lines))
    print("VERDICT", "PASS" if verdict else "FAIL", "| saved to", OUT, flush=True)



if __name__ == "__main__":
    main()
