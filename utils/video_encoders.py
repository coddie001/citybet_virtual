"""Detect and configure ffmpeg H.264 encoders (Fedora ships libopenh264, not libx264)."""
from __future__ import annotations

import logging
import subprocess
from functools import lru_cache

log = logging.getLogger(__name__)

# Fedora/ffmpeg-free order — libopenh264 is the portable default here.
_ENCODER_PREFERENCE = (
    "libopenh264",
    "h264_nvenc",
    "h264_vaapi",
    "h264_amf",
    "h264_qsv",
    "h264_v4l2m2m",
    "libx264",
)


@lru_cache(maxsize=1)
def available_h264_encoders() -> tuple[str, ...]:
    """Encoders present in this ffmpeg build, best-first for our target platform."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = (result.stdout or "") + (result.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Could not list ffmpeg encoders: %s", exc)
        return ("libopenh264",)

    found: list[str] = []
    for line in text.splitlines():
        if not line.strip().startswith("V"):
            continue
        for name in _ENCODER_PREFERENCE:
            if name in line and name not in found:
                found.append(name)
                break

    ordered = [name for name in _ENCODER_PREFERENCE if name in found]
    if not ordered:
        log.warning("No H.264 encoder found in ffmpeg — install ffmpeg with libopenh264 or libx264")
    elif "libx264" not in ordered and "libopenh264" in ordered:
        log.debug("Using libopenh264 (libx264 not installed on this host)")
    return tuple(ordered)


def encoder_video_args(encoder: str, bitrate_k: int) -> list[str]:
    """ffmpeg output args for a given H.264 encoder."""
    tail = ["-an", "-movflags", "+faststart"]
    br = str(bitrate_k)
    if encoder == "libopenh264":
        return [
            "-c:v", "libopenh264",
            "-b:v", f"{br}k", "-maxrate", f"{br}k", "-bufsize", f"{int(bitrate_k * 2)}k",
            "-pix_fmt", "yuv420p",
            *tail,
        ]
    if encoder == "libx264":
        return [
            "-c:v", "libx264", "-preset", "fast",
            "-b:v", f"{br}k", "-maxrate", f"{br}k", "-bufsize", f"{int(bitrate_k * 2)}k",
            "-pix_fmt", "yuv420p", "-profile:v", "baseline", "-level", "3.0",
            *tail,
        ]
    if encoder in ("h264_nvenc", "h264_vaapi", "h264_amf", "h264_qsv", "h264_v4l2m2m"):
        return ["-c:v", encoder, "-b:v", f"{br}k", "-pix_fmt", "yuv420p", *tail]
    return ["-c:v", encoder, "-b:v", f"{br}k", "-pix_fmt", "yuv420p", *tail]
