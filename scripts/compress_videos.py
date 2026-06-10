#!/usr/bin/env python3
"""
Re-encode match MP4s to browser-friendly H.264 (Chrome / Firefox / Edge).

Usage:
    venv/bin/python3 scripts/compress_videos.py
    venv/bin/python3 scripts/compress_videos.py --match-id 536a61af-05e0-4317-a294-54b7f988228a
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.video_compress import VIDEO_DIR, compress_mp4, needs_reencode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--match-id", help="Single match UUID to compress")
    parser.add_argument("--max-mb", type=float, default=8.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    paths = (
        [VIDEO_DIR / f"{args.match_id}_full.mp4"]
        if args.match_id
        else sorted(VIDEO_DIR.glob("*_full.mp4"))
    )

    done = 0
    for path in paths:
        if not path.is_file():
            print(f"[!] Missing {path.name}")
            continue
        if not args.force and not needs_reencode(path):
            print(f"[=] OK {path.name}")
            continue
        before = path.stat().st_size / (1024 * 1024)
        print(f"[~] Compressing {path.name} ({before:.1f} MB)…")
        compress_mp4(str(path), target_mb=args.max_mb)
        after = path.stat().st_size / (1024 * 1024)
        print(f"[+] {path.name} → {after:.1f} MB")
        done += 1

    print(f"Done — re-encoded {done} video(s).")


if __name__ == "__main__":
    main()
