import sys
sys.path.insert(0, "/home/Warta/projects/citybet_virtuals")
from utils.db import SessionLocal, GfrDump
from utils.video_faststart import mp4_has_moov_at_start
from pathlib import Path
import uuid

VIDEO_DIR = Path("/home/Warta/projects/citybet_virtuals/videos")

# Check corrupt/missing-moov files & their GfrDump entries
bad_ids = [
    "114354b1-4298-4688-94c3-6032fa1a2fbe",
]

db = SessionLocal()
for mid_str in bad_ids:
    mid = uuid.UUID(mid_str)
    dump = db.query(GfrDump).filter(GfrDump.match_id == mid).first()
    print(f"Match: {mid_str}")
    print(f"  dump.video_url: {dump.video_url if dump else 'NO DUMP'}")
    print(f"  dump.match_video: {dump.match_video if dump else 'NO DUMP'}")
    # Delete corrupt file
    corrupt = VIDEO_DIR / f"{mid_str}_full.mp4"
    if corrupt.is_file():
        print(f"  Removing corrupt file: {corrupt.name}")
        corrupt.unlink()
        print("  DONE")
db.close()

print()
print("Re-checking good videos count:")
good = bad = 0
for f in sorted(VIDEO_DIR.glob("*_full.mp4")):
    if f.stat().st_size < 50_000:
        continue
    if mp4_has_moov_at_start(f):
        good += 1
    else:
        bad += 1
print(f"  GOOD: {good}, BAD: {bad}")
