from utils.db import SessionLocal, Fixture, GfrDump, Team
db = SessionLocal()
completed = db.query(Fixture).filter(Fixture.status == 'completed').all()
print(f'Completed matches: {len(completed)}')
for f in completed:
    h = db.query(Team).filter(Team.team_id == f.home_team_id).first()
    a = db.query(Team).filter(Team.team_id == f.away_team_id).first()
    dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
    has_video = bool(dump and dump.video_url)
    result = (f.outcome or {}).get('result', '?')
    print(f'  GWK{f.gameweek} {h.team_name} {f.score} {a.team_name} | {result} | video={has_video}')
db.close()
