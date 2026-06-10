"""Ensure MP4 files are browser-streamable (moov atom before mdat)."""
import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

MOOV_SCAN_BYTES = 65_536


def mp4_has_moov_at_start(path: Path, scan_bytes: int = MOOV_SCAN_BYTES) -> bool:
    """True when the moov atom appears in the first scan_bytes (faststart layout)."""
    try:
        with path.open("rb") as fh:
            header = fh.read(scan_bytes)
        return b"moov" in header
    except OSError:
        return False


def needs_faststart(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        if path.stat().st_size < 1024:
            return False
    except OSError:
        return False
    return not mp4_has_moov_at_start(path)


def remux_faststart(src: Path) -> bool:
    """Copy streams and move moov to file start — required for HTML5 range playback."""
    if not src.is_file():
        return False
    if not needs_faststart(src):
        return True

    tmp = src.with_name(f"{src.stem}_faststart.tmp.mp4")
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-c", "copy", "-movflags", "+faststart",
        str(tmp),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0 or not tmp.is_file() or tmp.stat().st_size < 1024:
            log.warning("faststart remux failed for %s: %s", src.name, (result.stderr or b"")[-200:])
            tmp.unlink(missing_ok=True)
            return False
        src.unlink(missing_ok=True)
        tmp.rename(src)
        log.info("faststart remux OK → %s (%.1f MB)", src.name, src.stat().st_size / (1024 * 1024))
        return True
    except FileNotFoundError:
        log.warning("ffmpeg not found — cannot remux %s", src.name)
        return False
    except Exception as exc:
        log.warning("faststart remux error for %s: %s", src.name, exc)
        tmp.unlink(missing_ok=True)
        return False


def finalize_mp4(path: Path, target_mb: float = 5.0) -> Path:
    """Remux for streaming, then re-encode to H.264 if needed."""
    from utils.video_compress import compress_mp4, needs_reencode

    if not path.is_file():
        return path
    remux_faststart(path)
    if needs_reencode(path):
        compress_mp4(str(path), target_mb=target_mb)
    elif needs_faststart(path):
        remux_faststart(path)
    return path


def finalize_recent_mp4s(video_dir: Path | None = None, max_files: int = 3) -> int:
    """Post-render hook: remux/compress freshly written MP4s lacking faststart."""
    from utils.video_paths import VIDEO_DIR

    root = video_dir or VIDEO_DIR
    if not root.is_dir():
        return 0

    candidates = sorted(
        (p for p in root.glob("*_full.mp4") if needs_faststart(p)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    done = 0
    for path in candidates[:max_files]:
        if finalize_mp4(path):
            done += 1
    return done
