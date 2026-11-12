"""Virtual broadcast schedule helpers for the frontend timeline."""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from utils.db import Fixture, Season, Team, GfrDump
from utils.fixture_timing import FIXTURE_INTERVAL_MS
from utils.match_sync import build_match_sync_payload

COUNTDOWN_WINDOW_MS = 3 * 60 * 1000  # virtual-ms label (legacy)
REAL_COUNTDOWN_MS = 3 * 60 * 1000  # 3 real minutes for UI countdown
KICKOFF_GRACE_MS = 60_000


def virtual_clock_speed() -> float:
    return float(os.getenv("VIRTUAL_CLOCK_SPEED", "60"))


def virtual_until_real_ms(until_virtual_ms: int) -> float:
    """Convert virtual ms-until-kickoff to real milliseconds."""
    return max(0.0, until_virtual_ms) / virtual_clock_speed()

from utils.video_paths import (
    VIDEO_DIR,
    resolve_streamable_video,
    video_path_for,
)


def resolve_video_file(match_id: uuid.UUID, dump: Optional[GfrDump] = None) -> Optional[Path]:
    dump_url = dump.video_url if dump else None
    streamable = resolve_streamable_video(match_id, dump_url)
    if streamable:
        return streamable
    canonical = video_path_for(match_id)
    if canonical.is_file():
        return canonical
    if dump_url:
        path = Path(dump_url)
        if path.is_file():
            return path
    return None


def match_has_video(dump: Optional[GfrDump], match_id: uuid.UUID) -> bool:
    """True when a browser-streamable MP4 exists (full or _full_small, moov-at-start)."""
    dump_url = dump.video_url if dump else None
    return resolve_streamable_video(match_id, dump_url) is not None


def dump_has_video_record(dump: Optional[GfrDump]) -> bool:
    """Cheap DB-only check: True when GfrDump records a video path.

    Use this in high-frequency poll paths (e.g. /live/all) where reading
    the MP4 header from disk would be too slow.
    """
    if dump is None:
        return False
    return bool(dump.video_url or dump.match_video)


def effective_fixture_status(fixture: Fixture, dump: Optional[GfrDump] = None) -> str:
    """API-facing status — never live without streamable MP4; sim-running stays preparing."""
    if fixture.status == "live" and not match_has_video(dump, fixture.match_id):
        return "preparing"
    return fixture.status


def season_timeline_span(db: Session, season_id: uuid.UUID) -> int:
    last_show = (
        db.query(func.max(Fixture.show_at_ms))
        .filter(Fixture.season_id == season_id)
        .scalar()
    )
    if last_show is None:
        return 0
    return int(last_show) + FIXTURE_INTERVAL_MS


def virtual_clock_ms(
    season: Season,
    db: Session,
    virtual_ms: Optional[int] = None,
) -> int:
    if virtual_ms is not None:
        return max(0, int(virtual_ms))

    span = season_timeline_span(db, season.season_id)
    if span <= 0:
        return 0

    speed = float(os.getenv("VIRTUAL_CLOCK_SPEED", "60"))
    if not season.created_at:
        return 0
    created = season.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    elapsed_real_ms = (datetime.now(timezone.utc) - created).total_seconds() * 1000
    raw = max(0, int(elapsed_real_ms * speed))
    return raw % span


def _latest_completed_with_video(
    db: Session, season_id: uuid.UUID, before_show_at_ms: int
) -> Optional[Fixture]:
    return (
        db.query(Fixture)
        .join(GfrDump, Fixture.match_id == GfrDump.match_id)
        .filter(
            Fixture.season_id == season_id,
            Fixture.status == "completed",
            Fixture.show_at_ms < before_show_at_ms,
        )
        .filter((GfrDump.match_video.isnot(None)) | (GfrDump.video_url.isnot(None)))
        .order_by(Fixture.show_at_ms.desc())
        .first()
    )


def broadcast_fixture_at_clock(
    db: Session, season_id: uuid.UUID, virtual_ms: int
) -> Tuple[Optional[Fixture], str]:
    fixtures = (
        db.query(Fixture)
        .filter(Fixture.season_id == season_id)
        .order_by(Fixture.show_at_ms.asc())
        .all()
    )
    if not fixtures:
        return None, "none"

    span = int(fixtures[-1].show_at_ms or 0) + FIXTURE_INTERVAL_MS

    for i, f in enumerate(fixtures):
        next_show = fixtures[i + 1].show_at_ms if i + 1 < len(fixtures) else span
        if f.show_at_ms <= virtual_ms < next_show:
            if f.status == "completed":
                return f, "virtual_completed"
            if f.status == "upcoming" and virtual_ms >= f.show_at_ms:
                replay = _latest_completed_with_video(db, season_id, f.show_at_ms)
                if replay:
                    return replay, "virtual_replay"
            return f, "virtual_upcoming" if f.status == "upcoming" else "virtual"

    last = fixtures[-1]
    if last.status == "completed":
        return last, "virtual_completed"
    return last, "virtual_upcoming"


