"""
Find and cache fixture preview images — modern on-pitch action / celebrations.

Reference style (see front_end/static/img/fixture_imgs/):
  - Real players in match kits on the pitch
  - Goal celebrations or live match action (not stadium exteriors / backstage)
  - Recent photography (2023–2025)

Priority: DuckDuckGo (sports hosts) → Wikimedia → Openverse.
Downloads locally for stable serving via /static/fixture-imgs/cache/.
"""
import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urlparse

import requests

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "front_end" / "static" / "img" / "fixture_imgs" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
USER_AGENT = "CityBetVirtuals/1.0 (fixture previews; educational)"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})

CACHE_VERSION = 2

PREFERRED_HOSTS = (
    "skysports.com",
    "goal.com",
    "fourfourtwo.com",
    "theguardian.com",
    "bbc.co.uk",
    "reuters.com",
    "gettyimages.com",
    "alamy.com",
    "eurosport.com",
    "espn.com",
    "marca.com",
    "as.com",
    "sportbible.com",
    "90min.com",
    "wikimedia.org",
    "wikipedia.org",
)

DEAD_HOSTS = ("unsplash.com", "images.unsplash.com", "placeholder.com", "via.placeholder.com")

GOOD_KEYWORDS = (
    "player", "players", "goal", "celebrat", "score", "action", "match", "kick",
    "tackle", "shoot", "header", "save", "kit", "uniform", "jersey", "pitch",
    "premier", "laliga", "serie", "bundesliga", "football", "soccer", "striker",
    "midfield", "defender", "2024", "2025", "2023",
)

BAD_KEYWORDS = (
    "stadium exterior", "stadium aerial", "training ground", "press conference",
    "manager", "coach", "backstage", "tunnel", "dressing room", "logo", "crest",
    "badge only", "fans only", "crowd only", "empty stadium", "architectural",
    "club shop", "museum", "headshot portrait", "signing", "transfer", "boardroom",
    "illustration", "cartoon", "vector", "wallpaper", "banner", "flag only",
)

MIN_BYTES = 12_000
MAX_BYTES = 4_000_000
MIN_WIDTH = 500
DOWNLOAD_TIMEOUT = 15


def _cache_key(home: str, away: str) -> str:
    raw = f"{home.lower()}|{away.lower()}"
    return hashlib.md5(raw.encode()).hexdigest()


def _meta_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def _read_cache_meta(key: str) -> dict:
    path = _meta_path(key)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_cache_meta(key: str, meta: dict) -> None:
    meta["version"] = CACHE_VERSION
    _meta_path(key).write_text(json.dumps(meta), encoding="utf-8")


def _local_url(filename: str) -> str:
    return f"{API_BASE_URL}/static/fixture-imgs/cache/{filename}"


def _is_preferred(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(p in host for p in PREFERRED_HOSTS)


def _is_dead(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(d in host for d in DEAD_HOSTS)


def _score_text(text: str) -> float:
    t = text.lower()
    score = 0.0
    for kw in GOOD_KEYWORDS:
        if kw in t:
            score += 1.5
    for kw in BAD_KEYWORDS:
        if kw in t:
            score -= 4.0
    return score


def _score_candidate(cand: dict) -> float:
    url = cand.get("url", "")
    title = cand.get("title", "") or ""
    source = cand.get("source", "") or ""
    w, h = cand.get("width") or 0, cand.get("height") or 0

    text_score = _score_text(f"{url} {title} {source}")
    host_bonus = 3.0 if _is_preferred(url) else 0.0
    landscape = 2.0 if w >= h and w >= MIN_WIDTH else (-2.0 if h > w * 1.2 else 0.0)
    size_bonus = min(max(w, h), 1200) / 600.0
    ddg_bonus = 1.0 if cand.get("engine") == "ddg" else 0.0
    return text_score + host_bonus + landscape + size_bonus + ddg_bonus


def _rank_candidates(candidates: list) -> list:
    return sorted(candidates, key=_score_candidate, reverse=True)


def _search_wikimedia(query: str, limit: int = 10) -> list:
    candidates = []
    try:
        resp = SESSION.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": limit,
                "gsrnamespace": 6,
                "prop": "imageinfo",
                "iiprop": "url|size|mime",
                "iiurlwidth": 900,
                "format": "json",
            },
            timeout=12,
        )
        if resp.status_code != 200:
            return []
        pages = resp.json().get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title", "")
            for info in page.get("imageinfo", []):
                url = info.get("thumburl") or info.get("url")
                mime = info.get("mime", "")
                if url and "image" in mime and not _is_dead(url):
                    candidates.append({
                        "url": url,
                        "title": title,
                        "width": info.get("thumbwidth") or info.get("width") or 0,
                        "height": info.get("thumbheight") or info.get("height") or 0,
                        "source": "wikimedia",
                        "engine": "wikimedia",
                    })
    except Exception as e:
        log.debug("Wikimedia search failed: %s", e)
    return candidates


def _search_openverse(query: str, limit: int = 8) -> list:
    candidates = []
    try:
        resp = SESSION.get(
            "https://api.openverse.org/v1/images/",
            params={"q": query, "page_size": limit, "license_type": "commercial,modification"},
            timeout=12,
        )
        if resp.status_code != 200:
            return []
        for item in resp.json().get("results", []):
            url = item.get("url") or item.get("thumbnail")
            if url and not _is_dead(url):
                candidates.append({
                    "url": url,
                    "title": item.get("title") or "",
                    "width": item.get("width") or 0,
                    "height": item.get("height") or 0,
                    "source": item.get("source") or "openverse",
                    "engine": "openverse",
                })
    except Exception as e:
        log.debug("Openverse search failed: %s", e)
    return candidates


