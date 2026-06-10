#!/usr/bin/env python3
"""
Prepare platform for go-live: reset virtual clock and clear stuck fixtures.

Usage:
    venv/bin/python3 scripts/go_live.py
    venv/bin/python3 scripts/go_live.py --full-reset   # also reset completed → upcoming
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.db import SessionLocal, Fixture, Season


def go_live(full_reset: bool = False) -> None:
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        seasons = db.query(Season).filter(Season.season_status == "active").all()
        for s in seasons:
            s.created_at = now
            print(f"[+] Reset virtual clock for {s.tournament_name}")

        stuck = db.query(Fixture).filter(Fixture.status.in_(["live", "error"])).all()
        for f in stuck:
            f.status = "upcoming"
            f.settled = False
            f.score = None
            f.outcome = None
        if stuck:
            print(f"[+] Cleared {len(stuck)} live/error fixtures → upcoming")

        if full_reset:
            done = db.query(Fixture).filter(Fixture.status == "completed").all()
            for f in done:
                f.status = "upcoming"
                f.settled = False
                f.score = None
                f.outcome = None
            print(f"[+] Full reset: {len(done)} completed fixtures → upcoming")

        db.commit()
        print("[+] Go-live prep complete — virtual timeline starts from gameweek 1 window.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full-reset",
        action="store_true",
        help="Reset ALL completed fixtures back to upcoming (re-simulate everything)",
    )
    args = parser.parse_args()
    go_live(full_reset=args.full_reset)
