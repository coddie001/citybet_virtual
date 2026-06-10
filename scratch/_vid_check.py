import uuid
from pathlib import Path
from utils.db import SessionLocal, Fixture, GfrDump, Team
from utils.virtual_schedule import match_has_video, resolve_video_file

MID = uuid.UUID("bf7358e2-ccc6-41b0-9bf6-a35cd10ca2cf")
root = Path(__file__).resolve().parent.parent
db = SessionLocal()
f = db.query(Fixture).filter(Fixture.match_id == MID).first()
d = db.query(GfrDump).filter(GfrDump.match_id == MID).first()
if f:
    h = db.query(Team).filter(Team.team_id == f.home_team_id).first()
    a = db.query(Team).filter(Team.team_id == f.away_team_id).first()
    print("fixture", h.team_name if h else "?", "vs", a.team_name if a else "?", f.status, f.score)
else:
    print("no fixture")
if d:
    print("video_url", d.video_url)
    print("gfr_stats steps", (d.gfr_stats or {}).get("total_steps"))
print("has_video", match_has_video(d, MID))
p = resolve_video_file(MID, d)
print("resolved", p)
if p:
    print("size_bytes", p.stat().st_size)
for base in [root / "videos", root / ".bytecode_archive" / "videos"]:
    fp = base / f"{MID}_full.mp4"
    print("exists", fp, fp.is_file(), fp.stat().st_size if fp.is_file() else 0)
db.close()