def resolve_live_fixture(
    db: Session,
    season_id: uuid.UUID,
    virtual_ms: Optional[int] = None,
    *,
    skip_video_probe: bool = False,
) -> Tuple[Optional[Fixture], int, str]:
    season = db.query(Season).filter(Season.season_id == season_id).first()
    if not season:
        return None, 0, "missing"

    clock = virtual_clock_ms(season, db, virtual_ms)

    from utils.carousel_schedule import use_wall_clock_schedule

    live = (
        db.query(Fixture)
        .filter(Fixture.season_id == season_id, Fixture.status == "live")
        .order_by(Fixture.show_at_ms.asc())
        .first()
    )
    if live:
        dump = db.query(GfrDump).filter(GfrDump.match_id == live.match_id).first()
        has_vid = dump_has_video_record(dump) if skip_video_probe else match_has_video(dump, live.match_id)
        if has_vid:
            return live, clock, "live_status"

    if use_wall_clock_schedule():
        return None, clock, "none"

    scheduled, source = broadcast_fixture_at_clock(db, season_id, clock)
    if scheduled:
        return scheduled, clock, source

    latest_done = (
        db.query(Fixture)
        .filter(Fixture.season_id == season_id, Fixture.status == "completed")
        .order_by(Fixture.show_at_ms.desc())
        .first()
    )
    if latest_done:
        return latest_done, clock, "latest_completed"
    return None, clock, "none"


def fixture_progress_gameweek(db: Session, season_id: uuid.UUID) -> Optional[int]:
    """Gameweek aligned with simulation progress — ignores superseded lower-GW leftovers."""
    max_done = (
        db.query(func.max(Fixture.gameweek))
        .filter(Fixture.season_id == season_id, Fixture.status == "completed")
        .scalar()
    )
    floor_gw = int(max_done) if max_done else 1

    active_gw = (
        db.query(func.min(Fixture.gameweek))
        .filter(
            Fixture.season_id == season_id,
            Fixture.status.in_(("upcoming", "preparing", "live")),
            Fixture.gameweek >= floor_gw,
        )
        .scalar()
    )
    if active_gw is not None:
        return int(active_gw)
    if max_done is not None:
        return int(max_done)
    return None


def next_progress_fixture(db: Session, season_id: uuid.UUID) -> Optional[Fixture]:
    """Next sim-round fixture (live first, then upcoming) — not virtual-clock replay."""
    gwk = fixture_progress_gameweek(db, season_id)
    if not gwk:
        return None

    live = (
        db.query(Fixture)
        .filter(
            Fixture.season_id == season_id,
            Fixture.status == "live",
            Fixture.gameweek >= gwk,
        )
        .order_by(Fixture.gameweek.asc(), Fixture.show_at_ms.asc())
        .first()
    )
    if live:
        return live

    return (
        db.query(Fixture)
        .filter(
            Fixture.season_id == season_id,
            Fixture.status == "upcoming",
            Fixture.gameweek >= gwk,
        )
        .order_by(Fixture.gameweek.asc(), Fixture.show_at_ms.asc())
        .first()
    )


def current_gameweek_at_clock(
    db: Session, season_id: uuid.UUID, virtual_ms: int
) -> Optional[int]:
    """Derive broadcast gameweek from the virtual timeline (avoids stale DB current_gwk)."""
    row = (
        db.query(Fixture.gameweek)
        .filter(
            Fixture.season_id == season_id,
            Fixture.show_at_ms <= virtual_ms,
        )
        .order_by(Fixture.show_at_ms.desc())
        .first()
    )
    if row and row[0] is not None:
        return int(row[0])
    nxt = next_carousel_fixture(db, season_id, virtual_ms)
    return int(nxt.gameweek) if nxt and nxt.gameweek is not None else None


def next_carousel_fixture(db: Session, season_id: uuid.UUID, virtual_ms: int) -> Optional[Fixture]:
    return (
        db.query(Fixture)
        .filter(
            Fixture.season_id == season_id,
            Fixture.status == "upcoming",
            Fixture.show_at_ms > virtual_ms,
        )
        .order_by(Fixture.show_at_ms.asc())
        .first()
    )


def _kickoff_or_grace_fixture(
    db: Session, season_id: uuid.UUID, virtual_ms: int
) -> Optional[Fixture]:
    """Fixture at or just past kickoff — keeps countdown anchored through live window."""
    return (
        db.query(Fixture)
        .filter(
            Fixture.season_id == season_id,
            Fixture.status.in_(("upcoming", "live")),
            Fixture.show_at_ms <= virtual_ms,
            Fixture.show_at_ms > virtual_ms - KICKOFF_GRACE_MS,
        )
        .order_by(Fixture.show_at_ms.desc())
        .first()
    )


