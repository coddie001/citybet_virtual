#!/usr/bin/env python3
"""Inspect gfr_stats and sidecar files for goal timing data."""
import json
import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.db import SessionLocal, GfrDump, Fixture  # noqa: E402


def main():
    db = SessionLocal()
    try:
        dumps = db.query(GfrDump).filter(GfrDump.gfr_stats.isnot(None)).limit(5).all()
        for d in dumps:
            print("=== match", d.match_id)
            stats = d.gfr_stats or {}
            print("keys:", sorted(stats.keys()))
            for k in ("goal_events", "goals", "stats_timeline", "possession"):
                if k in stats:
                    print(k, ":", json.dumps(stats[k])[:500])
            f = db.query(Fixture).filter(Fixture.match_id == d.match_id).first()
            if f and f.outcome:
                print("outcome keys:", list(f.outcome.keys()) if isinstance(f.outcome, dict) else type(f.outcome))
    finally:
        db.close()

    print("\n--- sidecar samples with goals ---")
    for p in sorted(glob.glob(str(ROOT / "dumps" / "*" / "_stats.json"))):
        data = json.loads(Path(p).read_text())
        if data.get("home_goals", 0) + data.get("away_goals", 0) > 0:
            print(p, data.get("score"), sorted(data.keys()))
            if "goal_events" in data:
                print("  goal_events:", data["goal_events"])
            break


if __name__ == "__main__":
    main()
