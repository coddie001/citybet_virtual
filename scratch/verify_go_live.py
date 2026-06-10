#!/usr/bin/env python3
import json
import subprocess
import sys
import urllib.request

ROOT = "/home/Warta/projects/citybet_virtuals"
MID = "66f491cf-9b4c-412e-90d1-99dc65b7e84b"

def main():
    # countdown API
    with urllib.request.urlopen("http://localhost:8000/live/all") as r:
        live = json.load(r)
    cd = live[0].get("countdown")
    print("countdown:", cd)
    assert cd and "next_match_id" in cd, "countdown missing from /live/all"

    # video codec
    path = f"{ROOT}/videos/{MID}_full.mp4"
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    codec = out.stdout.strip()
    print(f"video codec: {codec}")
    if codec != "h264":
        print("WARN: video still not h264 — run compress_videos.py")

    # video HTTP
    with urllib.request.urlopen(f"http://localhost:8000/video/{MID}") as r:
        print(f"video HTTP: {r.status} {r.headers.get('content-type')} {r.length} bytes")

if __name__ == "__main__":
    main()
