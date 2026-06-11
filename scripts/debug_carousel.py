#!/usr/bin/env python3
import sys
sys.path.insert(0, ".")

from utils.db import SessionLocal, Fixture
from utils.carousel_schedule import build_carousel_response

db = SessionLocal()
prep = db.query(Fixture).filter(Fixture.status == "preparing").limit(5).all()
print("DB preparing sample:")
for f in prep:
    print(f.match_id, f.gameweek, (f.predictions or {}).get("_scheduled_start_at"))

c = build_carousel_response(db)
print("\ncarousel first 6:")
for it in c["items"][:6]:
    print(it["carousel_step"], it["status"], it.get("is_next"), it["gameweek"], it["league_name"][:10], (it.get("home_team") or {}).get("name"))
db.close()
