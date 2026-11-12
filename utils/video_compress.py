"""Re-encode match MP4s to browser-friendly H.264 (Chrome / Firefox / Edge)."""
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from utils.video_encoders import available_h264_encoders, encoder_video_args

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = PROJECT_ROOT / "videos"

MIN_KB = 10
MAX_KB = 12000
ACCEPT_MAX_KB = 15000
MIN_BYTES = MIN_KB * 1024
MAX_BYTES = MAX_KB * 1024
ACCEPT_MAX_BYTES = ACCEPT_MAX_KB * 1024
TARGET_BYTES = MAX_BYTES // 2  # aim for ~6000 KB when size is unconstrained


def _file_bytes(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _size_in_range(path: Path) -> bool:
    size = _file_bytes(path)
    return MIN_BYTES <= size <= ACCEPT_MAX_BYTES


def _video_duration_sec(path: Path) -> float:
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode == 0 and out.stdout.strip():
            return max(30.0, float(out.stdout.strip()))
    except Exception:
        pass
    return 120.0


def _video_codec(path: Path) -> str:
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "csv=p=0", str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return (out.stdout or "").strip().lower()
    except Exception:
        return ""


def _target_bitrate_k(path: Path) -> int:
    """Bitrate (kbps) to land near TARGET_BYTES for this clip length."""
    dur = _video_duration_sec(path)
    kbps = int((TARGET_BYTES * 8) / dur / 1000)
    return max(600, min(2500, kbps))


def _run_ffmpeg(cmd: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=900)
        err = (result.stderr or b"").decode("utf-8", errors="replace")[-800:]
        return result.returncode == 0, err
    except Exception as exc:
        return False, str(exc)


def _snapshot_input(src: Path) -> Path:
    """Stable copy so concurrent sim/coordinator cannot race the live file."""
    fd, name = tempfile.mkstemp(suffix=".snap.mp4", dir=str(src.parent))
    import os
    os.close(fd)
    snap = Path(name)
    shutil.copy2(src, snap)
    return snap


def _encode_h264(inp: Path, out: Path, scale: str, bitrate_k: int) -> bool:
    """Transcode to H.264 using encoders available on this host."""
    encoders = available_h264_encoders()
    if not encoders:
        return False

    for encoder in encoders:
        cmd = ["ffmpeg", "-y", "-i", str(inp), "-vf", scale, *encoder_video_args(encoder, bitrate_k), str(out)]
        ok, err = _run_ffmpeg(cmd)
        if not ok:
            log.debug("Encoder %s failed for %s: %s", encoder, inp.name, err[-200:])
            out.unlink(missing_ok=True)
            continue
        if not out.is_file() or _file_bytes(out) < 5_000:
            out.unlink(missing_ok=True)
            continue
        from utils.video_faststart import probe_mp4
        if probe_mp4(out) is None:
            out.unlink(missing_ok=True)
            continue
        log.info("Encoded with %s → %s (%.0f KB)", encoder, out.name, _file_bytes(out) / 1024)
        return True
    return False


def _install_candidate(src: Path, candidate: Path) -> bool:
    """Replace src only when candidate is within the 4000–5000 KB band."""
    size = _file_bytes(candidate)
    if size < MIN_BYTES:
        log.warning(
            "Rejecting encode for %s — %.0f KB below %d KB floor",
            src.name, size / 1024, MIN_KB,
        )
        return False
    if size > MAX_BYTES:
        log.warning(
            "Rejecting encode for %s — %.0f KB above %d KB cap",
            src.name, size / 1024, MAX_KB,
        )
        return False
    backup = src.with_name(f"{src.stem}.precompress.mp4")
    try:
        if src.is_file():
            shutil.copy2(src, backup)
        candidate.replace(src)
        backup.unlink(missing_ok=True)
        log.info("Compressed video → %.0f KB (%s)", _file_bytes(src) / 1024, src.name)
        return True
    except OSError as exc:
        log.warning("Could not install compressed video for %s: %s", src.name, exc)
        if backup.is_file() and not src.is_file():
            backup.replace(src)
        return False


def compress_mp4(src_path: str, target_mb: float = 4.5) -> str:
    """Re-encode MP4 to H.264 within 4000–5000 KB for web playback."""
    from utils.video_faststart import is_finalizable

    src = Path(src_path)
    if not src.is_file():
        return src_path

    if not is_finalizable(src, check_writing=True):
        log.debug("Skip compress — MP4 not finalizable yet: %s", src.name)
        return str(src)

    orig_size = _file_bytes(src)
    codec = _video_codec(src)
    if codec in ("h264", "avc1") and _size_in_range(src):
        return str(src)
    if codec in ("h264", "avc1") and orig_size >= MIN_BYTES and orig_size <= MAX_BYTES:
        return str(src)

    snap = _snapshot_input(src)
    try:
        base_k = _target_bitrate_k(snap)
        tmp_path = src.with_name(f"{src.stem}_compressed.mp4")
        best: tuple[Path, int] | None = None

        for scale, mult in (
            ("scale=480:-2", 1.0),
            ("scale=480:-2", 1.15),
            ("scale=420:-2", 1.3),
            ("scale=360:-2", 1.5),
        ):
            bitrate = int(base_k * mult)
            if not _encode_h264(snap, tmp_path, scale, bitrate_k=bitrate):
                continue
            size = _file_bytes(tmp_path)
            if MIN_BYTES <= size <= MAX_BYTES:
                if _install_candidate(src, tmp_path):
                    return str(src)
            if size >= MIN_BYTES and (
                best is None or abs(size - TARGET_BYTES) < abs(best[1] - TARGET_BYTES)
            ):
                if best and best[0].is_file() and best[0] != tmp_path:
                    best[0].unlink(missing_ok=True)
                best = (tmp_path, size)
            else:
                tmp_path.unlink(missing_ok=True)
                tmp_path = src.with_name(f"{src.stem}_compressed.mp4")

        if best and _install_candidate(src, best[0]):
            return str(src)

        tmp_path.unlink(missing_ok=True)

        encoders = available_h264_encoders()
        if encoders:
            fallback = src.with_name(f"{src.stem}_fallback.mp4")
            fb_k = max(_target_bitrate_k(snap), 900)
            encoder = encoders[0]
            ok, err = _run_ffmpeg([
                "ffmpeg", "-y", "-i", str(snap), "-vf", "scale=480:-2",
                *encoder_video_args(encoder, fb_k), str(fallback),
            ])
            if ok and fallback.is_file() and MIN_BYTES <= _file_bytes(fallback) <= MAX_BYTES:
                if _install_candidate(src, fallback):
                    return str(src)
            fallback.unlink(missing_ok=True)
            if err and "Unknown encoder" not in err:
                log.warning("Fallback %s failed for %s: %s", encoder, src.name, err[-300:])
    finally:
        snap.unlink(missing_ok=True)

    log.warning(
        "All H.264 encoders failed for %s (codec=%s, %.0f KB, encoders=%s) — keeping original",
        src.name,
        codec or "unknown",
        orig_size / 1024,
        ",".join(available_h264_encoders()) or "none",
    )
    return str(src)


def needs_reencode(path: Path) -> bool:
    codec = _video_codec(path)
    if codec and codec not in ("h264", "avc1"):
        return True
    return _file_bytes(path) > ACCEPT_MAX_BYTES
