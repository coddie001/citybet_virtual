"""Ensure MP4 files are browser-streamable (moov atom before mdat)."""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

log = logging.getLogger(__name__)

MOOV_SCAN_BYTES = 65_536
TAIL_SCAN_BYTES = 512_000
SETTLE_SEC = 2.0


def mp4_has_moov_at_start(path: Path, scan_bytes: int = MOOV_SCAN_BYTES) -> bool:
    """True when the moov atom appears in the first scan_bytes (faststart layout)."""
    try:
        with path.open("rb") as fh:
            header = fh.read(scan_bytes)
        return b"moov" in header
    except OSError:
        return False


def mp4_has_moov_atom(path: Path) -> bool:
    """True when moov exists anywhere (start or tail — normal MP4 places it at end)."""
    if mp4_has_moov_at_start(path):
        return True
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > TAIL_SCAN_BYTES:
                fh.seek(size - TAIL_SCAN_BYTES)
            return b"moov" in fh.read()
    except OSError:
        return False


def probe_mp4(path: Path) -> Optional[dict]:
    """ffprobe metadata — None when file is incomplete, corrupt, or has no video stream."""
    if not path.is_file():
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration,size:stream=codec_name,width,height",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout or "{}")
        streams = [s for s in (data.get("streams") or []) if s.get("codec_name")]
        if not streams:
            return None
        fmt = data.get("format") or {}
        duration = float(fmt.get("duration") or 0)
        if duration <= 0:
            return None
        codec = str(streams[0].get("codec_name") or "").lower()
        return {
            "duration": duration,
            "codec": codec,
            "size": int(fmt.get("size") or path.stat().st_size),
        }
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return None


def is_still_writing(path: Path, settle_sec: float = SETTLE_SEC) -> bool:
    """True while file size is still growing (sim render in progress)."""
    try:
        s1 = path.stat().st_size
        if settle_sec <= 0:
            return False
        time.sleep(settle_sec)
        s2 = path.stat().st_size
        return s2 > s1
    except OSError:
        return True


def is_recently_modified(path: Path, within_sec: float = 45.0) -> bool:
    try:
        return (time.time() - path.stat().st_mtime) < within_sec
    except OSError:
        return True


def is_finalizable(path: Path, *, check_writing: bool = True) -> bool:
    """True when MP4 is a complete, readable file (not mid-render)."""
    if not path.is_file():
        return False
    try:
        if path.stat().st_size < 5_000:
            return False
    except OSError:
        return False

    if not mp4_has_moov_atom(path):
        if check_writing and is_recently_modified(path):
            return False
        return False

    meta = probe_mp4(path)
    if meta is not None:
        return True

    if check_writing:
        if is_recently_modified(path):
            return False
        if is_still_writing(path, settle_sec=1.0):
            return False
    return False


def quarantine_incomplete(path: Path) -> bool:
    """Move broken partial MP4 aside so coordinator stops retrying ffmpeg on it."""
    if not path.is_file():
        return False
    dest = path.with_name(f"{path.stem}.partial.mp4")
    try:
        if dest.is_file():
            dest.unlink()
        path.rename(dest)
        log.warning("Quarantined invalid MP4 → %s", dest.name)
        return True
    except OSError as exc:
        log.warning("Could not quarantine %s: %s", path.name, exc)
        return False


def sanitize_corrupt_videos(video_dir: Path | None = None) -> int:
    """Quarantine MP4 shells with no video stream (failed remux / mid-render)."""
    from utils.video_paths import VIDEO_DIR

    root = video_dir or VIDEO_DIR
    if not root.is_dir():
        return 0
    removed = 0
    for path in root.glob("*_full.mp4"):
        if not path.is_file() or path.stat().st_size < 5_000:
            continue
        if probe_mp4(path) is None and not is_recently_modified(path, within_sec=90.0):
            if quarantine_incomplete(path):
                removed += 1
    return removed


def needs_faststart(path: Path) -> bool:
    if not is_finalizable(path, check_writing=True):
        return False
    return not mp4_has_moov_at_start(path)


