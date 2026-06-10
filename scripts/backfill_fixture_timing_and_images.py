"""
Backfill show_at_ms and fixture_image_url on fixtures that were created
before the timing/image columns existed. Run once after migration.
"""
import sys

sys.path.insert(0, "/home/Warta/projects/citybet_virtuals")

from utils.db import SessionLocal, Fixture, Team, Season
from utils.fixture_timing import assign_show_at_ms
from utils.fixture_assets import pick_fixture_image_url


def backfill():
    db = SessionLocal()
    try:
        seasons = db.query(Season).all()
        updated = 0
        for season in seasons:
            fixtures = (
                db.query(Fixture)
                .filter(Fixture.season_id == season.season_id)
                .order_by(Fixture.gameweek.asc(), Fixture.game_date.asc(), Fixture.game_time.asc())
                .all()
            )
            team_cache = {}
            for idx, fixture in enumerate(fixtures):
                if fixture.show_at_ms is None or fixture.show_at_ms == 0:
                    fixture.show_at_ms = assign_show_at_ms(idx)
                    updated += 1
                if not fixture.fixture_image_url:
                    for tid in (fixture.home_team_id, fixture.away_team_id):
                        if tid not in team_cache:
                            t = db.query(Team).filter(Team.team_id == tid).first()
                            team_cache[tid] = t.team_name if t else "Unknown"
                    fixture.fixture_image_url = pick_fixture_image_url(
                        team_cache[fixture.home_team_id],
                        team_cache[fixture.away_team_id],
                        fixture.home_team_id,
                        fixture.away_team_id,
                        fixture.gameweek,
                    )
                    updated += 1
            db.commit()
        print(f"[+] Backfill complete. Fields updated on {updated} fixture records.")
    finally:
        db.close()


if __name__ == "__main__":
    backfill()
