#!/usr/bin/env python3
"""Quick check: live league table from completed fixtures."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.db import SessionLocal, Season, Fixture
from utils.league_table import build_league_table, persist_league_table

db = SessionLocal()
try:
    for season in db.query(Season).filter(Season.season_status == "active").all():
        completed = (
            db.query(Fixture)
            .filter(Fixture.season_id == season.season_id, Fixture.status == "completed")
            .count()
        )
        rows = build_league_table(db, season.season_id)
        top = rows[0] if rows else None
        print(f"\n{season.tournament_name}: {completed} completed, {len(rows)} teams")
        if top:
            print(
                f"  #1 {top['team_name']}: {top['points']}pts "
                f"({top['wins']}W {top['draws']}D {top['losses']}L)"
            )
        persist_league_table(db, season.season_id)
        print("  persisted league_rank + team_data.live_table")
finally:
    db.close()
