"""Wall-clock preparing stage — one active countdown per league, sim on entry."""
from __future__ import annotations

import logging
import time
from typing import Optional

from sqlalchemy.orm import Session

from utils.db import Fixture, GfrDump, Season
from utils.virtual_schedule import fixture_progress_gameweek, match_has_video

log = logging.getLogger(__name__)


def _scheduled_start(pred: dict) -> Optional[float]:
    raw = pred.get("_scheduled_start_at")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _league_name(season: Season) -> str:
    return " ".join(season.tournament_name.split()[:-1])


def collapse_extra_preparing(db: Session) -> int:
    """Keep only the earliest preparing fixture per league; revert the rest to upcoming."""
    changed = 0
    for season in db.query(Season).filter(Season.season_status == "active").all():
        prep = (
            db.query(Fixture)
            .filter(Fixture.season_id == season.season_id, Fixture.status == "preparing")
            .all()
        )
        if len(prep) <= 1:
            continue
        prep.sort(key=lambda f: _scheduled_start(dict(f.predictions or {})) or float("inf"))
        for f in prep[1:]:
            pred = dict(f.predictions or {})
            pred.pop("_scheduled_start_at", None)
            pred.pop("_processing_started_at", None)
            pred.pop("_preparing_hook_at", None)
            f.predictions = pred
            f.status = "upcoming"
            changed += 1
            log.info("Reverted extra preparing→upcoming: %s (%s)", f.match_id, _league_name(season))
    if changed:
        db.commit()
    return changed


def on_preparing_entered(db: Session, fixture: Fixture) -> None:
    """Hook: fixture just entered preparing — mark for sim/render priority."""
    pred = dict(fixture.predictions or {})
    if pred.get("_preparing_hook_at"):
        return
    pred["_preparing_hook_at"] = time.time()
    pred.setdefault("_processing_started_at", time.time())
    fixture.predictions = pred
    db.commit()
    log.info("Preparing hook: %s queued for sim/render", fixture.match_id)


def ensure_preparing_hooks(db: Session) -> int:
    """Run hook for any preparing rows that missed it."""
    hooked = 0
    for f in db.query(Fixture).filter(Fixture.status == "preparing").all():
        pred = dict(f.predictions or {})
        if pred.get("_preparing_hook_at"):
            continue
        on_preparing_entered(db, f)
        hooked += 1
    return hooked


def repair_simmed_preparing_without_video(db: Session, max_repairs: int = 2) -> int:
    """Preparing + sim done + no MP4 → trigger render repair."""
    from utils.broadcast_gate import _dump_steps
    from utils.video_repair import repair_one

    done = 0
    for f in db.query(Fixture).filter(Fixture.status == "preparing").all():
        if done >= max_repairs:
            break
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        if _dump_steps(dump) < 100:
            continue
        if match_has_video(dump, f.match_id):
            continue
        if repair_one(db, f.match_id):
            done += 1
            log.info("Preparing render repair OK: %s", f.match_id)
        else:
            log.warning("Preparing render repair failed: %s", f.match_id)
    return done


def log_stuck_preparing(db: Session) -> int:
    """Warn when preparing is past kickoff without sim or video."""
    from utils.broadcast_gate import _dump_steps

    now = time.time()
    warned = 0
    for f in db.query(Fixture).filter(Fixture.status == "preparing").all():
        pred = dict(f.predictions or {})
        start = _scheduled_start(pred)
        if start is None or now < start + 30:
            continue
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        steps = _dump_steps(dump)
        has_vid = match_has_video(dump, f.match_id)
        if steps >= 100 and has_vid:
            continue
        log.warning(
            "Stuck preparing %s: overdue=%ds steps=%d video=%s proc=%s",
            f.match_id,
            int(now - start),
            steps,
            has_vid,
            bool(pred.get("_processing_started_at")),
        )
        warned += 1
    return warned


def pick_sim_target(db: Session) -> Optional[Fixture]:
    """Next fixture the worker should sim — earliest preparing without completed sim."""
    from utils.broadcast_gate import _dump_steps
    from utils.carousel_schedule import use_wall_clock_schedule

    if not use_wall_clock_schedule():
        return None

    candidates: list[tuple[float, Fixture]] = []
    for f in db.query(Fixture).filter(Fixture.status == "preparing").all():
        # Skip preparing fixtures that belong to a past gameweek — they are stuck
        # orphans that reset_off_progress_schedules will clean up. Selecting them
        # here would cause fixture_ready_for_sim to reject them and halt the worker.
        prog = fixture_progress_gameweek(db, f.season_id)
        if prog is not None and f.gameweek < prog:
            log.debug(
                "pick_sim_target: skipping off-progress preparing %s (GW%d < progress GW%d)",
                f.match_id,
                f.gameweek,
                prog,
            )
            continue
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        if _dump_steps(dump) >= 100:
            continue
        pred = dict(f.predictions or {})
        start = _scheduled_start(pred) or float("inf")
        candidates.append((start, f))

    if candidates:
        candidates.sort(key=lambda row: row[0])
        return candidates[0][1]

    for season in db.query(Season).filter(Season.season_status == "active").all():
        prog = fixture_progress_gameweek(db, season.season_id) or 1
        for f in (
            db.query(Fixture)
            .filter(
                Fixture.season_id == season.season_id,
                Fixture.status == "upcoming",
                Fixture.gameweek == prog,
            )
            .order_by(Fixture.show_at_ms.asc())
            .all()
        ):
            dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
            if _dump_steps(dump) >= 100:
                continue
            pred = dict(f.predictions or {})
            if not pred.get("_processing_started_at"):
                continue
            return f
    return None


def run_preparing_pipeline(db: Session) -> int:
    total = collapse_extra_preparing(db)
    total += ensure_preparing_hooks(db)
    total += repair_simmed_preparing_without_video(db)
    log_stuck_preparing(db)
    return total
