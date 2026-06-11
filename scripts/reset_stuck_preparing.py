#!/usr/bin/env python3
"""Reset preparing/live fixtures with no sim back to upcoming so the worker can run them."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.db import SessionLocal, Fixture, GfrDump, Season


def _steps(dump) -> int:
    if not dump or not dump.gfr_stats:
        return 0
    stats = dump.gfr_stats
    if isinstance(stats, list):
        return len(stats)
    return int(stats.get("total_steps") or stats.get("steps") or 0)


def _clear_schedule_keys(pred: dict) -> dict:
    for key in (
        "_scheduled_start_at",
        "_broadcast_started_at",
        "_live_started_at",
        "_live_stuck_at",
    ):
        pred.pop(key, None)
    return pred


def reset_stuck(db, current_gwk_only: bool = False) -> int:
    now = time.time()
    changed = 0
    active_seasons = {
        s.season_id: (s.current_gwk or 1)
        for s in db.query(Season).filter(Season.season_status == "active").all()
    }

    for f in db.query(Fixture).filter(Fixture.status.in_(("preparing", "live"))).all():
        if current_gwk_only:
            gwk = active_seasons.get(f.season_id)
            if gwk is None or f.gameweek < gwk:
                continue
        dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        if _steps(dump) >= 100:
            continue
        pred = _clear_schedule_keys(dict(f.predictions or {}))
        pred.setdefault("_processing_started_at", now)
        f.predictions = pred
        f.status = "upcoming"
        changed += 1

    if changed:
        db.commit()
    return changed


def main() -> int:
    db = SessionLocal()
    try:
        before_prep = db.query(Fixture).filter(Fixture.status == "preparing").count()
        before_live = db.query(Fixture).filter(Fixture.status == "live").count()
        n = reset_stuck(db, current_gwk_only=False)
        after_prep = db.query(Fixture).filter(Fixture.status == "preparing").count()
        after_up = db.query(Fixture).filter(Fixture.status == "upcoming").count()
        print(f"before: preparing={before_prep} live={before_live}")
        print(f"reset {n} fixture(s) → upcoming")
        print(f"after: preparing={after_prep} upcoming={after_up}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
