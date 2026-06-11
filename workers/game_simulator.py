"""Loads game_simulator from bytecode archive (full simulator)."""
import importlib.util
import logging
import os
import sys
import traceback
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_tmarl = _root / "tmarl"
_root_s, _tmarl_s = str(_root), str(_tmarl)
if _root_s not in sys.path:
    sys.path.insert(0, _root_s)
if _tmarl_s not in sys.path:
    sys.path.insert(1, _tmarl_s)
_prev = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = os.pathsep.join(
    [_root_s, _tmarl_s] + ([_prev] if _prev else [])
)

_model_link = _root / ".bytecode_archive" / "models" / "11_vs_11_kaggle" / "actor.pt"
_model_src = _root / "models" / "11_vs_11_kaggle" / "actor.pt"
if _model_src.is_file():
    _model_link.parent.mkdir(parents=True, exist_ok=True)
    if not _model_link.exists():
        _model_link.symlink_to(_model_src.resolve())

_pyc = _root / ".bytecode_archive" / "workers" / "game_simulator.cpython-313.pyc"
if not _pyc.is_file():
    raise ImportError(f"Missing bytecode archive: {_pyc}")

_spec = importlib.util.spec_from_file_location("workers.game_simulator_impl", _pyc)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

for _name, _val in _mod.__dict__.items():
    if not _name.startswith("_"):
        globals()[_name] = _val

from utils.video_paths import VIDEO_DIR as _CANONICAL_VIDEO_DIR

_CANONICAL_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_STORE = _CANONICAL_VIDEO_DIR
if hasattr(_mod, "VIDEO_STORE"):
    _mod.VIDEO_STORE = _CANONICAL_VIDEO_DIR

log = logging.getLogger(__name__)


def _simulate_target_fixture(db, fixture) -> bool:
    """Run sim+render for a specific fixture (bytecode queue ignores preparing status)."""
    from utils.db import Team

    home = db.query(Team).filter(Team.team_id == fixture.home_team_id).first()
    away = db.query(Team).filter(Team.team_id == fixture.away_team_id).first()
    if not home or not away:
        log.error("Teams missing for %s", fixture.match_id)
        fixture.status = "error"
        db.commit()
        return False

    dump_dir = _mod.DUMP_STORE / str(fixture.match_id)
    dump_dir.mkdir(parents=True, exist_ok=True)

    log.info(
        "[Sim] %s vs %s (GW%d, status=%s)",
        home.team_name,
        away.team_name,
        fixture.gameweek,
        fixture.status,
    )

    home_attrs, away_attrs = _mod.load_team_attributes(db, fixture.home_team_id, fixture.away_team_id)
    match_config = _mod.build_match_config(home, away, home_attrs, away_attrs)

    fixture.status = "live"
    db.commit()

    try:
        stats = _mod.run_simulation(
            fixture, home, away, home_attrs, away_attrs, match_config, dump_dir
        )
        video_paths = {"mp4": None, "gif": None}
        dump_file = stats.get("dump_file")
        if dump_file and os.path.exists(dump_file):
            video_paths = _mod.render_dump_to_video(
                dump_path=dump_file,
                match_config_path=stats["match_config_path"],
                output_dir=_CANONICAL_VIDEO_DIR,
                match_id=str(fixture.match_id),
            )

        _mod.settle_fixture(db, fixture, stats)
        _mod.persist_dump(db, fixture, stats, video_paths)
        _mod.update_season_gameweek(db, fixture.season_id, fixture.gameweek)

        from utils.carousel_schedule import use_wall_clock_schedule

        if use_wall_clock_schedule():
            pred = dict(fixture.predictions or {})
            start = pred.get("_scheduled_start_at")
            if start is not None:
                fixture.status = "preparing"
                fixture.settled = False
                fixture.predictions = pred
                db.commit()

        if hasattr(_mod, "PlayerActionInfluencer") and hasattr(_mod, "update_player_tiredness"):
            influencer = _mod.PlayerActionInfluencer(home_attrs, away_attrs)
            _mod.update_player_tiredness(db, fixture.home_team_id, influencer, 0)
            _mod.update_player_tiredness(db, fixture.away_team_id, influencer, 1)

        log.info("[Sim] Complete: %s %s %s", home.team_name, stats.get("score"), away.team_name)
        return True
    except Exception as exc:
        log.error("Simulation failed for %s: %s", fixture.match_id, exc)
        traceback.print_exc()
        fixture.status = "error"
        db.commit()
        return False


