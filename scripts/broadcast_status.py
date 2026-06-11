#!/usr/bin/env python3
"""Broadcast pipeline diagnostic — preparing/live/video state."""
import sys
import time

sys.path.insert(0, ".")

from utils.db import SessionLocal, Fixture, GfrDump, Season
from utils.virtual_schedule import match_has_video, fixture_progress_gameweek
from utils.broadcast_gate import _dump_steps

db = SessionLocal()
now = time.time()
for s in db.query(Season).filter(Season.season_status == "active").all():
    name = " ".join(s.tournament_name.split()[:-1])
    prep = db.query(Fixture).filter(
        Fixture.season_id == s.season_id, Fixture.status == "preparing"
    ).all()
    live_n = db.query(Fixture).filter(
        Fixture.season_id == s.season_id, Fixture.status == "live"
    ).count()
    prog = fixture_progress_gameweek(db, s.season_id)
    print(f"\n{name}: preparing={len(prep)} live={live_n} prog_gw={prog}")
    for f in sorted(prep, key=lambda x: (dict(x.predictions or {}).get("_scheduled_start_at") or 0)):
        pred = dict(f.predictions or {})
        start = pred.get("_scheduled_start_at")
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        steps = _dump_steps(dump)
        hv = match_has_video(dump, f.match_id)
        overdue = bool(start and now >= float(start))
        until = int(float(start) - now) if start else None
        print(
            f"  {str(f.match_id)[:8]} gw{f.gameweek} until_kickoff={until}s "
            f"steps={steps} video={hv} overdue={overdue} proc={bool(pred.get('_processing_started_at'))}"
        )

live_all = db.query(Fixture).filter(Fixture.status == "live").all()
print(f"\nLIVE globally: {len(live_all)}")
for f in live_all:
    dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
    print(f"  {f.match_id} video={match_has_video(dump, f.match_id)}")
db.close()
