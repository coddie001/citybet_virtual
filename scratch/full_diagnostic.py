"""
Thorough diagnostic: DB state, match progression, gameweek, and live broadcast health.
"""
import sys, json
sys.path.insert(0, "/home/Warta/projects/citybet_virtuals")

from utils.db import SessionLocal, Season, Fixture, GfrDump, Team
from utils.virtual_schedule import match_has_video, effective_fixture_status, resolve_live_fixture
from sqlalchemy import func

db = SessionLocal()

print("=" * 70)
print("1. SEASON / GAMEWEEK STATE")
print("=" * 70)
seasons = db.query(Season).all()
for s in seasons:
    league_name = " ".join(s.tournament_name.split()[:-1])
    total = db.query(Fixture).filter(Fixture.season_id == s.season_id).count()
    completed = db.query(Fixture).filter(Fixture.season_id == s.season_id, Fixture.status == 'completed').count()
    live = db.query(Fixture).filter(Fixture.season_id == s.season_id, Fixture.status == 'live').count()
    preparing = db.query(Fixture).filter(Fixture.season_id == s.season_id, Fixture.status == 'preparing').count()
    upcoming = db.query(Fixture).filter(Fixture.season_id == s.season_id, Fixture.status == 'upcoming').count()
    print(f"\n  {league_name} (GWK {s.current_gwk})")
    print(f"    Total={total} | completed={completed} | live={live} | preparing={preparing} | upcoming={upcoming}")

print()
print("=" * 70)
print("2. CURRENT LIVE/PREPARING MATCHES")
print("=" * 70)
for status in ['live', 'preparing']:
    fixtures = db.query(Fixture).filter(Fixture.status == status).all()
    print(f"\n  STATUS={status.upper()} ({len(fixtures)} matches):")
    for f in fixtures:
        h = db.query(Team).filter(Team.team_id == f.home_team_id).first()
        a = db.query(Team).filter(Team.team_id == f.away_team_id).first()
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        has_v = match_has_video(dump, f.match_id)
        eff = effective_fixture_status(f, dump)
        home_name = h.team_name if h else '?'
        away_name = a.team_name if a else '?'
        score = f.score or '0-0'
        print(f"    GWK{f.gameweek} {home_name} {score} {away_name} | eff_status={eff} | has_video={has_v}")
        if dump:
            print(f"      dump.video_url={dump.video_url}")
        else:
            print(f"      NO DUMP ROW")

print()
print("=" * 70)
print("3. RECENTLY COMPLETED (last 10)")
print("=" * 70)
recent = db.query(Fixture).filter(Fixture.status == 'completed').order_by(Fixture.show_at_ms.desc()).limit(10).all()
for f in recent:
    h = db.query(Team).filter(Team.team_id == f.home_team_id).first()
    a = db.query(Team).filter(Team.team_id == f.away_team_id).first()
    dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
    has_v = match_has_video(dump, f.match_id)
    score = f.score or '0-0'
    home_name = h.team_name if h else '?'
    away_name = a.team_name if a else '?'
    print(f"  GWK{f.gameweek} {home_name} {score} {away_name} | has_video={has_v}")

print()
print("=" * 70)
print("4. resolve_live_fixture PER LEAGUE")
print("=" * 70)
for s in seasons:
    league_name = " ".join(s.tournament_name.split()[:-1])
    fixture, clock, source = resolve_live_fixture(db, s.season_id)
    if fixture:
        h = db.query(Team).filter(Team.team_id == fixture.home_team_id).first()
        a = db.query(Team).filter(Team.team_id == fixture.away_team_id).first()
        dump = db.query(GfrDump).filter(GfrDump.match_id == fixture.match_id).first()
        has_v = match_has_video(dump, fixture.match_id)
        home_name = h.team_name if h else '?'
        away_name = a.team_name if a else '?'
        score = fixture.score or '0-0'
        print(f"\n  {league_name}: source={source} | {home_name} {score} {away_name} | has_video={has_v}")
    else:
        print(f"\n  {league_name}: NO FIXTURE RESOLVED")

print()
print("=" * 70)
print("5. MATCH_SYNC DATA PRESENCE (for scoreline/commentary in replays)")
print("=" * 70)
recent_completed = db.query(Fixture).filter(Fixture.status == 'completed').order_by(Fixture.show_at_ms.asc()).limit(6).all()
for f in recent_completed:
    dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
    has_v = match_has_video(dump, f.match_id)
    has_stats = bool(dump and dump.gfr_stats)
    score = f.score or '0-0'
    h = db.query(Team).filter(Team.team_id == f.home_team_id).first()
    a = db.query(Team).filter(Team.team_id == f.away_team_id).first()
    home_name = h.team_name if h else '?'
    away_name = a.team_name if a else '?'
    if has_stats and dump:
        stats = dump.gfr_stats
        goal_events = stats.get('goal_events', []) if isinstance(stats, dict) else []
        vid_dur = stats.get('video_duration_sec', 0) if isinstance(stats, dict) else 0
        print(f"  GWK{f.gameweek} {home_name} {score} {away_name} | has_video={has_v} | has_stats=YES | goals={len(goal_events)} | vid_dur={vid_dur}s")
    else:
        print(f"  GWK{f.gameweek} {home_name} {score} {away_name} | has_video={has_v} | has_stats=NO")

db.close()
