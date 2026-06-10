"""Reseed all team squads from FC26 CSV."""
import uuid

from utils.db import SessionLocal, Team, Player
from utils.seeder import generate_player_roster


def reseed_all_players() -> tuple:
    db = SessionLocal()
    updated_teams = 0
    updated_players = 0
    fallback_teams = []
    try:
        teams = db.query(Team).all()
        for team in teams:
            roster, squad_rating = generate_player_roster(
                team.team_name,
                team.team_rating or 3,
                team.league_name,
            )

            db.query(Player).filter(Player.team_id == team.team_id).delete(
                synchronize_session=False
            )

            has_fc26 = any(p.get("gfr_attributes", {}).get("fifa_player_id") for p in roster)
            if not has_fc26:
                fallback_teams.append(f"{team.league_name}: {team.team_name}")

            team.team_rating = squad_rating
            for p in roster:
                db.add(
                    Player(
                        player_id=uuid.uuid4(),
                        team_id=team.team_id,
                        player_name=p["player_name"],
                        role=p["role"],
                        player_position=p["player_position"],
                        player_rating=p["player_rating"],
                        age=p["age"],
                        tired_factor=0.0,
                        velocity=p["velocity"],
                        gfr_attributes=p["gfr_attributes"],
                        rewards=p["rewards"],
                        player_face_url=p.get("player_face_url"),
                    )
                )
                updated_players += 1
            updated_teams += 1

        db.commit()
        return updated_teams, updated_players, fallback_teams
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
