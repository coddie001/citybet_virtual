#!/usr/bin/env python3
"""Diagnose why live fixtures are not appearing on the frontend."""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.db import SessionLocal, Fixture, GfrDump, Season
from utils.virtual_schedule import match_has_video, effective_fixture_status, resolve_live_fixture


def main():
    base = "http://localhost:8000"
    print("=== /live/all ===")
    try:
        with urllib.request.urlopen(f"{base}/live/all", timeout=5) as r:
            cards = json.loads(r.read())
        for c in cards:
            fx = c.get("fixture")
            print(
                c.get("league_name"),
                "source=", c.get("source"),
                "clock=", c.get("virtual_clock_ms"),
                "fixture=",
                (fx or {}).get("match_id"),
                "status=",
                (fx or {}).get("status"),
                "has_video=",
                (fx or {}).get("has_video"),
            )
    except Exception as e:
        print("live/all failed:", e)

    db = SessionLocal()
    try:
        print("\n=== DB live fixtures ===")
        live_rows = (
            db.query(Fixture)
            .join(Season, Fixture.season_id == Season.season_id)
            .filter(Fixture.status == "live")
            .order_by(Fixture.show_at_ms.asc())
            .limit(10)
            .all()
        )
        if not live_rows:
            print("(none)")
        for f in live_rows:
            dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
            has = match_has_video(dump, f.match_id)
            eff = effective_fixture_status(f, dump)
            print(
                f.match_id,
                f"g{f.gameweek}",
                "db=live",
                f"effective={eff}",
                f"has_video={has}",
            )

        print("\n=== resolve_live_fixture per season ===")
        for season in db.query(Season).filter(Season.season_status == "active").all():
            fx, clock, src = resolve_live_fixture(db, season.season_id)
            name = " ".join(season.tournament_name.split()[:-1])
            if fx:
                dump = db.query(GfrDump).filter(GfrDump.match_id == fx.match_id).first()
                print(
                    name,
                    src,
                    fx.match_id,
                    effective_fixture_status(fx, dump),
                    match_has_video(dump, fx.match_id),
                )
            else:
                print(name, src, "no fixture")
    finally:
        db.close()


if __name__ == "__main__":
    main()
