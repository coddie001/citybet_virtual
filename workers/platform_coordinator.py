"""
Platform coordinator — automatic bootstrap and housekeeping.

Runs as a background loop (started by run.sh). Does NOT run simulations;
that remains workers.game_simulator.

Responsibilities:
  - Seed DB on first run (4 leagues, teams, players)
  - Generate fixtures for active seasons missing them
  - Reconcile stale fixture rows (outcome on non-completed)
  - Refresh live league tables
  - Aggregate player goal stats after matches complete
  - Roll seasons when all fixtures in a league are done
"""
import logging
import os
import sys
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.db import SessionLocal, Season, Fixture, GfrDump
from utils.league_table import persist_league_table
from utils.stats_aggregator import process_pending_match_stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Coordinator] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

INTERVAL_SEC = int(os.getenv("COORDINATOR_INTERVAL_SEC", "60"))


def ensure_seeded(db) -> bool:
    if db.query(Season).count() > 0:
        return False
    log.info("Empty database — running initial seed (4 leagues).")
    from utils.seeder import seed_database
    seed_database()
    return True


def ensure_fixtures(db) -> int:
    from workers.fixture_generator import generate_fixtures_for_season

    created = 0
    for season in db.query(Season).filter(Season.season_status == "active").all():
        count = db.query(Fixture).filter(Fixture.season_id == season.season_id).count()
        if count == 0:
            log.info("Generating fixtures for '%s'.", season.tournament_name)
            generate_fixtures_for_season(db, season)
            created += 1
    return created


def reconcile_stale_fixtures(db) -> int:
    """Clear outcome/score on fixtures wrongly left as upcoming with old outcomes."""
    stale = db.query(Fixture).filter(
        Fixture.status == "upcoming",
        Fixture.outcome.isnot(None),
    ).all()
    for f in stale:
        f.outcome = None
        f.score = "0-0"
        f.settled = False
        f.stats_recorded = False
    if stale:
        db.commit()
        log.info("Cleared stale outcomes on %d upcoming fixtures.", len(stale))

    reset = 0
    # Only fix fake completed 0-0 rows (broadcast_gate owns live/upcoming transitions).
    for f in db.query(Fixture).filter(Fixture.status == "completed").all():
        if f.score != "0-0":
            continue
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        steps = 0
        if dump and dump.gfr_stats:
            steps = int(
                dump.gfr_stats.get("total_steps")
                or dump.gfr_stats.get("steps")
                or 0
            )
        if steps >= 100:
            continue
        f.status = "upcoming"
        f.score = None
        f.outcome = None
        f.settled = False
        f.stats_recorded = False
        reset += 1
    if reset:
        db.commit()
        log.info("Re-queued %d fake 0-0 fixtures (no sim data) for replay.", reset)
    return len(stale) + reset


def supersede_stale_upcoming(db) -> int:
    """Drop superseded low-GW upcoming rows so API/carousel match sim progress."""
    from utils.virtual_schedule import fixture_progress_gameweek

    archived = 0
    for season in db.query(Season).filter(Season.season_status == "active").all():
        prog = fixture_progress_gameweek(db, season.season_id)
        if not prog:
            continue
        stale = (
            db.query(Fixture)
            .filter(
                Fixture.season_id == season.season_id,
                Fixture.status == "upcoming",
                Fixture.gameweek < prog,
            )
            .all()
        )
        for f in stale:
            f.status = "completed"
            f.settled = True
            if not f.score:
                f.score = "0-0"
            f.outcome = f.outcome or "superseded"
            archived += 1
    if archived:
        db.commit()
        log.info("Archived %d superseded upcoming fixtures (GW behind progress).", archived)
    return archived


def run_broadcast_gate(db) -> int:
    """Live requires MP4; retry failed renders twice; then score and complete."""
    from utils.broadcast_gate import purge_illegal_live
    from utils.carousel_schedule import run_wall_clock_broadcast_gate, use_wall_clock_schedule

    total = purge_illegal_live(db)

    if use_wall_clock_schedule():
        total += run_wall_clock_broadcast_gate(db)
        return total

    from utils.broadcast_gate import (
        begin_processing_countdowns,
        finalize_videos_before_promote,
        manage_on_air_window,
        promote_ready_to_live,
        retry_or_complete_videoless,
    )

    total += begin_processing_countdowns(db)
    total += retry_or_complete_videoless(db, max_repairs=1)
    total += finalize_videos_before_promote(db)
    total += promote_ready_to_live(db)
    total += manage_on_air_window(db)
    return total


