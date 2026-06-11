#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.video_compress import _video_codec, compress_mp4
from utils.video_encoders import available_h264_encoders
from utils.video_faststart import finalize_mp4, is_finalizable, probe_mp4

mid = "22f16022-9e6f-4d13-95bd-4c1c14a25e6b"
p = Path(f"videos/{mid}_full.mp4")
print("path:", p, "exists:", p.is_file())
if not p.is_file():
    sys.exit(1)
print("size_kb:", p.stat().st_size // 1024)
print("codec:", _video_codec(p))
print("probe:", probe_mp4(p))
print("finalizable:", is_finalizable(p, check_writing=False))
print("encoders:", available_h264_encoders())
ok = finalize_mp4(p, target_mb=4.5)
print("finalize:", ok, "size_kb:", p.stat().st_size // 1024)
print("codec after:", _video_codec(p))
