import sys
import uuid
sys.path.insert(0, ".")
from utils.db import SessionLocal, Fixture, GfrDump
from utils.virtual_schedule import match_has_video
from utils.broadcast_gate import _dump_steps
from pathlib import Path

mid = uuid.UUID("114354b1-4298-4688-94c3-6032fa1a2fbe")
db = SessionLocal()
f = db.query(Fixture).filter(Fixture.match_id == mid).first()
d = db.query(GfrDump).filter(GfrDump.match_id == mid).first()
print("status", f.status if f else None, "score", f.score if f else None)
print("steps", _dump_steps(d), "video", match_has_video(d, mid))
p = Path("videos/114354b1-4298-4688-94c3-6032fa1a2fbe_full.mp4")
print("file", p.is_file(), p.stat().st_size // 1024 if p.is_file() else 0)
db.close()
