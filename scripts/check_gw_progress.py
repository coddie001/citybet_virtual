#!/usr/bin/env python3
import sys
sys.path.insert(0, ".")

from utils.db import SessionLocal, Fixture, Season
from utils.virtual_schedule import fixture_progress_gameweek

db = SessionLocal()
for s in db.query(Season).filter(Season.season_status == "active").all():
    prog = fixture_progress_gameweek(db, s.season_id)
    up = db.query(Fixture).filter(Fixture.season_id == s.season_id, Fixture.status == "upcoming").count()
    min_up = (
        db.query(Fixture)
        .filter(Fixture.season_id == s.season_id, Fixture.status == "upcoming")
        .order_by(Fixture.gameweek.asc())
        .first()
    )
    max_comp = (
        db.query(Fixture)
        .filter(Fixture.season_id == s.season_id, Fixture.status == "completed")
        .order_by(Fixture.gameweek.desc())
        .first()
    )
    print(
        s.tournament_name[:20],
        "prog", prog,
        "current_gwk", s.current_gwk,
        "upcoming", up,
        "min_up_gw", min_up.gameweek if min_up else None,
        "max_comp_gw", max_comp.gameweek if max_comp else None,
    )
db.close()
