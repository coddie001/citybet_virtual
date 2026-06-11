"""Broadcast policy: live status requires a confirmed MP4 on disk."""
import logging
import os
import time
from typing import Optional

from utils.db import Fixture, GfrDump, Season
from utils.virtual_schedule import (
    REAL_COUNTDOWN_MS,
    match_has_video,
    virtual_clock_ms,
    virtual_until_real_ms,
)

log = logging.getLogger(__name__)

MAX_VIDEO_RENDER_ATTEMPTS = 2
BROADCAST_LIVE_SEC = int(os.getenv("BROADCAST_LIVE_SEC", "600"))  # 10 min on-air window


def _dump_steps(dump: Optional[GfrDump]) -> int:
    if not dump or not dump.gfr_stats:
        return 0
    return int(
        dump.gfr_stats.get("total_steps") or dump.gfr_stats.get("steps") or 0
    )


def score_from_sim(fixture: Fixture, dump: Optional[GfrDump]) -> str:
    if fixture.score and str(fixture.score).strip() not in ("", "0-0", None):
        return str(fixture.score)
    if dump and dump.gfr_stats:
        stats = dump.gfr_stats
        if stats.get("score"):
            return str(stats["score"])
        hg = stats.get("home_goals") if stats.get("home_goals") is not None else stats.get("goals_home")
        ag = stats.get("away_goals") if stats.get("away_goals") is not None else stats.get("goals_away")
        if hg is not None and ag is not None:
            return f"{int(hg)}-{int(ag)}"
    return "0-0"


def _clear_broadcast_keys(pred: dict) -> dict:
    for key in ("_broadcast_started_at", "_live_started_at", "_live_stuck_at"):
        pred.pop(key, None)
    return pred


def complete_without_video(fixture: Fixture, dump: Optional[GfrDump], reason: str) -> None:
    pred = _clear_broadcast_keys(dict(fixture.predictions or {}))
    pred.pop("_video_render_attempts", None)
    fixture.predictions = pred
    fixture.status = "completed"
    fixture.settled = True
    fixture.score = score_from_sim(fixture, dump)
    fixture.outcome = fixture.outcome or reason


def begin_processing_countdowns(db) -> int:
    """Mark upcoming fixtures when 3 real minutes to kickoff — starts countdown + sim window."""
    changed = 0
    for season in db.query(Season).filter(Season.season_status == "active").all():
        clock = virtual_clock_ms(season, db)
        gwk_fixtures = (
            db.query(Fixture)
            .filter(
                Fixture.season_id == season.season_id,
                Fixture.status == "upcoming",
            )
            .order_by(Fixture.show_at_ms.asc())
            .all()
        )
        for f in gwk_fixtures:
            until_virt = int(f.show_at_ms or 0) - int(clock)
            until_real = virtual_until_real_ms(until_virt)
            pred = dict(f.predictions or {})
            if pred.get("_processing_started_at"):
                continue
            # Start at 3-min countdown OR catch up fixtures that missed the window.
            in_window = 0 < until_real <= REAL_COUNTDOWN_MS
            overdue = until_virt <= 0
            if not in_window and not overdue:
                continue
            pred["_processing_started_at"] = time.time()
            f.predictions = pred
            f.status = "upcoming"
            changed += 1
            log.info("Processing countdown started for %s (%.0fs to kickoff).", f.match_id, until_real / 1000)
            break
    if changed:
        db.commit()
    return changed


def purge_illegal_live(db) -> int:
    """Status stays upcoming until MP4 exists — never leave live without a file."""
    changed = 0
    for f in db.query(Fixture).filter(Fixture.status == "live").all():
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        if match_has_video(dump, f.match_id):
            continue
        pred = _clear_broadcast_keys(dict(f.predictions or {}))
        f.predictions = pred
        f.status = "upcoming"
        changed += 1
        log.info("Demoted live→upcoming (no MP4): %s", f.match_id)
    if changed:
        db.commit()
    return changed


def _past_kickoff(db, fixture: Fixture) -> bool:
    season = db.query(Season).filter(Season.season_id == fixture.season_id).first()
    if not season:
        return False
    clock = virtual_clock_ms(season, db)
    return int(fixture.show_at_ms or 0) <= int(clock)


