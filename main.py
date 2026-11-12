"""
CityBet Virtuals - FastAPI Gateway
"""
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.db import (
    SessionLocal,
    get_db,
    Season,
    Team,
    Player,
    Fixture,
    EventMarket,
    GfrDump,
)
from utils.league_table import build_league_table, build_leaderboard_payload
from utils.stats_aggregator import get_top_scorers
from utils.virtual_schedule import (
    build_countdown_state,
    fixture_progress_gameweek,
    match_has_video,
    resolve_live_fixture,
    serialize_fixture_card,
    virtual_clock_ms,
)

app = FastAPI(
    title="CityBet Virtuals API",
    description="Virtual football simulation platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FIXTURE_IMG_DIR = PROJECT_ROOT / "front_end" / "static" / "img" / "fixture_imgs"
TEAM_FIX_IMG_DIR = PROJECT_ROOT / "front_end" / "static" / "img" / "team_fix_imgs"
# FE assets (logo, etc.) served at /static/img via proxy
FE_STATIC_IMG_DIR = PROJECT_ROOT / "front_end" / "citybet_virtual_FE" / "static" / "img"
from utils.video_paths import VIDEO_DIR

VIDEO_DIR.mkdir(parents=True, exist_ok=True)

if FE_STATIC_IMG_DIR.is_dir():
    app.mount("/static/img", StaticFiles(directory=str(FE_STATIC_IMG_DIR)), name="fe-static-img")
if FIXTURE_IMG_DIR.is_dir():
    app.mount("/static/fixture-imgs", StaticFiles(directory=str(FIXTURE_IMG_DIR)), name="fixture-imgs")
if TEAM_FIX_IMG_DIR.is_dir():
    app.mount("/static/team-fix-imgs", StaticFiles(directory=str(TEAM_FIX_IMG_DIR)), name="team-fix-imgs")


def _resolve_video_file(match_id: str, dump=None) -> Optional[Path]:
    from utils.virtual_schedule import resolve_video_file

    try:
        mid = uuid.UUID(match_id)
    except ValueError:
        return None
    return resolve_video_file(mid, dump)


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


@app.get("/seasons", tags=["Seasons"])
def list_seasons(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Season)
    if status:
        q = q.filter(Season.season_status == status)
    seasons = q.order_by(Season.tournament_name.asc()).all()
    return [
        {
            "season_id": str(s.season_id),
            "tournament_name": s.tournament_name,
            "season_status": s.season_status,
            "current_gwk": s.current_gwk,
            "cum_gwk": s.cum_gwk,
            "cum_teams": db.query(Team).filter(Team.season_id == s.season_id).count(),
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in seasons
    ]


@app.get("/leagues", tags=["Leagues"])
def list_leagues(
    status: Optional[str] = Query("active"),
    db: Session = Depends(get_db),
):
    q = db.query(Season)
    if status:
        q = q.filter(Season.season_status == status)
    seasons = q.order_by(Season.tournament_name.asc()).all()
    result = []
    for s in seasons:
        league_name = " ".join(s.tournament_name.split()[:-1]) if s.tournament_name else s.tournament_name
        synced_gwk = fixture_progress_gameweek(db, s.season_id) or s.current_gwk
        result.append({
            "league_name": league_name,
            "season_id": str(s.season_id),
            "tournament_name": s.tournament_name,
            "season_status": s.season_status,
            "current_gwk": synced_gwk,
            "cum_gwk": s.cum_gwk,
            "team_count": db.query(Team).filter(Team.season_id == s.season_id).count(),
        })
    return result


@app.get("/leagues/{league_name}/teams", tags=["Leagues"])
def league_teams(league_name: str, db: Session = Depends(get_db)):
    season = (
        db.query(Season)
        .filter(Season.season_status == "active", Season.tournament_name.like(f"{league_name} %"))
        .order_by(Season.created_at.desc())
        .first()
    )
    if not season:
        raise HTTPException(status_code=404, detail=f"No active season for league '{league_name}'")

    teams = db.query(Team).filter(Team.season_id == season.season_id).order_by(Team.team_name).all()
    return {
        "league_name": league_name,
        "season_id": str(season.season_id),
        "tournament_name": season.tournament_name,
        "teams": [
            {
                "team_id": str(t.team_id),
                "team_name": t.team_name,
                "team_rating": t.team_rating,
                "league_rank": t.league_rank,
                "team_data": t.team_data,
                "player_count": db.query(Player).filter(Player.team_id == t.team_id).count(),
            }
            for t in teams
        ],
    }


@app.get("/teams/{team_id}/players", tags=["Teams"])
def team_players(team_id: str, db: Session = Depends(get_db)):
    players = (
        db.query(Player)
        .filter(Player.team_id == uuid.UUID(team_id))
        .order_by(Player.player_position)
        .all()
    )
    return [
        {
            "player_id": str(p.player_id),
            "player_name": p.player_name,
            "player_position": p.player_position,
            "role": p.role,
            "player_rating": p.player_rating,
            "gfr_attributes": p.gfr_attributes,
            "player_face_url": p.player_face_url,
            "goals": p.goals or 0,
            "assists": p.assists or 0,
            "appearances": p.appearances or 0,
        }
        for p in players
    ]


@app.get("/seasons/{season_id}/table", tags=["Leagues"])
def league_table(season_id: str, db: Session = Depends(get_db)):
    season = db.query(Season).filter(Season.season_id == uuid.UUID(season_id)).first()
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")
    return {
        "season_id": str(season.season_id),
        "tournament_name": season.tournament_name,
        "current_gwk": fixture_progress_gameweek(db, season.season_id) or season.current_gwk,
        "table": build_league_table(db, season.season_id),
    }


@app.get("/leaderboard", tags=["Leagues"])
def leaderboard(
    season_id: str = Query(...),
    db: Session = Depends(get_db),
):
    season = db.query(Season).filter(Season.season_id == uuid.UUID(season_id)).first()
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")
    return build_leaderboard_payload(db, season.season_id)


@app.get("/fixtures", tags=["Fixtures"])
def list_fixtures(
    season_id: Optional[str] = Query(None),
    gameweek: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    min_show_at_ms: Optional[int] = Query(None),
    min_gameweek: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Fixture)
    if season_id:
        q = q.filter(Fixture.season_id == uuid.UUID(season_id))
    if gameweek:
        q = q.filter(Fixture.gameweek == gameweek)
    if min_gameweek is not None:
        q = q.filter(Fixture.gameweek >= int(min_gameweek))
    if status:
        q = q.filter(Fixture.status == status)
    if min_show_at_ms is not None:
        q = q.filter(Fixture.show_at_ms >= int(min_show_at_ms))

    total = q.count()
    fixtures = q.order_by(Fixture.show_at_ms.asc()).offset(offset).limit(limit).all()

    from utils.virtual_schedule import effective_fixture_status
    from utils.match_sync import build_match_sync_payload

    result = []
    for f in fixtures:
        home = db.query(Team).filter(Team.team_id == f.home_team_id).first()
        away = db.query(Team).filter(Team.team_id == f.away_team_id).first()
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        eff_status = effective_fixture_status(f, dump)
        match_sync = None
        if dump and dump.gfr_stats and eff_status in ("live", "preparing"):
            match_sync = build_match_sync_payload(f.match_id, dump.gfr_stats)
        result.append({
            "match_id": str(f.match_id),
            "season_id": str(f.season_id),
            "gameweek": f.gameweek,
            "game_date": str(f.game_date),
            "game_time": str(f.game_time),
            "show_at_ms": int(f.show_at_ms or 0),
            "status": eff_status,
            "settled": f.settled,
            "score": f.score,
            "fixture_image_url": f.fixture_image_url,
            "home_team": {"id": str(home.team_id), "name": home.team_name} if home else None,
            "away_team": {"id": str(away.team_id), "name": away.team_name} if away else None,
            "predictions": f.predictions,
            "outcome": f.outcome,
            "has_video": match_has_video(dump, f.match_id),
            "match_sync": match_sync,
        })
        pred = dict(f.predictions or {})
        sched = pred.get("_scheduled_start_at")
        result[-1]["scheduled_start_at_ms"] = int(float(sched) * 1000) if sched else None

    return {"total": total, "fixtures": result}


@app.get("/carousel", tags=["Carousel"])
def get_carousel(db: Session = Depends(get_db)):
    """Backend-driven carousel queue — ordered by scheduled wall-clock start."""
    from utils.carousel_schedule import build_carousel_response, use_wall_clock_schedule

    if not use_wall_clock_schedule():
        return {"mode": "legacy", "server_time_ms": int(__import__("time").time() * 1000), "items": [], "total": 0}
    return build_carousel_response(db)


@app.get("/fixtures/{match_id}", tags=["Fixtures"])
def get_fixture(match_id: str, db: Session = Depends(get_db)):
    f = db.query(Fixture).filter(Fixture.match_id == uuid.UUID(match_id)).first()
    if not f:
        raise HTTPException(status_code=404, detail="Fixture not found")
    home = db.query(Team).filter(Team.team_id == f.home_team_id).first()
    away = db.query(Team).filter(Team.team_id == f.away_team_id).first()
    markets = db.query(EventMarket).filter(EventMarket.match_id == f.match_id).all()
    return {
        "match_id": str(f.match_id),
        "season_id": str(f.season_id),
        "gameweek": f.gameweek,
        "show_at_ms": int(f.show_at_ms or 0),
        "status": f.status,
        "score": f.score,
        "fixture_image_url": f.fixture_image_url,
        "home_team": {"id": str(home.team_id), "name": home.team_name} if home else None,
        "away_team": {"id": str(away.team_id), "name": away.team_name} if away else None,
        "markets": [
            {"market_type": m.market_type, "selections": m.selections, "odds": m.odds}
            for m in markets
        ],
    }


@app.get("/results", tags=["Results"])
def list_results(
    season_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    q = db.query(Fixture).filter(Fixture.status == "completed")
    if season_id:
        q = q.filter(Fixture.season_id == uuid.UUID(season_id))
    total = q.count()
    fixtures = q.order_by(Fixture.show_at_ms.desc()).offset(offset).limit(limit).all()

    result = []
    for f in fixtures:
        home = db.query(Team).filter(Team.team_id == f.home_team_id).first()
        away = db.query(Team).filter(Team.team_id == f.away_team_id).first()
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        result.append({
            "match_id": str(f.match_id),
            "season_id": str(f.season_id),
            "gameweek": f.gameweek,
            "game_date": str(f.game_date),
            "show_at_ms": int(f.show_at_ms or 0),
            "fixture_image_url": f.fixture_image_url,
            "home_team": home.team_name if home else "Unknown",
            "away_team": away.team_name if away else "Unknown",
            "score": f.score,
            "outcome": f.outcome,
            "video_url": dump.video_url if dump else None,
            "video_endpoint": f"/video/{f.match_id}",
            "gfr_stats": dump.gfr_stats if dump else None,
        })
    return {"total": total, "results": result}


@app.get("/stats/top-scorers", tags=["Stats"])
def top_scorers(
    season_id: str = Query(...),
    limit: int = Query(20, le=50),
    db: Session = Depends(get_db),
):
    season = db.query(Season).filter(Season.season_id == uuid.UUID(season_id)).first()
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")
    return {
        "season_id": str(season.season_id),
        "tournament_name": season.tournament_name,
        "scorers": get_top_scorers(db, season.season_id, limit),
    }


RECENT_REPLAY_LIMIT = 8


def _get_recent_completed_fixtures_with_video(
    db: Session, season_id: uuid.UUID, limit: int = RECENT_REPLAY_LIMIT
):
    """Most recent *limit* completed fixtures whose video is properly saved.

    Newest first. "Properly saved" = a browser-streamable MP4 exists on disk
    (full or _full_small, moov-at-start, > 50 KB). Only the video_url column is
    read from GfrDump (never the match_video blob), candidates are paged
    newest-first, and each check is a stat + small header read, so this stays
    cheap inside the /live/all poll even though it touches the filesystem.
    """
    from utils.video_paths import resolve_streamable_video

    found: list = []
    seen: set = set()
    page = 40
    for offset in range(0, 1000, page):
        rows = (
            db.query(Fixture, GfrDump.video_url)
            .join(GfrDump, Fixture.match_id == GfrDump.match_id)
            .filter(Fixture.season_id == season_id, Fixture.status == "completed")
            .order_by(Fixture.show_at_ms.desc(), Fixture.match_id)
            .offset(offset)
            .limit(page)
            .all()
        )
        if not rows:
            break
        for fixture, video_url in rows:
            if fixture.match_id in seen:
                continue
            seen.add(fixture.match_id)
            if resolve_streamable_video(fixture.match_id, video_url) is None:
                continue
            found.append(fixture)
            if len(found) >= limit:
                return found
    return found


@app.get("/live/now", tags=["Live"])
def live_now(
    season_id: str = Query(...),
    virtual_ms: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    season = db.query(Season).filter(Season.season_id == uuid.UUID(season_id)).first()
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")

    fixture, clock, source = resolve_live_fixture(db, season.season_id, virtual_ms)
    if not fixture:
        fallbacks = _get_recent_completed_fixtures_with_video(db, season.season_id, limit=1)
        if fallbacks:
            fixture = fallbacks[0]
            source = "virtual_replay"
        else:
            return {
                "season_id": str(season.season_id),
                "virtual_clock_ms": clock,
                "source": source,
                "fixture": None,
            }
    return {
        "season_id": str(season.season_id),
        "virtual_clock_ms": clock,
        "source": source,
        "fixture": serialize_fixture_card(db, fixture, clock),
    }


@app.get("/live/all", tags=["Live"])
def live_all_leagues(
    virtual_ms: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Carousel/landing-page polling endpoint — called every 5 s by the frontend.
    match_sync is intentionally omitted (it runs ffprobe which is expensive);
    fetch /live/now or /fixtures/{id} for the full sync payload when playing a video.

    Performance notes:
    - Teams and GfrDumps are bulk-loaded once per request (eliminates N+1 queries).
    - has_video uses DB-only check (no MP4 filesystem probes).
    - match_sync skipped (no ffprobe).
    """
    seasons = db.query(Season).filter(Season.season_status == "active").all()

    # ── Gather all fixture candidates first so we can bulk-load related objects ─
    season_fixtures: list[tuple] = []  # (season, fixture_or_None, clock, source, fallbacks)
    for season in seasons:
        fixture, clock, source = resolve_live_fixture(db, season.season_id, virtual_ms, skip_video_probe=True)
        if fixture:
            season_fixtures.append((season, fixture, clock, source, []))
        else:
            fallbacks = _get_recent_completed_fixtures_with_video(db, season.season_id)
            season_fixtures.append((season, None, clock, source, fallbacks))

    # ── Collect all match_ids we need to render ─────────────────────────────────
    all_fixtures: list = []
    for _, fixture, _, _, fallbacks in season_fixtures:
        if fixture:
            all_fixtures.append(fixture)
        else:
            all_fixtures.extend(fallbacks)

    all_match_ids = [f.match_id for f in all_fixtures]
    all_team_ids  = list({f.home_team_id for f in all_fixtures} | {f.away_team_id for f in all_fixtures})

    # ── Two bulk queries instead of 4×N individual ones ────────────────────────
    teams_by_id: dict = {}
    dumps_by_match: dict = {}
    if all_team_ids:
        for team in db.query(Team).filter(Team.team_id.in_(all_team_ids)).all():
            teams_by_id[team.team_id] = team
    if all_match_ids:
        for dump in db.query(GfrDump).filter(GfrDump.match_id.in_(all_match_ids)).all():
            dumps_by_match[dump.match_id] = dump

    # ── Pre-compute per-season countdown (reused across all cards of a season) ──
    countdown_by_season: dict = {}
    for season, _, clock, _, _ in season_fixtures:
        sid = season.season_id
        if sid not in countdown_by_season:
            countdown_by_season[sid] = build_countdown_state(db, sid, clock)

    def _card(fixture, clock):
        return serialize_fixture_card(
            db, fixture, clock,
            skip_match_sync=True,
            skip_video_probe=True,
            preloaded_teams=teams_by_id,
            preloaded_dumps=dumps_by_match,
        )

    # ── Assemble response cards ─────────────────────────────────────────────────
    cards = []
    for season, fixture, clock, source, fallbacks in season_fixtures:
        league_name = " ".join(season.tournament_name.split()[:-1])
        countdown = countdown_by_season[season.season_id]
        if fixture:
            cards.append({
                "league_name": league_name,
                "season_id": str(season.season_id),
                "virtual_clock_ms": clock,
                "source": source,
                "fixture": _card(fixture, clock),
                "countdown": countdown,
            })
        elif fallbacks:
            for f in fallbacks:
                cards.append({
                    "league_name": league_name,
                    "season_id": str(season.season_id),
                    "virtual_clock_ms": clock,
                    "source": "virtual_replay",
                    "fixture": _card(f, clock),
                    "countdown": countdown,
                })
        else:
            cards.append({
                "league_name": league_name,
                "season_id": str(season.season_id),
                "virtual_clock_ms": clock,
                "source": "none",
                "fixture": None,
                "countdown": countdown,
            })
    return cards


def stream_match_video(match_id: str, request: Request, db: Session):
    from utils.video_stream import stream_mp4

    try:
        mid = uuid.UUID(match_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid match id") from exc

    dump = db.query(GfrDump).filter(GfrDump.match_id == mid).first()
    video_path = _resolve_video_file(match_id, dump)
    if not video_path:
        raise HTTPException(status_code=404, detail="No video available for this match")
    return stream_mp4(video_path, request)


def _video_path_for_match(match_id: str, db: Session) -> Optional[Path]:
    try:
        mid = uuid.UUID(match_id)
    except ValueError:
        return None
    dump = db.query(GfrDump).filter(GfrDump.match_id == mid).first()
    return _resolve_video_file(match_id, dump)


@app.get("/video/{match_id}", tags=["Media"])
@app.head("/video/{match_id}", tags=["Media"])
def stream_video(match_id: str, request: Request, db: Session = Depends(get_db)):
    if request.method == "HEAD":
        from utils.video_stream import head_mp4

        video_path = _video_path_for_match(match_id, db)
        if not video_path:
            raise HTTPException(status_code=404, detail="No video available for this match")
        return head_mp4(video_path, request)
    return stream_match_video(match_id, request, db)


@app.get("/video/live", tags=["Media"])
def stream_live_video(
    request: Request,
    season_id: str = Query(...),
    virtual_ms: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    season = db.query(Season).filter(Season.season_id == uuid.UUID(season_id)).first()
    if not season:
        raise HTTPException(status_code=404, detail="Season not found")

    fixture, clock, source = resolve_live_fixture(db, season.season_id, virtual_ms)
    if not fixture:
        raise HTTPException(status_code=404, detail="No fixture scheduled at this time")

    if fixture.status not in ("completed", "live"):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Match not yet played — video unavailable",
                "virtual_clock_ms": clock,
                "show_at_ms": int(fixture.show_at_ms or 0),
                "status": fixture.status,
                "match_id": str(fixture.match_id),
            },
        )
    return stream_match_video(str(fixture.match_id), request, db)


@app.post("/simulate/next", tags=["Simulation"])
def simulate_next(background_tasks: BackgroundTasks):
    from workers.game_simulator import simulate_next_fixture

    def _run():
        db = SessionLocal()
        try:
            simulate_next_fixture(db)
        finally:
            db.close()

    background_tasks.add_task(_run)
    return {"status": "ok", "message": "Next fixture simulation started in background."}


@app.post("/simulate/gameweek/{gameweek}", tags=["Simulation"])
def simulate_gameweek(gameweek: int, background_tasks: BackgroundTasks):
    from workers.game_simulator import run_gameweek

    background_tasks.add_task(run_gameweek, gameweek)
    return {"status": "ok", "message": f"Gameweek {gameweek} simulation started in background."}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