def build_countdown_state(db: Session, season_id: uuid.UUID, virtual_ms: int) -> Optional[dict]:
    from utils.carousel_schedule import countdown_for_scheduled, use_wall_clock_schedule

    if use_wall_clock_schedule():
        candidates = (
            db.query(Fixture)
            .filter(
                Fixture.season_id == season_id,
                Fixture.status.in_(("preparing", "live")),
            )
            .all()
        )
        best = None
        best_start = None
        for f in candidates:
            pred = dict(f.predictions or {})
            raw = pred.get("_scheduled_start_at")
            if raw is None:
                continue
            try:
                start = float(raw)
            except (TypeError, ValueError):
                continue
            if best_start is None or start < best_start:
                best_start = start
                best = f
        if best:
            return countdown_for_scheduled(best)
        return None

    gwk = fixture_progress_gameweek(db, season_id) or 1
    nxt = (
        db.query(Fixture)
        .filter(
            Fixture.season_id == season_id,
            Fixture.status == "upcoming",
            Fixture.gameweek >= gwk,
            Fixture.show_at_ms > virtual_ms - KICKOFF_GRACE_MS,
        )
        .order_by(Fixture.show_at_ms.asc())
        .first()
    )
    if not nxt:
        return None
    return _countdown_for_fixture(nxt, virtual_ms)


def _countdown_for_fixture(fixture: Fixture, virtual_ms: int) -> dict:
    """Real-time 03:00→00:00; starts when processing begins or 3 real min before kickoff."""
    import time

    pred = dict(fixture.predictions or {})
    started = pred.get("_processing_started_at")
    if started:
        until_real = max(0.0, REAL_COUNTDOWN_MS - (time.time() - float(started)) * 1000)
    else:
        until_virtual = int(fixture.show_at_ms or 0) - int(virtual_ms)
        until_real = virtual_until_real_ms(until_virtual)

    in_window = 0 < until_real <= REAL_COUNTDOWN_MS
    seconds = min(180, max(0, int((until_real + 999) // 1000))) if in_window else 0
    mm, ss = divmod(seconds, 60)
    return {
        "next_match_id": str(fixture.match_id),
        "show_at_ms": int(fixture.show_at_ms or 0),
        "virtual_clock_ms": int(virtual_ms),
        "ms_until_kickoff": int(until_real),
        "in_countdown_window": in_window,
        "countdown_seconds": seconds,
        "is_kickoff": False,
        "formatted": f"{mm:02d}:{ss:02d}" if in_window else "00:00",
        "countdown_real_ms": True,
    }


def serialize_fixture_card(
    db: Session,
    fixture: Fixture,
    virtual_ms: int,
    *,
    skip_match_sync: bool = False,
    skip_video_probe: bool = False,
    preloaded_teams: dict | None = None,
    preloaded_dumps: dict | None = None,
) -> dict:
    """Serialize a fixture card for the API response.

    Pass ``preloaded_teams`` and ``preloaded_dumps`` (keyed by UUID) to avoid
    N+1 DB queries when rendering many cards (e.g. in /live/all).
    """
    if preloaded_teams is not None:
        home = preloaded_teams.get(fixture.home_team_id)
        away = preloaded_teams.get(fixture.away_team_id)
    else:
        home = db.query(Team).filter(Team.team_id == fixture.home_team_id).first()
        away = db.query(Team).filter(Team.team_id == fixture.away_team_id).first()

    if preloaded_dumps is not None:
        dump = preloaded_dumps.get(fixture.match_id)
    else:
        dump = db.query(GfrDump).filter(GfrDump.match_id == fixture.match_id).first()

    next_ms = (
        db.query(Fixture.show_at_ms)
        .filter(
            Fixture.season_id == fixture.season_id,
            Fixture.show_at_ms > fixture.show_at_ms,
        )
        .order_by(Fixture.show_at_ms.asc())
        .limit(1)
        .scalar()
    )
    match_sync = None
    if not skip_match_sync and dump and dump.gfr_stats:
        match_sync = build_match_sync_payload(fixture.match_id, dump.gfr_stats)

    pred = dict(fixture.predictions or {})
    sched_raw = pred.get("_scheduled_start_at")
    scheduled_start_at_ms = int(float(sched_raw) * 1000) if sched_raw is not None else None

    return {
        "match_id": str(fixture.match_id),
        "season_id": str(fixture.season_id),
        "gameweek": fixture.gameweek,
        "show_at_ms": int(fixture.show_at_ms or 0),
        "virtual_clock_ms": virtual_ms,
        "next_show_at_ms": int(next_ms) if next_ms is not None else None,
        "status": effective_fixture_status(fixture, dump),
        "score": fixture.score,
        "fixture_image_url": fixture.fixture_image_url,
        "home_team": {"id": str(home.team_id), "name": home.team_name} if home else None,
        "away_team": {"id": str(away.team_id), "name": away.team_name} if away else None,
        "has_video": dump_has_video_record(dump) if skip_video_probe else match_has_video(dump, fixture.match_id),
        "video_endpoint": f"/video/{fixture.match_id}",
        "scheduled_start_at_ms": scheduled_start_at_ms,
        "match_sync": match_sync,
    }
