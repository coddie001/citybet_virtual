#!/usr/bin/env python3
import sys
sys.path.insert(0, ".")

from utils.db import SessionLocal, Fixture, GfrDump
from utils.carousel_schedule import build_carousel_response
from utils.virtual_schedule import match_has_video
from utils.video_paths import VIDEO_DIR

db = SessionLocal()
carousel = build_carousel_response(db)
items = carousel["items"]
print("carousel total", len(items), "has_video", sum(1 for i in items if i.get("has_video")))
statuses = {}
for i in items:
    statuses[i["status"]] = statuses.get(i["status"], 0) + 1
print("statuses", statuses)

video_ids = {p.name.replace("_full.mp4", "") for p in VIDEO_DIR.glob("*_full.mp4")}
carousel_ids = {i["match_id"] for i in items}
overlap = video_ids & carousel_ids
print("video files", len(video_ids), "carousel overlap", len(overlap))

# fixtures with video not on carousel
with_video = []
for p in VIDEO_DIR.glob("*_full.mp4"):
    mid_str = p.name.replace("_full.mp4", "")
    import uuid
    try:
        mid = uuid.UUID(mid_str)
    except ValueError:
        continue
    dump = db.query(GfrDump).filter(GfrDump.match_id == mid).first()
    if match_has_video(dump, mid):
        f = db.query(Fixture).filter(Fixture.match_id == mid).first()
        with_video.append((mid_str[:8], f.status if f else None, f.gameweek if f else None, mid_str in carousel_ids))
print("streamable fixtures sample:")
for row in with_video[:10]:
    print(" ", row)

# preparing/live globally
for st in ("preparing", "live"):
    n = db.query(Fixture).filter(Fixture.status == st).count()
    print(st, n)

from utils.carousel_schedule import schedule_mode
print("schedule_mode", schedule_mode())
db.close()
