#!/usr/bin/env python3
"""Quick check: ffmpeg available + moov-at-start on newest MP4s."""
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.video_faststart import mp4_has_moov_at_start

print("ffmpeg:", shutil.which("ffmpeg") or "MISSING")
videos = Path(__file__).resolve().parents[1] / "videos"
files = sorted(videos.glob("*_full.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
print("sample moov check:")
for p in files:
    ok = mp4_has_moov_at_start(p)
    print(f"  {p.name}  {p.stat().st_size // 1024} KB  {'ok' if ok else 'NEEDS_FASTSTART'}")
