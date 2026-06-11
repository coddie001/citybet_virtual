#!/usr/bin/env python3
"""One-shot: move archive MP4s into videos/ and fix DB paths."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import SessionLocal
from utils.video_consolidate import consolidate_videos

if __name__ == "__main__":
    db = SessionLocal()
    try:
        n = consolidate_videos(db, max_moves=100)
        print(f"consolidated: {n}")
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise SystemExit(1) from exc
    finally:
        db.close()
