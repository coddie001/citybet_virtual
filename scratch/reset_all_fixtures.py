"""
Reset all previously settled fixtures back to 'upcoming' so they get
re-simulated by the fixed actor vs actor engine.
"""
import sys
sys.path.insert(0, "/home/Warta/projects/citybet_virtuals")

from utils.db import SessionLocal, Fixture

db = SessionLocal()

# Count current statuses
from sqlalchemy import func
status_counts = db.query(Fixture.status, func.count()).group_by(Fixture.status).all()
print("Current fixture statuses:")
for status, count in status_counts:
    print(f"  {status}: {count}")

# Reset ALL non-upcoming back to upcoming so they get re-simulated fresh
to_reset = db.query(Fixture).filter(Fixture.status != 'upcoming').all()
print(f"\nResetting {len(to_reset)} fixtures back to 'upcoming'...")

for f in to_reset:
    f.status = 'upcoming'
    f.home_score = None
    f.away_score = None
    f.result = None

db.commit()
db.close()
print("Done. All fixtures are now queued for fresh simulation.")
