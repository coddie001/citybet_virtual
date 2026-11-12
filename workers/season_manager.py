"""
Season lifecycle management worker — handles season end, table computation,
and automated rollover to next season.
"""

import os
import sys
import uuid
from sqlalchemy.orm import Session

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.db import SessionLocal, Season, Team, Player, Fixture
from utils.league_table import persist_league_table


def compute_league_table(db: Session, season_id: uuid.UUID):
    """Persist final league ranks and end-of-season stats."""
    persist_league_table(db, season_id)
    rows = db.query(Team).filter(Team.season_id == season_id).order_by(Team.league_rank).all()
    for team in rows:
        live = (team.team_data or {}).get("live_table", {})
        if live:
            if team.team_data:
                team.team_data["end_of_season_stats"] = live
    db.commit()
    print(f"[+] Computed league rankings for Season {season_id}.")


def start_next_season(db: Session, completed_season: Season):
    """
    Creates a new season, copies teams and starting rosters,
    and rolls forward the season loop.
    """
    orig_name = completed_season.tournament_name
    name_parts = orig_name.split(" ")
    try:
        year = int(name_parts[-1])
        new_year = year + 1
        new_name = " ".join(name_parts[:-1]) + f" {new_year}"
    except (ValueError, IndexError):
        new_name = f"{orig_name} (Next)"

    new_season_uuid = uuid.uuid4()
    new_season = Season(
        season_id=new_season_uuid,
        tournament_id=completed_season.tournament_id,
        tournament_name=new_name,
        season_status="active",
        cum_teams=completed_season.cum_teams,
        cum_gwk=completed_season.cum_gwk,
        current_gwk=1,
    )
    db.add(new_season)
    db.commit()
    print(f"[*] Started new season loop: '{new_name}' (Season ID: {new_season_uuid})")

    old_teams = db.query(Team).filter(Team.season_id == completed_season.season_id).all()
    team_id_map = {}

    for t in old_teams:
        new_team_uuid = uuid.uuid4()
        new_team = Team(
            team_id=new_team_uuid,
            season_id=new_season_uuid,
            league_name=t.league_name,
            team_name=t.team_name,
            league_rank=1,
            team_rating=t.team_rating,
            team_data=t.team_data.copy() if t.team_data else {},
        )
        db.add(new_team)
        db.commit()
        team_id_map[t.team_id] = new_team_uuid

        old_players = db.query(Player).filter(Player.team_id == t.team_id).all()
        for p in old_players:
            new_player = Player(
                player_id=uuid.uuid4(),
                team_id=new_team_uuid,
                player_name=p.player_name,
                role=p.role,
                player_position=p.player_position,
                player_rating=p.player_rating,
                age=p.age,
                tired_factor=0.0,
                velocity=p.velocity,
                gfr_attributes=p.gfr_attributes,
                rewards=p.rewards,
                player_face_url=p.player_face_url,
                goals=0,
                assists=0,
                appearances=0,
            )
            db.add(new_player)
        db.commit()

    print(f"  [+] Transferred all {len(old_teams)} teams and rosters to the new season.")

    from workers.fixture_generator import generate_fixtures_for_season
    generate_fixtures_for_season(db, new_season)


def check_and_transition_seasons():
    """Scan active seasons and start new ones if all gameweeks completed."""
    db = SessionLocal()
    try:
        active_seasons = db.query(Season).filter(Season.season_status == "active").all()
        for season in active_seasons:
            total_fixtures = db.query(Fixture).filter(Fixture.season_id == season.season_id).count()
            completed_fixtures = db.query(Fixture).filter(
                Fixture.season_id == season.season_id,
                Fixture.status == "completed"
            ).count()

            if total_fixtures > 0 and completed_fixtures == total_fixtures:
                print(f"[!] Season '{season.tournament_name}' is fully completed ({completed_fixtures}/{total_fixtures} matches).")
                compute_league_table(db, season.season_id)
                season.season_status = "completed"
                db.commit()
                start_next_season(db, season)
    finally:
        db.close()


if __name__ == "__main__":
    check_and_transition_seasons()
