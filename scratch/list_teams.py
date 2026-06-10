from utils.db import SessionLocal, Team
db = SessionLocal()
for t in db.query(Team).order_by(Team.team_name):
    print(t.team_name)
db.close()
