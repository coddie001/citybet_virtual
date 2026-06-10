"""Quick sanity check: FC26 roster coverage for all LEAGUE_TEAMS."""
from utils.seeder import LEAGUE_TEAMS
from utils.fc26_loader import build_roster_from_fc26

fc26_count = 0
fallback_count = 0

for league, teams in LEAGUE_TEAMS.items():
    for team_name, *_ in teams:
        roster, rating = build_roster_from_fc26(league, team_name)
        if roster:
            fc26_count += 1
            faces = sum(1 for p in roster if p.get("player_face_url"))
            sample = roster[0]["player_name"]
            print(f"OK  {league:16} {team_name:28} rating={rating} faces={faces}/11  e.g. {sample}")
        else:
            fallback_count += 1
            print(f"FB  {league:16} {team_name:28} (random fallback at seed)")

print(f"\nFC26: {fc26_count}, fallback: {fallback_count}, total: {fc26_count + fallback_count}")
