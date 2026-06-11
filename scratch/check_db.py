import os
import sys
import uuid
import sqlalchemy as sa
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.db import SessionLocal, Fixture, GfrDump, Team, Season

db = SessionLocal()
try:
    print("Total seasons:", db.query(Season).count())
    active_seasons = db.query(Season).filter(Season.season_status == "active").all()
    print("Active seasons:")
    for s in active_seasons:
        print(f"  Season ID: {s.season_id}, Name: {s.tournament_name}, Current GWK: {s.current_gwk}")
    
    print("\nTotal fixtures:", db.query(Fixture).count())
    status_counts = db.query(Fixture.status, sa.func.count(Fixture.status)).group_by(Fixture.status).all()
    print("Fixture status counts:", status_counts)
    
    preparing_fixtures = db.query(Fixture).filter(Fixture.status == "preparing").limit(5).all()
    print("\nPreparing fixtures (first 5):")
    for f in preparing_fixtures:
        print(f"  Match ID: {f.match_id}, GWK: {f.gameweek}, Score: {f.score}, Settled: {f.settled}")
        
    live_fixtures = db.query(Fixture).filter(Fixture.status == "live").limit(5).all()
    print("\nLive fixtures (first 5):")
    for f in live_fixtures:
        print(f"  Match ID: {f.match_id}, GWK: {f.gameweek}, Score: {f.score}, Settled: {f.settled}")

    latest_dumps = db.query(GfrDump).order_by(GfrDump.created_at.desc()).limit(5).all()
    print("\nLatest 5 dumps:")
    for d in latest_dumps:
        print(f"  Match ID: {d.match_id}, Video URL: {d.video_url}, Created At: {d.created_at}")
        # Check if the file actually exists on disk
        if d.video_url:
            path_exists = Path(d.video_url).exists()
            print(f"    Disk path exists: {path_exists} for {d.video_url}")
            
finally:
    db.close()
