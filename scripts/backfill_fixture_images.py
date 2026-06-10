#!/usr/bin/env python3
"""
Refresh stale fixture preview images (unsplash / dead links) via image search.

Usage:
    venv/bin/python3 scripts/backfill_fixture_images.py
    venv/bin/python3 scripts/backfill_fixture_images.py --limit 20
    venv/bin/python3 scripts/backfill_fixture_images.py --upcoming-only
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.db import SessionLocal, Fixture, Team
from utils.fixture_assets import is_stale_image_url, refresh_fixture_image


def backfill(limit: int = 30, upcoming_only: bool = False) -> int:
    db = SessionLocal()
    updated = 0
    try:
        q = db.query(Fixture)
        if upcoming_only:
            q = q.filter(Fixture.status == "upcoming")
        fixtures = q.order_by(Fixture.show_at_ms.asc()).all()

        for f in fixtures:
            if updated >= limit:
                break
            if not is_stale_image_url(f.fixture_image_url):
                continue

            home = db.query(Team.team_name).filter(Team.team_id == f.home_team_id).scalar()
            away = db.query(Team.team_name).filter(Team.team_id == f.away_team_id).scalar()
            if not home or not away:
                continue

            new_url = refresh_fixture_image(home, away, f.fixture_image_url, force=True)
            if new_url and new_url != f.fixture_image_url:
                f.fixture_image_url = new_url
                updated += 1
                print(f"[+] {home} vs {away} → {new_url}")
            time.sleep(0.6)

        if updated:
            db.commit()
        print(f"Done — updated {updated} fixture images.")
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--upcoming-only", action="store_true")
    args = parser.parse_args()
    backfill(limit=args.limit, upcoming_only=args.upcoming_only)
