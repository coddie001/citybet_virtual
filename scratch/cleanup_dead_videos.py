"""
Cleans up GfrDump rows where the video_url points to a file that no longer exists
or is not streamable (no moov atom). This ensures the backend's _latest_completed_with_video
query only picks fixtures with actual working video files.
"""
import sys
sys.path.insert(0, "/home/Warta/projects/citybet_virtuals")

from utils.db import SessionLocal, GfrDump, Fixture
from utils.video_paths import resolve_streamable_video, VIDEO_DIR
from pathlib import Path
import uuid

db = SessionLocal()

dumps = db.query(GfrDump).all()
cleaned = 0

for dump in dumps:
    # Try to resolve a streamable video for this match
    streamable = resolve_streamable_video(dump.match_id, dump.video_url)
    
    if streamable is not None:
        # Video is fine
        continue
    
    # No streamable video — check if there's a broken/missing reference to clear
    if dump.video_url or dump.match_video:
        video_url_path = Path(dump.video_url) if dump.video_url else None
        file_gone = video_url_path is None or not video_url_path.is_file()
        
        if file_gone:
            print(f"  Clearing dead video_url for {dump.match_id}: {dump.video_url}")
            dump.video_url = None
            dump.match_video = None
            cleaned += 1

if cleaned:
    db.commit()
    print(f"\nCleaned {cleaned} dead GfrDump video references.")
else:
    print("No dead video references found — all good.")

db.close()
