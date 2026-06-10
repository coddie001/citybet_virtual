import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.db import SessionLocal, Fixture, GfrDump

db = SessionLocal()
rows = (
    db.query(Fixture)
    .filter(Fixture.status == "completed", Fixture.score == "0-0")
    .order_by(Fixture.show_at_ms.desc())
    .limit(5)
    .all()
)
for f in rows:
    dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
    steps = None
    if dump and dump.gfr_stats:
        steps = dump.gfr_stats.get("total_steps") or dump.gfr_stats.get("steps")
    print("steps", steps, "score", f.score)

fake = 0
for f in db.query(Fixture).filter(Fixture.status == "completed", Fixture.score == "0-0").all():
    dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
    steps = 0
    if dump and dump.gfr_stats:
        steps = int(dump.gfr_stats.get("total_steps") or dump.gfr_stats.get("steps") or 0)
    if steps < 100:
        fake += 1
print("fake_0-0 (steps<100):", fake)
db.close()
