#!/usr/bin/env python3
"""Unit test: 3-minute spacing between queued fixtures in same league."""
import sys
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.carousel_schedule import FIRST_START_OFFSET_SEC, INTERVAL_SEC, enqueue_scheduled_fixtures
from utils.db import SessionLocal, Fixture, Season
from utils.virtual_schedule import match_has_video


def main():
    db = SessionLocal()
    try:
        season = db.query(Season).filter(Season.season_status == "active").first()
        if not season:
            print("SKIP: no season")
            return 0

        # Find upcoming with video, clear schedule for test isolation on last 2 only
        candidates = []
        for f in (
            db.query(Fixture)
            .filter(Fixture.season_id == season.season_id, Fixture.status == "upcoming")
            .order_by(Fixture.show_at_ms)
            .all()
        ):
            from utils.db import GfrDump
            dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
            if match_has_video(dump, f.match_id):
                candidates.append(f)

        if len(candidates) < 2:
            print("SKIP interval test: need 2+ video-ready upcoming (have", len(candidates), ")")
            return 0

        for f in candidates[:2]:
            pred = dict(f.predictions or {})
            pred.pop("_scheduled_start_at", None)
            f.predictions = pred
            f.status = "upcoming"
        db.commit()

        t0 = time.time()
        with patch("utils.carousel_schedule._should_run_queue_batch", return_value=True):
            with patch("utils.carousel_schedule.time.time", return_value=t0):
                n = enqueue_scheduled_fixtures(db)
        print("scheduled count:", n)

        times = []
        for f in candidates[:2]:
            db.refresh(f)
            pred = dict(f.predictions or {})
            start = pred.get("_scheduled_start_at")
            times.append(float(start) if start else None)
            print(f.status, start)

        if len(times) == 2 and times[0] and times[1]:
            delta = times[1] - times[0]
            ok = abs(delta - INTERVAL_SEC) < 2
            print(f"interval delta={delta:.0f}s expected={INTERVAL_SEC}s -> {'PASS' if ok else 'FAIL'}")
            return 0 if ok else 1
        print("FAIL: could not read two schedule times")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
