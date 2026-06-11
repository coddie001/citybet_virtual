#!/usr/bin/env python3
"""Report fixture step counts by status (carousel-relevant rows)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.db import SessionLocal, Fixture, GfrDump
from utils.virtual_schedule import match_has_video


def dump_steps(dump):
    if not dump or not dump.gfr_stats:
        return 0
    stats = dump.gfr_stats
    if isinstance(stats, list):
        return len(stats)
    return int(stats.get("total_steps") or stats.get("steps") or 0)


def main() -> int:
    db = SessionLocal()
    try:
        for status in ("live", "preparing", "upcoming"):
            rows = db.query(Fixture).filter(Fixture.status == status).all()
            zero = []
            for f in rows:
                dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
                steps = dump_steps(dump)
                if steps < 100:
                    pred = dict(f.predictions or {})
                    zero.append(
                        (f, steps, pred.get("_scheduled_start_at"), pred.get("_processing_started_at"))
                    )
            print(f"\n{status}: total={len(rows)} needs_sim={len(zero)}")
            for f, steps, sched, proc in zero[:8]:
                dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
                hv = match_has_video(dump, f.match_id)
                print(
                    str(f.match_id)[:8],
                    f"gw{f.gameweek}",
                    f"steps={steps}",
                    f"video={hv}",
                    f"sched={sched}",
                    f"proc={proc}",
                )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
