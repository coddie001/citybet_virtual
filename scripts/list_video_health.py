#!/usr/bin/env python3
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "videos"
for p in sorted(root.glob("*_full.mp4"))[:30]:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(p)],
        capture_output=True, text=True,
    )
    codec = (r.stdout or "").strip() or "BROKEN"
    kb = p.stat().st_size // 1024
    print(f"{kb:6d} KB  {codec:10s}  {p.name}")
