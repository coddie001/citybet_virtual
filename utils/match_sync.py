"""Build video-synced match state from GFR dumps and gfr_stats."""
from __future__ import annotations

import pickle
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DUMPS_DIR = PROJECT_ROOT / ".bytecode_archive" / "dumps"
if not DUMPS_DIR.is_dir():
    DUMPS_DIR = PROJECT_ROOT / "dumps"
VIDEO_DIR = PROJECT_ROOT / "videos"

DEFAULT_VIDEO_DURATION_SEC = 300.0
DEFAULT_TOTAL_STEPS = 3001

# Cache ffprobe duration results — MP4 duration doesn't change after creation.
_duration_cache: dict[str, float] = {}


def _resolve_dump_path(match_id: uuid.UUID, gfr_stats: Optional[dict]) -> Optional[Path]:
    if gfr_stats:
        dump_file = gfr_stats.get("dump_file")
        if dump_file:
            p = Path(dump_file)
            if p.is_file():
                return p
    named = DUMPS_DIR / str(match_id) / f"{match_id}.dump"
    if named.is_file():
        return named
    folder = DUMPS_DIR / str(match_id)
    if folder.is_dir():
        dumps = sorted(folder.glob("*.dump"), key=lambda x: x.stat().st_mtime, reverse=True)
        if dumps:
            return dumps[0]
    return None


def _resolve_video_duration_sec(match_id: uuid.UUID) -> float:
    for name in (f"{match_id}_full.mp4", f"{match_id}_full_compressed.mp4"):
        path = VIDEO_DIR / name
        if not path.is_file():
            continue
        cache_key = str(path)
        if cache_key in _duration_cache:
            return _duration_cache[cache_key]
        try:
            import subprocess

            out = subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            if out:
                dur = max(1.0, float(out))
                _duration_cache[cache_key] = dur
                return dur
        except Exception:
            pass
    return DEFAULT_VIDEO_DURATION_SEC


def _load_sidecar_stats(match_id: uuid.UUID) -> dict:
    path = DUMPS_DIR / str(match_id) / "_stats.json"
    if not path.is_file():
        return {}
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_goal_events_from_dump(dump_path: Path) -> List[Dict[str, Any]]:
    """Return goal events with simulation step indices from a GFR pickle dump."""
    prev: Optional[List[int]] = None
    goals: List[Dict[str, Any]] = []
    with open(dump_path, "rb") as f:
        step_idx = 0
        while True:
            try:
                frame = pickle.load(f)
            except EOFError:
                break

            obs = frame
            if isinstance(frame, dict) and "observation" in frame:
                obs = frame["observation"]
            if isinstance(obs, (list, tuple)) and obs:
                obs = obs[0]

            score = obs.get("score") if isinstance(obs, dict) else None
            if score is not None:
                current = [int(score[0]), int(score[1])]
                if prev is not None and current != prev:
                    if current[0] > prev[0]:
                        side = "home"
                    elif current[1] > prev[1]:
                        side = "away"
                    else:
                        side = "home"
                    goals.append(
                        {
                            "side": side,
                            "step": step_idx,
                            "home_score": current[0],
                            "away_score": current[1],
                        }
                    )
                prev = current
            step_idx += 1
    return goals


def _steps_to_video_sec(step: int, total_steps: int, duration_sec: float) -> float:
    if total_steps <= 0:
        return 0.0
    return round((step / total_steps) * duration_sec, 2)


def build_match_sync_payload(
    match_id: uuid.UUID,
    gfr_stats: Optional[dict] = None,
) -> Optional[Dict[str, Any]]:
    """Assemble goal timestamps and final stats for frontend video sync."""
    stats = dict(gfr_stats or {})
    sidecar = _load_sidecar_stats(match_id)
    for key, value in sidecar.items():
        stats.setdefault(key, value)

    home_goals = int(stats.get("home_goals") or stats.get("goals_home") or 0)
    away_goals = int(stats.get("away_goals") or stats.get("goals_away") or 0)
    total_steps = int(stats.get("total_steps") or stats.get("steps") or DEFAULT_TOTAL_STEPS)
    duration_sec = _resolve_video_duration_sec(match_id)

    goal_events: List[Dict[str, Any]] = []
    if isinstance(stats.get("goal_events"), list) and stats["goal_events"]:
        goal_events = list(stats["goal_events"])
    else:
        dump_path = _resolve_dump_path(match_id, stats)
        if dump_path:
            goal_events = parse_goal_events_from_dump(dump_path)

    for event in goal_events:
        if "video_sec" not in event:
            step = int(event.get("step", 0))
            event["video_sec"] = _steps_to_video_sec(step, total_steps, duration_sec)

    possession = stats.get("possession") or {}
    home_poss = float(possession.get("home_pct", 50.0))
    away_poss = float(possession.get("away_pct", 50.0))

    corners = int(stats.get("corners") or 0)
    free_kicks = int(stats.get("free_kicks") or 0)

    return {
        "video_duration_sec": duration_sec,
        "total_steps": total_steps,
        "goal_events": goal_events,
        "final_stats": {
            "home_goals": home_goals,
            "away_goals": away_goals,
            "score": stats.get("score") or f"{home_goals}-{away_goals}",
            "possession": {"home_pct": home_poss, "away_pct": away_poss},
            "corners": corners,
            "free_kicks": free_kicks,
            "shots_home": int(stats.get("shots_home") or home_goals + free_kicks),
            "shots_away": int(stats.get("shots_away") or away_goals + free_kicks),
            "fouls_home": int(stats.get("fouls_home") or free_kicks // 2),
            "fouls_away": int(stats.get("fouls_away") or max(0, free_kicks - free_kicks // 2)),
            "corners_home": int(stats.get("corners_home") or corners // 2),
            "corners_away": int(stats.get("corners_away") or max(0, corners - corners // 2)),
        },
    }
