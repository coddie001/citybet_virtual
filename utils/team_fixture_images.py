"""
Map locally curated team images (team_fix_imgs/) to database team names.
Falls back to default_image for unmapped teams or problematic assets.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEAM_IMG_DIR = PROJECT_ROOT / "front_end" / "static" / "img" / "team_fix_imgs"
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
STATIC_PREFIX = "/static/team-fix-imgs"

MIN_FILE_BYTES = 15 * 1024
DEFAULT_IMAGE_NAME = "default_image.webp"
DEFAULT_STATIC_PATH = f"{STATIC_PREFIX}/{DEFAULT_IMAGE_NAME}"

EXT_PRIORITY = {".jpg": 0, ".jpeg": 1, ".webp": 2, ".png": 3, ".avif": 4}
SKIP_STEMS = {"default_image", "default"}

FILENAME_ALIASES: Dict[str, str] = {
    "ac_millan": "AC Milan",
    "ac_milan": "AC Milan",
    "alaves": "Alaves",
    "arsenal": "Arsenal",
    "aston_villa": "Aston Villa",
    "atalanta": "Atalanta",
    "athletic_club": "Athletic Bilbao",
    "athletico_madrid": "Atletico Madrid",
    "barceona": "Barcelona",
    "barcelona": "Barcelona",
    "bayer_leverkusen": "Bayer Leverkusen",
    "bayern_munich": "Bayern Munich",
    "bologna": "Bologna",
    "bologna_fc": "Bologna",
    "borussia_dortmund": "Borussia Dortmund",
    "borussia_m_gladbach": "Borussia M'gladbach",
    "bournemouh": "Bournemouth",
    "bournemouth": "Bournemouth",
    "brentford": "Brentford",
    "brighton": "Brighton & Hove Albion",
    "cagliari": "Cagliari",
    "celta_vigo": "Celta Vigo",
    "chelsea": "Chelsea",
    "como": "Como",
    "crystal_palace": "Crystal Palace",
    "eintracht_frankfurt": "Eintracht Frankfurt",
    "empoli": "Empoli",
    "espanyol": "Espanyol",
    "everton": "Everton",
    "fc_augsburg": "FC Augsburg",
    "florentina": "Fiorentina",
    "fulham": "Fulham",
    "geona_fc": "Genoa",
    "genoa": "Genoa",
    "getafe": "Getafe",
    "girona": "Girona",
    "heidenheim": "Heidenheim",
    "holstein_kiel": "Holstein Kiel",
    "intermillan_fc": "Inter Milan",
    "inter_milan": "Inter Milan",
    "ipswitch": "Ipswich Town",
    "juventus": "Juventus",
    "las_palmas": "Las Palmas",
    "lazio": "Lazio",
    "lecce": "Lecce",
    "leganes": "Leganes",
    "leicester": "Leicester City",
    "liverpool": "Liverpool",
    "mainz_05": "Mainz 05",
    "mallorca": "Mallorca",
    "man_city": "Manchester City",
    "manchester_utd": "Manchester United",
    "manchester_united": "Manchester United",
    "monza": "Monza",
    "monza_fc": "Monza",
    "napoli": "Napoli",
    "newcastle": "Newcastle United",
    "notthingham_forest": "Nottingham Forest",
    "nottingham_forest": "Nottingham Forest",
    "osasuna": "Osasuna",
    "parma": "Parma",
    "parma_fc": "Parma",
    "rayo_vallecano": "Rayo Vallecano",
    "rb_leipzig": "RB Leipzig",
    "real_betis": "Real Betis",
    "real_madrid": "Real Madrid",
    "real_sociedad": "Real Sociedad",
    "roma": "Roma",
    "sc_freiburg": "SC Freiburg",
    "sevilla": "Sevilla",
    "southhampton": "Southampton",
    "southampton": "Southampton",
    "st_pauli": "St. Pauli",
    "torino": "Torino",
    "tottenham_fc": "Tottenham Hotspur",
    "tottenham_hotspur": "Tottenham Hotspur",
    "tsg_hoffenheim": "TSG Hoffenheim",
    "udinesse_fc": "Udinese",
    "udinese": "Udinese",
    "union_berlin": "Union Berlin",
    "valencia_cf": "Valencia",
    "valencia": "Valencia",
    "valladolid": "Valladolid",
    "venezia_fc": "Venezia",
    "venezia": "Venezia",
    "verona": "Verona",
    "vfb_stuttgart": "VfB Stuttgart",
    "vfl_bochum": "VfL Bochum",
    "vfl_wolfsburg": "VfL Wolfsburg",
    "villareal": "Villarreal",
    "villarreal": "Villarreal",
    "werder_bremen": "Werder Bremen",
    "westham": "West Ham United",
    "west_ham_united": "West Ham United",
    "wolves": "Wolverhampton Wanderers",
    "wolverhampton_wanderers": "Wolverhampton Wanderers",
}

_TEAM_INDEX: Optional[Dict[str, str]] = None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _stem_key(path: Path) -> str:
    stem = re.sub(r"_\d+$", "", path.stem)
    return _slug(stem)


def _is_usable_image(path: Path) -> bool:
    """Reject tiny thumbnails and AVIF (limited browser support in carousel)."""
    try:
        size = path.stat().st_size
    except OSError:
        return False
    if size < MIN_FILE_BYTES:
        return False
    if path.suffix.lower() == ".avif":
        return False
    return True


def _score_file(path: Path) -> tuple:
    """Lower is better. Prefer non-numbered suffix, jpg/webp, moderate size."""
    has_num_suffix = 1 if re.search(r"_\d+$", path.stem) else 0
    ext_rank = EXT_PRIORITY.get(path.suffix.lower(), 9)
    size = path.stat().st_size
    size_penalty = 0 if 20_000 <= size <= 800_000 else 1
    return (has_num_suffix, ext_rank, size_penalty, size)


def _static_path_for(path: Path) -> str:
    return f"{STATIC_PREFIX}/{path.name}"


def _default_image_path() -> Optional[Path]:
    for name in (DEFAULT_IMAGE_NAME, "default_image.png", "default_image.jpg"):
        candidate = TEAM_IMG_DIR / name
        if candidate.is_file():
            return candidate
    return None


def build_team_image_index() -> Dict[str, str]:
    """team_name → static URL path."""
    if not TEAM_IMG_DIR.is_dir():
        return {}

    default_path = _default_image_path()
    default_static = _static_path_for(default_path) if default_path else DEFAULT_STATIC_PATH

    buckets: Dict[str, list[Path]] = {}
    for path in TEAM_IMG_DIR.iterdir():
        if not path.is_file() or path.name.endswith(":Zone.Identifier"):
            continue
        if path.suffix.lower() not in EXT_PRIORITY:
            continue
        key = _stem_key(path)
        if key in SKIP_STEMS:
            continue
        team = FILENAME_ALIASES.get(key)
        if not team:
            continue
        buckets.setdefault(team, []).append(path)

    index: Dict[str, str] = {}
    for team, files in buckets.items():
        usable = [f for f in files if _is_usable_image(f)]
        if usable:
            best = sorted(usable, key=_score_file)[0]
            index[team] = _static_path_for(best)
        else:
            index[team] = default_static

    return index


def get_team_image_index() -> Dict[str, str]:
    global _TEAM_INDEX
    if _TEAM_INDEX is None:
        _TEAM_INDEX = build_team_image_index()
    return _TEAM_INDEX


def team_image_url(team_name: str) -> Optional[str]:
    rel = get_team_image_index().get(team_name)
    if not rel:
        return None
    return f"{API_BASE_URL}{rel}"


def fixture_image_url(
    home_team: str,
    away_team: str,
    home_id,
    away_id,
) -> str:
    for team in (home_team, away_team):
        url = team_image_url(team)
        if url:
            return url

    index = get_team_image_index()
    if index:
        names = sorted(index.keys())
        key = f"{home_id}:{away_id}"
        pick = names[int(hashlib.md5(key.encode()).hexdigest(), 16) % len(names)]
        return f"{API_BASE_URL}{index[pick]}"

    return f"{API_BASE_URL}{DEFAULT_STATIC_PATH}"


def reload_index() -> int:
    global _TEAM_INDEX
    _TEAM_INDEX = build_team_image_index()
    return len(_TEAM_INDEX)
