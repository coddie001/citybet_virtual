"""
Wall-clock carousel scheduling (revert: CAROUSEL_SCHEDULE_MODE=legacy).

Upcoming fixtures → worker assigns scheduled_start_at → preparing → live at start time.
Carousel lists by fixture status + schedule; MP4 is only required for the live stream drawer.
Per league: first queued game +1 min, each next +3 min. Queue scan every 5 min.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from utils.db import Fixture, GfrDump, Season, Team
from utils.virtual_schedule import (
    REAL_COUNTDOWN_MS,
    effective_fixture_status,
    fixture_progress_gameweek,
    match_has_video,
)

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_ROOT / ".carousel_schedule_state.json"

FIRST_START_OFFSET_SEC = 60
INTERVAL_SEC = 180
QUEUE_SCAN_INTERVAL_SEC = int(os.getenv("SCHEDULE_QUEUE_INTERVAL_SEC", "300"))
COUNTDOWN_SEC = REAL_COUNTDOWN_MS // 1000


def schedule_mode() -> str:
    return os.getenv("CAROUSEL_SCHEDULE_MODE", "wall_clock").strip().lower()


def use_wall_clock_schedule() -> bool:
    return schedule_mode() != "legacy"


def _load_state() -> dict:
    try:
        if STATE_FILE.is_file():
            return json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state))
    except OSError as exc:
        log.warning("Could not persist schedule state: %s", exc)


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


def _should_run_queue_batch() -> bool:
    state = _load_state()
    last = float(state.get("last_queue_at") or 0)
    return time.time() - last >= QUEUE_SCAN_INTERVAL_SEC


def _mark_queue_batch() -> None:
    state = _load_state()
    state["last_queue_at"] = time.time()
    _save_state(state)


def _fixture_has_video(db: Session, fixture: Fixture) -> bool:
    dump = db.query(GfrDump).filter(GfrDump.match_id == fixture.match_id).first()
    return match_has_video(dump, fixture.match_id)


def _last_scheduled_start(db: Session, season_id) -> Optional[float]:
    latest: Optional[float] = None
    for f in (
        db.query(Fixture)
        .filter(
            Fixture.season_id == season_id,
            Fixture.status.in_(("upcoming", "preparing", "live")),
        )
        .all()
    ):
        start = _scheduled_start(dict(f.predictions or {}))
        if start is not None and (latest is None or start > latest):
            latest = start
    return latest


def enqueue_video_ready_immediate(db: Session) -> int:
    """First upcoming fixture per league at progress GW: preparing in 1 min (sim runs during countdown)."""
    now = time.time()
    changed = 0
    for season in db.query(Season).filter(Season.season_status == "active").all():
        active_prep = (
            db.query(Fixture)
            .filter(Fixture.season_id == season.season_id, Fixture.status == "preparing")
            .count()
        )
        if active_prep > 0:
            continue
        if _last_scheduled_start(db, season.season_id) is not None:
            continue
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
            pred = dict(f.predictions or {})
            if _scheduled_start(pred) is not None:
                continue
            pred["_scheduled_start_at"] = now + FIRST_START_OFFSET_SEC
            f.predictions = pred
            f.status = "preparing"
            changed += 1
            log.info("Immediate schedule %s (%s GW%d) in 60s", f.match_id, _league_name(season), prog)
            from utils.preparing_pipeline import on_preparing_entered

            on_preparing_entered(db, f)
            break
    if changed:
        db.commit()
    return changed


def enqueue_scheduled_fixtures(db: Session) -> int:
    """Assign start times to upcoming fixtures (batch every 5 min)."""
    if not _should_run_queue_batch():
        return 0

    now = time.time()
    changed = 0

    for season in db.query(Season).filter(Season.season_status == "active").all():
        if (
            db.query(Fixture)
            .filter(Fixture.season_id == season.season_id, Fixture.status == "preparing")
            .count()
            > 0
        ):
            continue
        prog = fixture_progress_gameweek(db, season.season_id) or 1
        candidates = []
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
            pred = dict(f.predictions or {})
            if _scheduled_start(pred) is not None:
                continue
            candidates.append(f)

        if not candidates:
            continue

        last = _last_scheduled_start(db, season.season_id)
        next_start = (now + FIRST_START_OFFSET_SEC) if last is None else max(now + FIRST_START_OFFSET_SEC, last + INTERVAL_SEC)

        f = candidates[0]
        pred = dict(f.predictions or {})
        pred["_scheduled_start_at"] = next_start
        f.predictions = pred
        f.status = "preparing"
        changed += 1
        log.info(
            "Scheduled %s (%s) preparing → live at %s",
            f.match_id,
            _league_name(season),
            time.strftime("%H:%M:%S", time.localtime(next_start)),
        )
        from utils.preparing_pipeline import on_preparing_entered

        on_preparing_entered(db, f)

    if changed:
        db.commit()
    _mark_queue_batch()
    return changed


def promote_preparing_to_live(db: Session) -> int:
    """Preparing/upcoming → live when scheduled start reached and sim complete (≥100 steps)."""
    from utils.broadcast_gate import _dump_steps

    now = time.time()
    changed = 0
    for f in db.query(Fixture).filter(Fixture.status.in_(("preparing", "upcoming"))).all():
        pred = dict(f.predictions or {})
        start = _scheduled_start(pred)
        if start is None or now < start:
            continue
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        if _dump_steps(dump) < 100:
            log.info("Kickoff reached but sim pending for %s — waiting", f.match_id)
            continue
        if not match_has_video(dump, f.match_id):
            log.info("Kickoff reached but video pending for %s — waiting", f.match_id)
            continue
        pred.setdefault("_broadcast_started_at", now)
        f.predictions = pred
        prev = f.status
        f.status = "live"
        changed += 1
        log.info("Promoted %s→live: %s", prev, f.match_id)
    if changed:
        db.commit()
    return changed


def recover_stale_broadcasts(db: Session) -> int:
    """Complete fixtures stuck past the 10-min broadcast window (including demoted/zombie rows)."""
    from utils.broadcast_gate import BROADCAST_LIVE_SEC, _clear_broadcast_keys, score_from_sim

    now = time.time()
    changed = 0

    for f in db.query(Fixture).filter(Fixture.status.in_(("upcoming", "preparing", "live"))).all():
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        pred = dict(f.predictions or {})
        started = pred.get("_broadcast_started_at")

        if started is not None:
            try:
                if now - float(started) >= BROADCAST_LIVE_SEC:
                    pred = _clear_broadcast_keys(pred)
                    f.predictions = pred
                    f.status = "completed"
                    f.settled = True
                    if not f.score:
                        f.score = score_from_sim(f, dump)
                    changed += 1
                    log.info("Recovered stale broadcast (started): %s", f.match_id)
            except (TypeError, ValueError):
                pass
            continue

        if f.status not in ("upcoming", "preparing"):
            continue
        start = _scheduled_start(pred)
        if start is None or now - start <= BROADCAST_LIVE_SEC:
            continue
        if not match_has_video(dump, f.match_id):
            continue
        pred = _clear_broadcast_keys(pred)
        f.predictions = pred
        f.status = "completed"
        f.settled = True
        if not f.score:
            f.score = score_from_sim(f, dump)
        changed += 1
        log.info("Recovered zombie fixture (missed promotion): %s", f.match_id)

    if changed:
        db.commit()
    return changed


def countdown_for_scheduled(fixture: Fixture, now: Optional[float] = None) -> dict:
    """Backend countdown for carousel card — preparing shows full time-to-kickoff."""
    now = now if now is not None else time.time()
    pred = dict(fixture.predictions or {})
    start = _scheduled_start(pred)
    if start is None:
        return {
            "next_match_id": str(fixture.match_id),
            "show_at_ms": int(fixture.show_at_ms or 0),
            "scheduled_start_at_ms": None,
            "ms_until_kickoff": 0,
            "in_countdown_window": False,
            "countdown_seconds": 0,
            "is_kickoff": fixture.status == "live",
            "formatted": "00:00",
            "countdown_real_ms": True,
        }

    is_live = fixture.status == "live"
    if is_live:
        return {
            "next_match_id": str(fixture.match_id),
            "show_at_ms": int(fixture.show_at_ms or 0),
            "scheduled_start_at_ms": int(start * 1000),
            "ms_until_kickoff": 0,
            "in_countdown_window": False,
            "countdown_seconds": 0,
            "is_kickoff": True,
            "formatted": "00:00",
            "countdown_real_ms": True,
        }

    until_sec = start - now
    until_ms = int(max(0.0, until_sec) * 1000)
    is_preparing = fixture.status == "preparing"
    # Preparing = up next on carousel — always count down to scheduled kickoff.
    if is_preparing and until_sec > 0:
        in_window = True
        seconds = max(0, int(until_sec + 0.999))
    else:
        in_window = 0 < until_sec <= COUNTDOWN_SEC
        seconds = min(COUNTDOWN_SEC, max(0, int(until_sec + 0.999))) if in_window else 0
    mm, ss = divmod(seconds, 60)

    return {
        "next_match_id": str(fixture.match_id),
        "show_at_ms": int(fixture.show_at_ms or 0),
        "scheduled_start_at_ms": int(start * 1000),
        "ms_until_kickoff": until_ms,
        "in_countdown_window": in_window,
        "countdown_seconds": seconds,
        "is_kickoff": False,
        "formatted": f"{mm:02d}:{ss:02d}" if in_window else "00:00",
        "countdown_real_ms": True,
    }


def _serialize_carousel_item(db: Session, fixture: Fixture, league_name: str, step: int, now: float) -> dict:
    home = db.query(Team).filter(Team.team_id == fixture.home_team_id).first()
    away = db.query(Team).filter(Team.team_id == fixture.away_team_id).first()
    dump = db.query(GfrDump).filter(GfrDump.match_id == fixture.match_id).first()
    pred = dict(fixture.predictions or {})
    start = _scheduled_start(pred)
    has_video = match_has_video(dump, fixture.match_id)
    eff_status = effective_fixture_status(fixture, dump)

    return {
        "carousel_id": str(fixture.match_id),
        "carousel_step": step,
        "match_id": str(fixture.match_id),
        "season_id": str(fixture.season_id),
        "league_name": league_name,
        "gameweek": fixture.gameweek,
        "show_at_ms": int(fixture.show_at_ms or 0),
        "scheduled_start_at_ms": int(start * 1000) if start else None,
        "status": eff_status,
        "has_video": has_video,
        "is_next": step == 0 and eff_status in ("preparing", "upcoming"),
        "fixture_image_url": fixture.fixture_image_url,
        "home_team": {"id": str(home.team_id), "name": home.team_name} if home else None,
        "away_team": {"id": str(away.team_id), "name": away.team_name} if away else None,
        "countdown": countdown_for_scheduled(fixture, now),
    }


def _carousel_sort_key(
    fixture: Fixture,
    scheduled_start: Optional[float],
    dump: Optional[GfrDump] = None,
) -> tuple:
    """Live first, then preparing/upcoming by wall-clock start, then unscheduled upcoming."""
    status = effective_fixture_status(fixture, dump)
    if status == "live":
        tier = 0
    elif status == "preparing":
        tier = 1
    elif scheduled_start is not None:
        tier = 2
    else:
        tier = 3
    time_key = scheduled_start if scheduled_start is not None else float(fixture.show_at_ms or 0)
    return (tier, time_key, str(fixture.match_id))


def build_carousel_response(db: Session, limit: int = 24) -> dict:
    """Global carousel: live stays until backend completes (10-min on-air window)."""
    now = time.time()
    now_ms = int(now * 1000)
    rows: list[tuple[tuple, Fixture, str]] = []

    for season in db.query(Season).filter(Season.season_status == "active").all():
        league = _league_name(season)
        prog = fixture_progress_gameweek(db, season.season_id) or (season.current_gwk or 1)
        for f in (
            db.query(Fixture)
            .filter(
                Fixture.season_id == season.season_id,
                Fixture.status.in_(("upcoming", "preparing", "live")),
                Fixture.gameweek == prog,
            )
            .order_by(Fixture.show_at_ms.asc())
            .all()
        ):
            dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
            pred = dict(f.predictions or {})
            start = _scheduled_start(pred)
            rows.append((_carousel_sort_key(f, start, dump), f, league))

    rows.sort(key=lambda r: r[0])
    trimmed = rows[:limit]
    items = [_serialize_carousel_item(db, f, league, i, now) for i, (_, f, league) in enumerate(trimmed)]

    return {
        "mode": "wall_clock",
        "server_time_ms": now_ms,
        "queue_interval_sec": QUEUE_SCAN_INTERVAL_SEC,
        "items": items,
        "total": len(items),
    }


def reset_off_progress_schedules(db: Session) -> int:
    """Drop wall-clock schedules on fixtures outside the current progress gameweek."""
    changed = 0
    for season in db.query(Season).filter(Season.season_status == "active").all():
        prog = fixture_progress_gameweek(db, season.season_id) or 1
        for f in (
            db.query(Fixture)
            .filter(
                Fixture.season_id == season.season_id,
                Fixture.status.in_(("upcoming", "preparing")),
                Fixture.gameweek != prog,
            )
            .all()
        ):
            pred = dict(f.predictions or {})
            if _scheduled_start(pred) is None and f.status == "upcoming":
                # No schedule and already upcoming — just scrub stale proc flag
                if pred.pop("_processing_started_at", None) is not None:
                    f.predictions = pred
                    changed += 1
                continue
            pred.pop("_scheduled_start_at", None)
            pred.pop("_processing_started_at", None)
            pred.pop("_preparing_hook_at", None)
            f.predictions = pred
            f.status = "upcoming"
            changed += 1
        # Also clear stale _processing_started_at on upcoming fixtures in the
        # progress gameweek that have no scheduled_start_at — these are orphaned
        # flags from a previous failed sim attempt and should not interfere with
        # the pick_sim_target secondary path or the enqueue functions.
        for f in (
            db.query(Fixture)
            .filter(
                Fixture.season_id == season.season_id,
                Fixture.status == "upcoming",
                Fixture.gameweek == prog,
            )
            .all()
        ):
            pred = dict(f.predictions or {})
            if _scheduled_start(pred) is None and pred.get("_processing_started_at"):
                pred.pop("_processing_started_at", None)
                f.predictions = pred
                changed += 1
                log.debug("Cleared stale proc flag on unscheduled upcoming %s", f.match_id)
    if changed:
        db.commit()
        log.info("Reset %d off-progress scheduled fixtures / stale proc flags.", changed)
    return changed


def repair_unscheduled_preparing(db: Session) -> int:
    """Preparing rows must have a wall-clock start — re-queue or revert."""
    import time as _time

    now = _time.time()
    changed = 0
    for f in db.query(Fixture).filter(Fixture.status == "preparing").all():
        pred = dict(f.predictions or {})
        if _scheduled_start(pred) is not None:
            continue
        pred["_scheduled_start_at"] = now + FIRST_START_OFFSET_SEC
        f.predictions = pred
        changed += 1
        log.info("Repaired preparing schedule for %s", f.match_id)
    if changed:
        db.commit()
    return changed


def run_wall_clock_broadcast_gate(db: Session) -> int:
    """Wall-clock path: enqueue → finalize video → promote → on-air window."""
    from utils.broadcast_gate import (
        finalize_videos_before_promote,
        manage_on_air_window,
        purge_illegal_live,
        retry_or_complete_videoless,
    )

    from utils.preparing_pipeline import run_preparing_pipeline

    total = run_preparing_pipeline(db)
    total += reset_off_progress_schedules(db)
    total += repair_unscheduled_preparing(db)
    total += enqueue_video_ready_immediate(db)
    total += enqueue_scheduled_fixtures(db)
    total += retry_or_complete_videoless(db, max_repairs=1)
    total += finalize_videos_before_promote(db)
    total += promote_preparing_to_live(db)
    total += purge_illegal_live(db)
    total += recover_stale_broadcasts(db)
    total += manage_on_air_window(db)
    return total
