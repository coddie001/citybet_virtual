#!/usr/bin/env python3
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.league_table import build_league_table, build_team_form
from utils import team_fixture_images as tfi
from utils.db import SessionLocal, Season

print("build_team_form:", inspect.signature(build_team_form))
print("build_league_table:", inspect.signature(build_league_table))
print("team_fixture_images exports:")
for name in sorted(dir(tfi)):
    if name.startswith("_"):
        continue
    obj = getattr(tfi, name)
    if callable(obj):
        try:
            print(f"  {name}{inspect.signature(obj)}")
        except (TypeError, ValueError):
            print(f"  {name}()")

db = SessionLocal()
try:
    s = db.query(Season).first()
    if s:
        tbl = build_league_table(db, s.season_id)
        if tbl:
            print("sample row keys:", list(tbl[0].keys()))
            print("sample last_5:", tbl[0].get("last_5"))
except Exception as e:
    print("db err:", e)
finally:
    db.close()