def retry_or_complete_videoless(db, max_repairs: int = 1) -> int:
    """
    Past kickoff, sim done, still no MP4: retry render up to 2×, then complete with score.
    """
    from utils.video_repair import repair_one

    changed = 0
    repairs = 0
    for f in db.query(Fixture).filter(Fixture.status.in_(("upcoming", "live"))).all():
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        if match_has_video(dump, f.match_id):
            continue
        if _dump_steps(dump) < 100:
            continue
        if not _past_kickoff(db, f):
            continue

        pred = dict(f.predictions or {})
        attempts = int(pred.get("_video_render_attempts") or 0)

        if attempts < MAX_VIDEO_RENDER_ATTEMPTS and repairs < max_repairs:
            ok = repair_one(db, f.match_id)
            pred["_video_render_attempts"] = attempts + 1
            f.predictions = pred
            if f.status == "live":
                f.status = "upcoming"
            changed += 1
            repairs += 1
            log.info(
                "Video render attempt %d/%d for %s (ok=%s).",
                attempts + 1,
                MAX_VIDEO_RENDER_ATTEMPTS,
                f.match_id,
                ok,
            )
            if match_has_video(
                db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first(),
                f.match_id,
            ):
                continue

        if int(pred.get("_video_render_attempts") or 0) >= MAX_VIDEO_RENDER_ATTEMPTS:
            complete_without_video(f, dump, "no_video_after_retries")
            changed += 1
            log.warning("Completed %s without video after %d render attempts.", f.match_id, MAX_VIDEO_RENDER_ATTEMPTS)

    if changed:
        db.commit()
    return changed


def finalize_videos_before_promote(db, max_files: int = 3) -> int:
    """Remux/compress MP4s so promote_ready_to_live can see streamable files."""
    from utils.video_faststart import finalize_mp4, is_finalizable, needs_faststart
    from utils.video_compress import needs_reencode
    from utils.video_paths import VIDEO_DIR, video_path_for
    from utils.virtual_schedule import match_has_video

    done = 0
    for f in db.query(Fixture).filter(Fixture.status.in_(("upcoming", "live", "preparing"))).all():
        if done >= max_files:
            break
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        if match_has_video(dump, f.match_id):
            continue
        for path in (video_path_for(f.match_id), VIDEO_DIR / f"{f.match_id}_full_small.mp4"):
            if not path.is_file() or not is_finalizable(path, check_writing=True):
                continue
            if needs_faststart(path) or needs_reencode(path):
                if finalize_mp4(path, target_mb=4.5):
                    done += 1
                break
    return done


def promote_ready_to_live(db) -> int:
    """Set live only when MP4 is confirmed on disk (one per season)."""
    changed = 0
    for season in db.query(Season).filter(Season.season_status == "active").all():
        already_live = (
            db.query(Fixture)
            .filter(Fixture.season_id == season.season_id, Fixture.status == "live")
            .first()
        )
        if already_live:
            dump = db.query(GfrDump).filter(GfrDump.match_id == already_live.match_id).first()
            if not match_has_video(dump, already_live.match_id):
                pred = _clear_broadcast_keys(dict(already_live.predictions or {}))
                already_live.predictions = pred
                already_live.status = "upcoming"
                changed += 1
            continue

        candidates = (
            db.query(Fixture)
            .filter(
                Fixture.season_id == season.season_id,
                Fixture.status == "upcoming",
            )
            .order_by(Fixture.show_at_ms.asc())
            .all()
        )
        clock = virtual_clock_ms(season, db)
        for f in candidates:
            if int(f.show_at_ms or 0) > int(clock):
                continue
            dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
            if not match_has_video(dump, f.match_id):
                continue
            pred = _clear_broadcast_keys(dict(f.predictions or {}))
            f.predictions = pred
            f.status = "live"
            changed += 1
            log.info("Promoted to live (MP4 ready): %s", f.match_id)
            break

    if changed:
        db.commit()
    return changed


