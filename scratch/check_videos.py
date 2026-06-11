import subprocess
import os
from pathlib import Path

VIDEO_DIR = Path("/home/Warta/projects/citybet_virtuals/videos")

# Find all videos that exist but don't have moov at start
import sys
sys.path.insert(0, "/home/Warta/projects/citybet_virtuals")
from utils.video_faststart import mp4_has_moov_at_start

bad_files = []
good_files = []
for f in sorted(VIDEO_DIR.glob("*_full.mp4")):
    if f.stat().st_size < 50_000:
        print(f"TINY: {f.name} ({f.stat().st_size} bytes)")
        continue
    has_moov = mp4_has_moov_at_start(f)
    if has_moov:
        good_files.append(f)
    else:
        bad_files.append(f)

print(f"\nGOOD (moov at start): {len(good_files)}")
print(f"BAD (moov at end): {len(bad_files)}")
print()
for f in bad_files:
    print(f"  BAD: {f.name}")
