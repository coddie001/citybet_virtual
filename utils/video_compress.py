"""Re-encode match MP4s to browser-friendly H.264 (Chrome / Firefox / Edge)."""
import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = PROJECT_ROOT / "videos"


def _encode_h264(inp: Path, out: Path, scale: str, bitrate_k: int) -> bool:
    """Try available H.264 encoders (libopenh264 preferred on Fedora)."""
    profiles = [
        ("libopenh264", ["-b:v", f"{bitrate_k}k", "-maxrate", f"{bitrate_k}k", "-bufsize", f"{bitrate_k * 2}k"]),
        ("h264_nvenc", ["-b:v", f"{bitrate_k}k", "-pix_fmt", "yuv420p"]),
        ("h264_vaapi", ["-b:v", f"{bitrate_k}k"]),
        ("libx264", ["-pix_fmt", "yuv420p", "-profile:v", "main", "-crf", "33", "-preset", "fast"]),
    ]
    for encoder, extra in profiles:
        cmd = [
            "ffmpeg", "-y", "-i", str(inp),
            "-vf", scale,
            "-c:v", encoder,
            *extra,
            "-an", "-movflags", "+faststart",
            str(out),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=600)
            if result.returncode == 0 and out.is_file() and out.stat().st_size > 1000:
                log.info("Encoded with %s → %s", encoder, out.name)
                return True
        except Exception as exc:
            log.debug("Encoder %s failed: %s", encoder, exc)
    return False


def compress_mp4(src_path: str, target_mb: float = 5.0) -> str:
    """Re-encode MP4 to H.264 at ~target_mb for web playback."""
    src = Path(src_path)
    if not src.is_file():
        return src_path

    tmp_path = src.with_name(f"{src.stem}_compressed.mp4")
    try:
        if not _encode_h264(src, tmp_path, "scale=480:-2", bitrate_k=800):
            log.warning("All H.264 encoders failed for %s", src.name)
            return str(src)

        size_mb = tmp_path.stat().st_size / (1024 * 1024)
        for scale, bitrate in (("scale=360:-2", 500), ("scale=320:-2", 350)):
            if size_mb <= target_mb:
                break
            smaller = src.with_name(f"{src.stem}_small.mp4")
            if _encode_h264(src, smaller, scale, bitrate_k=bitrate) and smaller.stat().st_size < tmp_path.stat().st_size:
                tmp_path.unlink(missing_ok=True)
                tmp_path = smaller
                size_mb = tmp_path.stat().st_size / (1024 * 1024)

        src.unlink(missing_ok=True)
        tmp_path.rename(src)
        log.info("Compressed video → %.1f MB (%s)", size_mb, src.name)
    except FileNotFoundError:
        log.warning("ffmpeg not found — skipping video compression")
    except Exception as exc:
        log.warning("Video compression failed, keeping original: %s", exc)
        tmp_path.unlink(missing_ok=True)
    return str(src)


def needs_reencode(path: Path) -> bool:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        codec = (out.stdout or "").strip().lower()
        if codec and codec not in ("h264", "avc1"):
            return True
    except Exception:
        pass
    return path.stat().st_size / (1024 * 1024) > 5.0
