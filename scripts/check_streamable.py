#!/usr/bin/env python3
from pathlib import Path
from utils.video_paths import VIDEO_DIR, resolve_streamable_video
from utils.video_faststart import mp4_has_moov_at_start, mp4_has_moov_atom, probe_mp4

for p in sorted(VIDEO_DIR.glob("*_full.mp4"))[:8]:
    mid = p.name.replace("_full.mp4", "")
    print(
        mid[:8],
        f"{p.stat().st_size // 1024}KB",
        "start", mp4_has_moov_at_start(p),
        "any", mp4_has_moov_atom(p),
        "probe", probe_mp4(p) is not None,
        "streamable", resolve_streamable_video(mid) is not None,
    )
