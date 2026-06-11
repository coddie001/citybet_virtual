"""Move/copy all MP4s into videos/ and update DB paths."""
import logging
import shutil
import uuid
from pathlib import Path

from utils.db import GfrDump
from utils.video_paths import ARCHIVE_VIDEO_DIR, VIDEO_DIR

log = logging.getLogger(__name__)


def consolidate_videos(db, max_moves: int = 10) -> int:
    """Ensure every match video lives under videos/ only."""
    moved = 0

    for mp4 in ARCHIVE_VIDEO_DIR.glob("*_full.mp4"):
        if moved >= max_moves:
            break
        mid_str = mp4.name.replace("_full.mp4", "")
        dest = VIDEO_DIR / mp4.name
        if dest.is_file() and dest.stat().st_size >= mp4.stat().st_size:
            mp4.unlink(missing_ok=True)
            moved += 1
            continue
        shutil.copy2(mp4, dest)
        mp4.unlink(missing_ok=True)
        try:
            mid = uuid.UUID(mid_str)
        except ValueError:
            continue
        dump = db.query(GfrDump).filter(GfrDump.match_id == mid).first()
        if dump:
            dump.video_url = str(dest)
        moved += 1
        log.info("Consolidated video → %s", dest)

    path_updates = 0
    for dump in db.query(GfrDump).all():
        if dump.video_url and str(dump.video_url).startswith(str(ARCHIVE_VIDEO_DIR)):
            name = Path(dump.video_url).name
            dest = VIDEO_DIR / name
            src = Path(dump.video_url)
            if src.is_file() and not dest.is_file():
                shutil.copy2(src, dest)
            if dest.is_file():
                dump.video_url = str(dest)
                path_updates += 1

    if moved or path_updates:
        db.commit()
    return moved + path_updates