def simulate_next_fixture(db):
    """Sim the highest-priority preparing fixture, then finalize MP4 for web."""
    import time

    from utils.broadcast_gate import finalize_after_sim, fixture_ready_for_sim
    from utils.db import Fixture
    from utils.preparing_pipeline import pick_sim_target
    from utils.video_faststart import finalize_mp4, wait_for_finalizable
    from utils.video_paths import video_path_for

    target = pick_sim_target(db)
    if target is None:
        candidates = (
            db.query(Fixture)
            .filter(Fixture.status.in_(("upcoming", "preparing")))
            .order_by(Fixture.show_at_ms.asc())
            .limit(80)
            .all()
        )
        for cand in candidates:
            if fixture_ready_for_sim(cand, db):
                target = cand
                break
    if target is None:
        return False

    pred = dict(target.predictions or {})
    pred["_processing_started_at"] = pred.get("_processing_started_at") or time.time()
    target.predictions = pred
    db.commit()

    ok = False
    try:
        ok = _simulate_target_fixture(db, target)
    finally:
        canonical = video_path_for(target.match_id)
        if canonical.is_file():
            wait_for_finalizable(canonical, timeout_sec=120.0)
            finalize_mp4(canonical, target_mb=4.5)
        finalize_after_sim(db, target.match_id)

    return ok


globals()["simulate_next_fixture"] = simulate_next_fixture


def run_queue_continuously_wall_clock(max_matches=None):
    """
    Wall-clock-aware replacement for the bytecode run_queue_continuously.

    The bytecode version calls settle_fixture then marks the match 'completed'
    immediately, bypassing the preparing → live promotion window managed by
    the coordinator.  This version calls simulate_next_fixture (our wrapper)
    so that after every simulation the fixture is placed in 'preparing' status
    and the coordinator's promote_preparing_to_live is responsible for taking
    it live at the correct scheduled time.
    """
    import time as _time

    from utils.carousel_schedule import use_wall_clock_schedule
    from utils.db import SessionLocal

    if not use_wall_clock_schedule():
        # Legacy path — delegate to bytecode implementation unchanged.
        run_queue_continuously(max_matches=max_matches)
        return

    log.info("[Queue] Wall-clock mode: starting continuous sim loop.")
    done = 0
    idle_sleep = 15  # seconds to wait when nothing is ready

    while True:
        if max_matches is not None and done >= max_matches:
            log.info("[Queue] Reached max_matches=%d — stopping.", max_matches)
            break

        db = SessionLocal()
        try:
            ok = simulate_next_fixture(db)
        except Exception as exc:
            log.exception("[Queue] Unexpected error in simulate_next_fixture: %s", exc)
            ok = False
        finally:
            db.close()

        if ok:
            done += 1
            log.info("[Queue] Simulated %d fixture(s) so far.", done)
            # Small gap so the coordinator can update schedule state before
            # the next fixture is picked.
            _time.sleep(2)
        else:
            # Nothing ready yet — wait before checking again.
            _time.sleep(idle_sleep)


globals()["run_queue_continuously"] = run_queue_continuously_wall_clock


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CityBet Virtuals GFR Simulator")
    parser.add_argument(
        "--mode",
        choices=["one", "gameweek", "all"],
        default="one",
        help="one=next fixture, gameweek=full GWK, all=continuous queue",
    )
    parser.add_argument("--gameweek", type=int, default=1)
    parser.add_argument("--max", type=int, default=None)
    args = parser.parse_args()

    if args.mode == "one":
        from utils.db import SessionLocal

        db = SessionLocal()
        try:
            simulate_next_fixture(db)
        finally:
            db.close()
    elif args.mode == "gameweek":
        run_gameweek(args.gameweek)
    elif args.mode == "all":
        run_queue_continuously_wall_clock(max_matches=args.max)
