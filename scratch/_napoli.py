from utils.db import SessionLocal, Fixture, GfrDump, Team
from utils.virtual_schedule import match_has_video, resolve_video_file

db = SessionLocal()
for f in db.query(Fixture).filter(Fixture.status == "live").all():
    home = db.query(Team).filter(Team.team_id == f.home_team_id).first()
    away = db.query(Team).filter(Team.team_id == f.away_team_id).first()
    if not home or not away:
        continue
    names = f"{home.team_name} vs {away.team_name}".lower()
    if "napoli" in names and "verona" in names:
        d = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
        steps = 0
        if d and d.gfr_stats:
            steps = int(d.gfr_stats.get("total_steps") or d.gfr_stats.get("steps") or 0)
        vid = resolve_video_file(f.match_id, d)
        print("match_id", f.match_id)
        print("status", f.status, "gw", f.gameweek, "score", f.score)
        print("steps", steps)
        print("has_video", match_has_video(d, f.match_id))
        print("video_url", d.video_url if d else None)
        print("resolved", vid)
        print("home/away", home.team_name, away.team_name)

# also list all live
print("--- all live ---")
for f in db.query(Fixture).filter(Fixture.status == "live").all():
    home = db.query(Team).filter(Team.team_id == f.home_team_id).first()
    away = db.query(Team).filter(Team.team_id == f.away_team_id).first()
    d = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
    print(f.match_id, home.team_name if home else "?", "vs", away.team_name if away else "?",
          "has_video", match_has_video(d, f.match_id) if d else False)
db.close()
