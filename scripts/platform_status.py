#!/usr/bin/env python3
"""Quick platform status snapshot."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.db import SessionLocal, Season, Fixture, GfrDump, Player, Team
from utils.fixture_image_search import is_stale_image_url, CACHE_DIR
from utils.fc26_loader import build_roster_from_fc26

db = SessionLocal()
try:
    seasons = db.query(Season).filter(Season.season_status == "active").count()
    fixtures = db.query(Fixture).count()
    upcoming = db.query(Fixture).filter(Fixture.status == "upcoming").count()
    completed = db.query(Fixture).filter(Fixture.status == "completed").count()
    live = db.query(Fixture).filter(Fixture.status == "live").count()
    videos = db.query(GfrDump).filter(
        (GfrDump.match_video.isnot(None)) | (GfrDump.video_url.isnot(None))
    ).count()

    stale_imgs = 0
    cached_imgs = 0
    for f in db.query(Fixture.fixture_image_url).all():
        url = f[0]
        if is_stale_image_url(url):
            stale_imgs += 1
        elif url and "/cache/" in url:
            cached_imgs += 1

    fc26_ok = 0
    fc26_bad = []
    for team in db.query(Team).limit(78):
        fc26, _ = build_roster_from_fc26(team.league_name, team.team_name)
        if not fc26:
            fc26_bad.append(team.team_name)
            continue
        players = db.query(Player).filter(Player.team_id == team.team_id).all()
        overlap = len({p.player_name for p in players} & {x["player_name"] for x in fc26})
        if overlap >= 6:
            fc26_ok += 1
        else:
            fc26_bad.append(team.team_name)

    cache_files = len(list(CACHE_DIR.glob("*"))) if CACHE_DIR.exists() else 0

    print("DATABASE")
    print(f"  Active seasons: {seasons}")
    print(f"  Fixtures: {fixtures} (upcoming={upcoming}, live={live}, completed={completed})")
    print(f"  Matches with video: {videos}")
    print(f"  Fixture images: {cached_imgs} cached, {stale_imgs} stale/unsplash, {cache_files} files on disk")
    print(f"  FC26 squads OK: {fc26_ok}/{fc26_ok + len(fc26_bad)}")
    if fc26_bad:
        print(f"  FC26 mismatches: {', '.join(fc26_bad[:8])}{'...' if len(fc26_bad) > 8 else ''}")
finally:
    db.close()