@contextmanager
def _finalize_lock(path: Path) -> Iterator[bool]:
    """Non-blocking lock — skip if sim/coordinator already finalizing this file."""
    lock_path = path.with_name(f"{path.stem}.finalize.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = lock_path.open("w")
    acquired = False
    try:
        import fcntl

        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError:
            acquired = False
        yield acquired
    except ImportError:
        yield True
    finally:
        if acquired:
            try:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except ImportError:
                pass
        fh.close()
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def wait_for_finalizable(path: Path, timeout_sec: float = 120.0) -> bool:
    """Wait until sim finishes writing a complete MP4."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if is_finalizable(path, check_writing=False):
            return True
        if not path.is_file():
            time.sleep(1.0)
            continue
        if not is_recently_modified(path, within_sec=5.0) and mp4_has_moov_atom(path):
            if probe_mp4(path) is not None:
                return True
        time.sleep(2.0)
    return is_finalizable(path, check_writing=False)


def remux_faststart(src: Path) -> bool:
    """Copy streams and move moov to file start — required for HTML5 range playback."""
    if not src.is_file():
        return False
    if not is_finalizable(src, check_writing=True):
        log.debug("Skip faststart remux — render not complete: %s", src.name)
        return False
    if mp4_has_moov_at_start(src):
        return True

    tmp = src.with_name(f"{src.stem}_faststart.tmp.mp4")
    snap = None
    try:
        fd, snap_name = tempfile.mkstemp(suffix=".snap.mp4", dir=str(src.parent))
        import os
        os.close(fd)
        snap = Path(snap_name)
        shutil.copy2(src, snap)
        cmd = [
            "ffmpeg", "-y", "-i", str(snap),
            "-c", "copy", "-movflags", "+faststart",
            str(tmp),
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0 or not tmp.is_file() or tmp.stat().st_size < 50_000:
            err = (result.stderr or b"").decode("utf-8", errors="replace")[-300:]
            log.warning("faststart remux failed for %s: %s", src.name, err)
            tmp.unlink(missing_ok=True)
            return False
        if probe_mp4(tmp) is None:
            log.warning("faststart remux produced invalid MP4 for %s — discarded", src.name)
            tmp.unlink(missing_ok=True)
            return False
        tmp.replace(src)
        log.info("faststart remux OK → %s (%.1f MB)", src.name, src.stat().st_size / (1024 * 1024))
        return True
    except FileNotFoundError:
        log.warning("ffmpeg not found — cannot remux %s", src.name)
        return False
    except Exception as exc:
        log.warning("faststart remux error for %s: %s", src.name, exc)
        tmp.unlink(missing_ok=True)
        return False
    finally:
        if snap is not None:
            snap.unlink(missing_ok=True)


def finalize_mp4(path: Path, target_mb: float = 4.5) -> bool:
    """Remux for streaming, then re-encode to H.264 if needed. Returns True on success."""
    from utils.video_compress import compress_mp4, needs_reencode

    if not path.is_file():
        return False

    with _finalize_lock(path) as acquired:
        if not acquired:
            log.debug("Skip finalize — already in progress: %s", path.name)
            return False

        if not wait_for_finalizable(path, timeout_sec=30.0):
            if not is_finalizable(path, check_writing=True):
                meta = probe_mp4(path)
                if meta is None and not is_still_writing(path, settle_sec=0.5):
                    age = time.time() - path.stat().st_mtime
                    if age > 120 and not mp4_has_moov_atom(path):
                        quarantine_incomplete(path)
                else:
                    log.debug("Skip finalize — render in progress: %s", path.name)
                return False

        if not remux_faststart(path):
            return False

        if needs_reencode(path):
            compress_mp4(str(path), target_mb=target_mb)
            if not is_finalizable(path, check_writing=False):
                return False

        if needs_faststart(path):
            return remux_faststart(path)

        return is_finalizable(path, check_writing=False)


def finalize_recent_mp4s(video_dir: Path | None = None, max_files: int = 3) -> int:
    """Post-render hook: remux/compress freshly written MP4s lacking faststart."""
    from utils.video_paths import VIDEO_DIR

    root = video_dir or VIDEO_DIR
    if not root.is_dir():
        return 0

    candidates = sorted(
        root.glob("*_full.mp4"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    done = 0
    for path in candidates:
        if done >= max_files:
            break
        if not path.is_file():
            continue
        if not mp4_has_moov_atom(path):
            continue
        if mp4_has_moov_at_start(path) and not needs_reencode_path(path):
            continue
        if finalize_mp4(path):
            done += 1
    return done


def needs_reencode_path(path: Path) -> bool:
    from utils.video_compress import needs_reencode
    return needs_reencode(path)
