#!/usr/bin/env python3
"""Complete simmed backlog fixtures that never got an MP4 (scores from sim data)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.broadcast_gate import purge_backlog_without_video
from utils.db import SessionLocal

if __name__ == "__main__":
    db = SessionLocal()
    try:
        n = purge_backlog_without_video(db)
        print(f"done: {n} backlog fixture(s) completed without video")
    finally:
        db.close()
