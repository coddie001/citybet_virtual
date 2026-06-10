#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.db import SessionLocal, Fixture, GfrDump, Season
from utils.virtual_schedule import match_has_video, virtual_clock_ms

db = SessionLocal()
for season in db.query(Season).filter(Season.season_status == "active").all():
    name = " ".join(season.tournament_name.split()[:-1])
    clock = virtual_clock_ms(season, db)
    print(f"\n=== {name} clock={clock} gw={season.current_gwk} ===")
    with_video = 0
    for f in (
        db.query(Fixture)
        .filter(Fixture.season_id == season.season_id, Fixture.status == "upcoming")
        .order_by(Fixture.show_at_ms)
        .limit(15)
        .all()
    ):
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        hv = match_has_video(dump, f.match_id)
        if hv:
            with_video += 1
        steps = 0
        if dump and dump.gfr_stats:
            steps = len(dump.gfr_stats) if isinstance(dump.gfr_stats, list) else 0
        print(
            str(f.match_id)[:8],
            f"gw{f.gameweek}",
            f"show={f.show_at_ms}",
            f"past={f.show_at_ms <= clock}",
            f"video={hv}",
            f"steps={steps}",
        )
    print(f"upcoming with video (first 15): {with_video}")
db.close()
