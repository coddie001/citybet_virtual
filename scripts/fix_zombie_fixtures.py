"""Reset broken live/0-0 fixtures so the worker can re-simulate them."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.db import SessionLocal, Fixture, GfrDump

def main() -> None:
    db = SessionLocal()
    try:
        reset_live = 0
        reset_completed = 0
        live_rows = db.query(Fixture).filter(Fixture.status == "live").all()
        for f in live_rows:
            dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
            if dump and dump.gfr_stats:
                continue
            f.status = "upcoming"
            f.score = None
            f.outcome = None
            f.settled = False
            f.stats_recorded = False
            reset_live += 1

        completed_zeros = (
            db.query(Fixture)
            .filter(Fixture.status == "completed", Fixture.score == "0-0")
            .all()
        )
        for f in completed_zeros:
            dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
            steps = 0
            if dump and dump.gfr_stats:
                steps = int(
                    dump.gfr_stats.get("total_steps")
                    or dump.gfr_stats.get("steps")
                    or 0
                )
            if steps >= 100:
                continue  # genuine 0-0 draw
            f.status = "upcoming"
            f.score = None
            f.outcome = None
            f.settled = False
            f.stats_recorded = False
            reset_completed += 1

        db.commit()
        print(f"Reset {reset_live} zombie live + {reset_completed} fake 0-0 completed → upcoming")
    finally:
        db.close()

if __name__ == "__main__":
    main()