def _search_ddg(query: str, max_results: int = 12) -> list:
    candidates = []
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            for item in ddgs.images(query, max_results=max_results, safesearch="moderate"):
                url = item.get("image") or item.get("thumbnail")
                if url and url.startswith("http") and not _is_dead(url):
                    candidates.append({
                        "url": url,
                        "title": item.get("title") or "",
                        "width": item.get("width") or 0,
                        "height": item.get("height") or 0,
                        "source": item.get("source") or "ddg",
                        "engine": "ddg",
                    })
    except Exception as e:
        log.debug("DDG search failed for '%s': %s", query, e)
    return candidates


def _short_team(name: str) -> str:
    """Common short names for better image search hits."""
    aliases = {
        "tottenham hotspur": "Tottenham",
        "manchester united": "Man United",
        "manchester city": "Man City",
        "newcastle united": "Newcastle",
        "west ham united": "West Ham",
        "wolverhampton wanderers": "Wolves",
        "brighton & hove albion": "Brighton",
        "nottingham forest": "Nottm Forest",
        "crystal palace": "Crystal Palace",
        "leicester city": "Leicester",
        "aston villa": "Aston Villa",
    }
    low = name.lower().strip()
    return aliases.get(low, name)


def _search_images(home: str, away: str) -> list:
    h, a = _short_team(home), _short_team(away)
    queries = [
        f'"{h} vs {a}" football match 2024 players action photo',
        f'"{h} vs {a}" football goal celebration 2024',
        f"{h} vs {a} premier league match action players kit",
        f"{h} {a} football match on pitch players uniform",
        f"{h} goal celebration football kit 2024",
        f"{a} goal celebration football kit 2024",
    ]
    seen = set()
    candidates = []

    for q in queries[:3]:
        for item in _search_ddg(q, max_results=10):
            if item["url"] not in seen:
                seen.add(item["url"])
                candidates.append(item)
        time.sleep(1.0)

    ranked = _rank_candidates(candidates)
    if ranked and _score_candidate(ranked[0]) >= 4.0:
        return ranked

    for q in queries[3:]:
        for source_fn in (_search_wikimedia, _search_openverse):
            for item in source_fn(q):
                if item["url"] not in seen:
                    seen.add(item["url"])
                    candidates.append(item)
        time.sleep(0.4)

    return _rank_candidates(candidates)


def _download_image(url: str, dest: Path) -> bool:
    try:
        resp = SESSION.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
        if resp.status_code != 200:
            return False
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return False

        data = resp.content
        if not (MIN_BYTES <= len(data) <= MAX_BYTES):
            return False

        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"

        dest = dest.with_suffix(ext)
        dest.write_bytes(data)
        return True
    except Exception as e:
        log.debug("Download failed %s: %s", url, e)
        return False


def cached_fixture_image_path(home_team: str, away_team: str) -> Optional[Path]:
    key = _cache_key(home_team, away_team)
    meta = _read_cache_meta(key)
    if meta.get("version") != CACHE_VERSION:
        return None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        path = CACHE_DIR / f"{key}{ext}"
        if path.exists() and path.stat().st_size >= MIN_BYTES:
            return path
    return None


def resolve_fixture_image_url(
    home_team: str,
    away_team: str,
    *,
    force_search: bool = False,
) -> Optional[str]:
    key = _cache_key(home_team, away_team)
    existing = cached_fixture_image_path(home_team, away_team)
    if existing and not force_search:
        return _local_url(existing.name)

    if force_search:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            stale = CACHE_DIR / f"{key}{ext}"
            stale.unlink(missing_ok=True)
        _meta_path(key).unlink(missing_ok=True)

    candidates = _search_images(home_team, away_team)
    if not candidates:
        return None

    for cand in _rank_candidates(candidates):
        if _score_candidate(cand) < 2.0:
            continue
        dest = CACHE_DIR / key
        if _download_image(cand["url"], dest):
            written = None
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                p = CACHE_DIR / f"{key}{ext}"
                if p.is_file():
                    written = p
                    break
            if written:
                _write_cache_meta(key, {
                    "home": home_team,
                    "away": away_team,
                    "source": cand.get("source"),
                    "query_score": _score_candidate(cand),
                    "url": cand["url"],
                })
                log.info("Cached %s vs %s ← %s (score=%.1f)", home_team, away_team,
                         cand.get("source"), _score_candidate(cand))
                return _local_url(written.name)
    return None


def is_stale_image_url(url: Optional[str]) -> bool:
    if not url:
        return True
    if _is_dead(url):
        return True
    if "unsplash.com" in url.lower():
        return True
    if "/static/fixture-imgs/cache/" in url:
        return False
    if url.startswith(API_BASE_URL) and "/static/fixture-imgs/cache/" in url:
        return False
    if url.startswith("/static/fixture-imgs/cache/"):
        return False
    if "/static/fixture-imgs/" in url and "/cache/" not in url:
        return False
    if url.startswith(("http://", "https://")):
        return True
    return False


def is_cache_stale(home_team: str, away_team: str) -> bool:
    """True when no v2 cached image exists for this fixture."""
    return cached_fixture_image_path(home_team, away_team) is None
