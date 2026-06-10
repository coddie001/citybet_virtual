"""
Assign aesthetic fixture preview images when fixtures are generated.
Uses local example assets and stable public football imagery URLs.
"""
import hashlib
import os
import re
from typing import Optional, Tuple

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")

# Served locally via FastAPI static mount (see main.py).
LOCAL_FIXTURE_IMAGES = [
    "/static/fixture-imgs/HIdxJdRXgAAVkvJ.jpg",
    "/static/fixture-imgs/P2024-04-14-Liverpool_Crystal_Palace-54-600x400.jpg",
    "/static/fixture-imgs/2267.avif",
]

# Curated stable web URLs depicting match action / stadium atmosphere.
WEB_FIXTURE_IMAGES = [
    "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&q=80",
    "https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d?w=800&q=80",
    "https://images.unsplash.com/photo-1522778119026-d647f0596c20?w=800&q=80",
    "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=800&q=80",
    "https://images.unsplash.com/photo-1517466787929-bc90951d0974?w=800&q=80",
    "https://images.unsplash.com/photo-1529900748604-07564a03e7a6?w=800&q=80",
    "https://images.unsplash.com/photo-1560272564-c83b66b1ad12?w=800&q=80",
    "https://images.unsplash.com/photo-1459865269677-1af656c836fb?w=800&q=80",
    "https://images.unsplash.com/photo-1489944440615-453fc3b6a9a0?w=800&q=80",
    "https://images.unsplash.com/photo-1522778119026-d647f0596c20?w=800&q=80",
    "https://images.unsplash.com/photo-1575361204480-aadea25e6e68?w=800&q=80",
    "https://images.unsplash.com/photo-1551958219-ac6ca609eea3?w=800&q=80",
]

IMAGE_POOL = LOCAL_FIXTURE_IMAGES + WEB_FIXTURE_IMAGES


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _abs_url(path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    return f"{API_BASE_URL}{path}"


def _filename_team_match(filename: str, home_name: str, away_name: str) -> bool:
    """True when a local example filename references both clubs."""
    slug_home = _slug(home_name)
    slug_away = _slug(away_name)
    fname = filename.lower()
    return slug_home in fname and slug_away in fname


def _team_specific_local_url(home_name: str, away_name: str) -> Optional[str]:
    for path in LOCAL_FIXTURE_IMAGES:
        if _filename_team_match(path, home_name, away_name):
            return _abs_url(path)
    return None


def pick_fixture_image_url(
    home_team_name: str,
    away_team_name: str,
    home_team_id,
    away_team_id,
    gameweek: int,
) -> str:
    """
    Pick a deterministic preview image for a fixture.
    Prefers local examples that mention both teams, otherwise hashes
    the pairing to rotate through the curated pool.
    """
    specific = _team_specific_local_url(home_team_name, away_team_name)
    if specific:
        return specific

    key = f"{home_team_id}:{away_team_id}:{gameweek}"
    idx = int(hashlib.md5(key.encode()).hexdigest(), 16) % len(IMAGE_POOL)
    return _abs_url(IMAGE_POOL[idx])
