from utils.db import SessionLocal, Fixture, GfrDump, Team
from utils.virtual_schedule import match_has_video
from pathlib import Path

db = SessionLocal()
live = db.query(Fixture).filter(Fixture.status=='live').all()
preparing = db.query(Fixture).filter(Fixture.status=='preparing').all()
completed = db.query(Fixture).filter(Fixture.status=='completed').all()
print('LIVE:', len(live))
print('PREPARING:', len(preparing))
print('COMPLETED:', len(completed))

# Check completed with videos
completed_with_video = []
for f in completed:
    dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
    has_v = match_has_video(dump, f.match_id)
    if has_v:
        completed_with_video.append(f)

print('COMPLETED WITH VIDEO:', len(completed_with_video))

for f in live:
    dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
    has_v = match_has_video(dump, f.match_id)
    print('LIVE match:', f.match_id, 'has_video:', has_v, 'dump_url:', dump.video_url if dump else None)

print()
print('Oldest 5 completed with video:')
for f in completed_with_video[:5]:
    h = db.query(Team).filter(Team.team_id == f.home_team_id).first()
    a = db.query(Team).filter(Team.team_id == f.away_team_id).first()
    print(f'  {f.match_id} | {h.team_name if h else "?"} vs {a.team_name if a else "?"} | score:{f.score}')

db.close()