def manage_on_air_window(db) -> int:
    """Complete live fixtures 5 minutes after broadcast starts (MP4 must exist)."""
    now = time.time()
    changed = 0

    for f in db.query(Fixture).filter(Fixture.status == "live").all():
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        if not match_has_video(dump, f.match_id):
            pred = _clear_broadcast_keys(dict(f.predictions or {}))
            f.predictions = pred
            f.status = "upcoming"
            changed += 1
            continue

        pred = dict(f.predictions or {})
        pred.pop("_live_stuck_at", None)
        if "_broadcast_started_at" not in pred:
            pred["_broadcast_started_at"] = now
            f.predictions = pred
            changed += 1
            continue

        if now - float(pred["_broadcast_started_at"]) < BROADCAST_LIVE_SEC:
            continue

        pred = _clear_broadcast_keys(pred)
        f.predictions = pred
        f.status = "completed"
        f.settled = True
        if not f.score:
            f.score = score_from_sim(f, dump)
        changed += 1

    if changed:
        db.commit()
        log.info("On-air window: updated %d fixture(s).", changed)
    return changed


def fixture_ready_for_sim(fixture: Fixture, db) -> bool:
    """Worker may sim in the 3-min countdown window or for overdue kickoff backlog."""
    from utils.carousel_schedule import use_wall_clock_schedule
    from utils.virtual_schedule import fixture_progress_gameweek

    pred = dict(fixture.predictions or {})
    if use_wall_clock_schedule():
        if fixture.status not in ("upcoming", "preparing"):
            return False
        dump = db.query(GfrDump).filter(GfrDump.match_id == fixture.match_id).first()
        if _dump_steps(dump) >= 100:
            return False
        season = db.query(Season).filter(Season.season_id == fixture.season_id).first()
        if not season:
            return False
        prog = fixture_progress_gameweek(db, season.season_id) or 1
        if fixture.gameweek != prog:
            return False
        if fixture.status == "preparing":
            from utils.preparing_pipeline import pick_sim_target

            picked = pick_sim_target(db)
            return picked is not None and picked.match_id == fixture.match_id
        for f in (
            db.query(Fixture)
            .filter(
                Fixture.season_id == fixture.season_id,
                Fixture.status.in_(("upcoming", "preparing")),
                Fixture.gameweek == prog,
            )
            .order_by(Fixture.show_at_ms.asc())
            .all()
        ):
            d = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
            if _dump_steps(d) < 100:
                return f.match_id == fixture.match_id
        return False

    if pred.get("_processing_started_at"):
        return True
    season = db.query(Season).filter(Season.season_id == fixture.season_id).first()
    if not season:
        return False
    clock = virtual_clock_ms(season, db)
    until_virt = int(fixture.show_at_ms or 0) - int(clock)
    if until_virt <= 0:
        return True
    until_real = virtual_until_real_ms(until_virt)
    return 0 < until_real <= REAL_COUNTDOWN_MS


def finalize_after_sim(db, match_id=None) -> None:
    """Bytecode may set live/completed — restore wall-clock status until promote."""
    from utils.carousel_schedule import use_wall_clock_schedule
    from utils.db import Fixture as Fx

    now = time.time()
    q = db.query(Fx).filter(Fx.status.in_(("live", "completed")))
    if match_id is not None:
        q = q.filter(Fx.match_id == match_id)

    for f in q.all():
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        pred = _clear_broadcast_keys(dict(f.predictions or {}))
        has_vid = match_has_video(dump, f.match_id)
        start_raw = pred.get("_scheduled_start_at")

        if use_wall_clock_schedule() and start_raw is not None:
            try:
                start = float(start_raw)
            except (TypeError, ValueError):
                start = None
            if start is not None and has_vid and now >= start and _dump_steps(dump) >= 100:
                pred.setdefault("_broadcast_started_at", now)
                f.predictions = pred
                f.status = "live"
                continue
            if start is not None:
                f.predictions = pred
                f.status = "preparing"
                continue

        f.predictions = pred
        f.status = "upcoming"
    db.commit()


def purge_backlog_without_video(db) -> int:
    """One-shot: complete simmed fixtures that never got an MP4 (testing backlog)."""
    changed = 0
    for f in db.query(Fixture).filter(Fixture.status.in_(("live", "upcoming"))).all():
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        if match_has_video(dump, f.match_id):
            continue
        if f.status == "upcoming" and _dump_steps(dump) < 100:
            continue
        complete_without_video(f, dump, "backlog_no_video")
        changed += 1
        log.info("Backlog completed (no MP4): %s", f.match_id)
    if changed:
        db.commit()
    return changed
