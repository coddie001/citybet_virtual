"""Repair missing MP4 files for simulated matches."""
import os
import shutil
import uuid
from pathlib import Path

from utils.db import GfrDump
from utils.video_paths import VIDEO_DIR, video_path_for
from utils.virtual_schedule import match_has_video
from workers.game_simulator import render_dump_to_video, VIDEO_STORE

ARCHIVE_ROOT = Path(__file__).resolve().parent.parent / ".bytecode_archive" / "dumps"


def _dump_steps(dump: GfrDump) -> int:
    if not dump or not dump.gfr_stats:
        return 0
    return int(
        dump.gfr_stats.get("total_steps") or dump.gfr_stats.get("steps") or 0
    )


def _resolve_paths(dump: GfrDump, match_id: uuid.UUID) -> tuple[str | None, str | None]:
    stats = dump.gfr_stats or {}
    dump_path = stats.get("dump_file")
    config_path = stats.get("match_config_path")

    archive_dir = ARCHIVE_ROOT / str(match_id)
    if not dump_path or not os.path.isfile(dump_path):
        named = archive_dir / f"{match_id}.dump"
        if named.is_file():
            dump_path = str(named)
        else:
            dumps = sorted(archive_dir.glob("*.dump"), key=lambda p: p.stat().st_mtime)
            if dumps:
                dump_path = str(dumps[-1])

    if not config_path or not os.path.isfile(config_path):
        cfg = archive_dir / f"match_{match_id}.json"
        if cfg.is_file():
            config_path = str(cfg)

    return dump_path, config_path


def repair_one(db, match_id: uuid.UUID) -> bool:
    dump = db.query(GfrDump).filter(GfrDump.match_id == match_id).first()
    if not dump or _dump_steps(dump) < 100:
        return False
    if match_has_video(dump, match_id):
        return True

    dump_path, config_path = _resolve_paths(dump, match_id)
    if not dump_path or not config_path:
        return False

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    out = render_dump_to_video(
        dump_path=dump_path,
        match_config_path=config_path,
        output_dir=VIDEO_DIR,
        match_id=str(match_id),
    )
    mp4 = out.get("mp4") if out else None
    canonical = video_path_for(match_id)
    if mp4 and os.path.isfile(mp4) and Path(mp4) != canonical:
        shutil.copy2(mp4, canonical)
        Path(mp4).unlink(missing_ok=True)
    if not canonical.is_file():
        return False

    from utils.video_faststart import finalize_mp4

    if not finalize_mp4(canonical, target_mb=4.5):
        return False

    dump.video_url = str(canonical)
    db.commit()
    return True


def repair_missing_videos(db, max_repairs: int = 1) -> int:
    """Render up to max_repairs missing videos per coordinator cycle."""
    repaired = 0
    for dump in db.query(GfrDump).order_by(GfrDump.match_id.asc()).all():
        if repaired >= max_repairs:
            break
        if _dump_steps(dump) < 100:
            continue
        if match_has_video(dump, dump.match_id):
            continue
        if repair_one(db, dump.match_id):
            repaired += 1
    return repaired
