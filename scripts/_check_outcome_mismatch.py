from utils.db import SessionLocal, Fixture

db = SessionLocal()
mismatch = (
    db.query(Fixture)
    .filter(Fixture.outcome.isnot(None), Fixture.status != "completed")
    .count()
)
print(f"fixtures with outcome but status != completed: {mismatch}")
for status in ("upcoming", "live", "error", "completed"):
    n = db.query(Fixture).filter(Fixture.status == status, Fixture.outcome.isnot(None)).count()
    print(f"  outcome set + status={status}: {n}")
db.close()
