#!/usr/bin/env python3
"""Apply local team_fix_imgs to all fixtures in the database."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.db import SessionLocal, Fixture, Team
from utils.team_fixture_images import fixture_image_url, reload_index


def main():
    n = reload_index()
    print(f"Indexed {n} team images")
    db = SessionLocal()
    updated = 0
    try:
        fixtures = db.query(Fixture).all()
        for f in fixtures:
            home = db.query(Team.team_name).filter(Team.team_id == f.home_team_id).scalar()
            away = db.query(Team.team_name).filter(Team.team_id == f.away_team_id).scalar()
            if not home or not away:
                continue
            url = fixture_image_url(home, away, f.home_team_id, f.away_team_id)
            if f.fixture_image_url != url:
                f.fixture_image_url = url
                updated += 1
        db.commit()
        print(f"Updated {updated} fixture image URLs")
    finally:
        db.close()


if __name__ == "__main__":
    main()
