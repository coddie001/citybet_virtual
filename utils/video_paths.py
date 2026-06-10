"""Single canonical location for all match MP4 files."""
from pathlib import Path
import uuid

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEO_DIR = PROJECT_ROOT / "videos"
ARCHIVE_VIDEO_DIR = PROJECT_ROOT / ".bytecode_archive" / "videos"

VIDEO_DIR.mkdir(parents=True, exist_ok=True)


def video_filename(match_id: uuid.UUID | str) -> str:
    return f"{match_id}_full.mp4"


def video_path_for(match_id: uuid.UUID | str) -> Path:
    return VIDEO_DIR / video_filename(match_id)


def video_small_path_for(match_id: uuid.UUID | str) -> Path:
    return VIDEO_DIR / f"{match_id}_full_small.mp4"


def iter_video_candidates(match_id: uuid.UUID | str, dump_video_url: str | None = None):
    """Canonical full, compressed small, then dump path — in preference order."""
    yield video_path_for(match_id)
    yield video_small_path_for(match_id)
    if dump_video_url:
        yield Path(dump_video_url)


def resolve_streamable_video(
    match_id: uuid.UUID | str,
    dump_video_url: str | None = None,
    *,
    min_bytes: int = 50_000,
) -> Path | None:
    """First browser-streamable MP4 (moov-at-start) for this match."""
    from utils.video_faststart import mp4_has_moov_at_start

    for path in iter_video_candidates(match_id, dump_video_url):
        try:
            if not path.is_file() or path.stat().st_size < min_bytes:
                continue
            if mp4_has_moov_at_start(path):
                return path
        except OSError:
            continue
    return None