def sync_season_gameweeks(db) -> int:
    """Keep season.current_gwk aligned with fixture simulation progress."""
    from utils.virtual_schedule import fixture_progress_gameweek

    updated = 0
    for season in db.query(Season).filter(Season.season_status == "active").all():
        gwk = fixture_progress_gameweek(db, season.season_id)
        if gwk and season.current_gwk != gwk:
            season.current_gwk = gwk
            updated += 1
    if updated:
        db.commit()
        log.info("Synced current_gwk for %d active seasons.", updated)
    return updated


def refresh_tables_and_stats(db) -> None:
    for season in db.query(Season).filter(Season.season_status == "active").all():
        persist_league_table(db, season.season_id)
    n = process_pending_match_stats(db)
    if n:
        log.info("Recorded player stats for %d newly completed matches.", n)


def check_season_transitions(db) -> None:
    from workers.season_manager import check_and_transition_seasons
    check_and_transition_seasons()


def consolidate_videos(db) -> int:
    from utils.video_consolidate import consolidate_videos as _consolidate

    n = _consolidate(db, max_moves=20)
    if n:
        log.info("Consolidated %d video(s) into videos/.", n)
    return n


def sweep_stuck_partials(db, max_repairs: int = 1) -> int:
    """Re-render quarantined partial MP4s from GFR dump when possible."""
    import uuid

    from utils.video_paths import VIDEO_DIR
    from utils.video_repair import repair_one

    repaired = 0
    for partial in sorted(VIDEO_DIR.glob("*_full.partial.mp4")):
        if repaired >= max_repairs:
            break
        mid_str = partial.name.replace("_full.partial.mp4", "")
        try:
            mid = uuid.UUID(mid_str)
        except ValueError:
            continue
        if repair_one(db, mid):
            partial.unlink(missing_ok=True)
            repaired += 1
            log.info("Re-rendered quarantined video for %s", mid_str)
    return repaired


def compress_oversized_videos(db) -> int:
    """Finalize MP4s: faststart remux + re-encode to 4000–5000 KB (one per cycle)."""
    from utils.video_compress import needs_reencode
    from utils.video_faststart import finalize_mp4, is_finalizable, needs_faststart
    from utils.video_paths import VIDEO_DIR
    from utils.virtual_schedule import resolve_video_file

    done = 0
    candidates: list = []
    for mp4 in sorted(VIDEO_DIR.glob("*_full.mp4"), key=lambda p: p.stat().st_size, reverse=True):
        if not is_finalizable(mp4, check_writing=True):
            continue
        if needs_faststart(mp4) or needs_reencode(mp4):
            candidates.append(mp4)
    for dump in db.query(GfrDump).order_by(GfrDump.match_id.desc()).limit(200).all():
        path = resolve_video_file(dump.match_id, dump)
        if (
            path
            and path.is_file()
            and is_finalizable(path, check_writing=True)
            and (needs_faststart(path) or needs_reencode(path))
            and path not in candidates
        ):
            candidates.append(path)

    for path in candidates:
        if done >= 1:
            break
        if finalize_mp4(path, target_mb=4.5):
            dump = db.query(GfrDump).filter(GfrDump.video_url.contains(path.name)).first()
            if dump:
                dump.video_url = str(path)
            done += 1
    if done:
        db.commit()
        log.info("Finalized %d match video(s) for web streaming.", done)
    return done


def run_once() -> None:
    db = SessionLocal()
    try:
        ensure_seeded(db)
        ensure_fixtures(db)
        reconcile_stale_fixtures(db)
        supersede_stale_upcoming(db)
        run_broadcast_gate(db)
        consolidate_videos(db)
        sweep_stuck_partials(db)
        from utils.video_faststart import sanitize_corrupt_videos

        sanitize_corrupt_videos()
        compress_oversized_videos(db)
        sync_season_gameweeks(db)
        refresh_tables_and_stats(db)
        check_season_transitions(db)
    except Exception:
        db.rollback()
        log.exception("Coordinator cycle failed.")
        raise
    finally:
        db.close()


def run_loop() -> None:
    from utils.carousel_schedule import schedule_mode

    log.info(
        "Platform coordinator started (interval=%ss, schedule=%s).",
        INTERVAL_SEC,
        schedule_mode(),
    )
    while True:
        try:
            run_once()
        except Exception:
            pass
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_once()
    else:
        run_loop()
