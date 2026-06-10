"""
Replace every team's squad with FC26 dataset rosters (keeps seasons/fixtures).

Run after clean_db.py if you want real players without wiping the whole DB:
    venv/bin/python3 scripts/reseed_players_from_fc26.py
"""
import sys
import uuid

sys.path.insert(0, "/home/Warta/projects/citybet_virtuals")

from utils.db import SessionLocal, Team, Player
from utils.seeder import generate_player_roster


def reseed_players():
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

            has_fc26 = any(p.get("player_face_url") for p in roster)
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
        print(f"[+] Reseeded {updated_teams} teams ({updated_players} players).")
        if fallback_teams:
            print(f"[!] {len(fallback_teams)} teams used random fallback (not in FC26 CSV):")
            for name in fallback_teams:
                print(f"    - {name}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    reseed_players()
