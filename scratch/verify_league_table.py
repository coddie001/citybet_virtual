#!/usr/bin/env python3
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.db import Season, SessionLocal
from utils import league_table as lt_src

pyc = ROOT / ".bytecode_archive/utils/league_table.cpython-313.pyc"
spec = importlib.util.spec_from_file_location("lt_bc", pyc)
lt_bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lt_bc)

db = SessionLocal()
try:
    season = db.query(Season).first()
    if not season:
        print("No season in DB")
        sys.exit(0)
    src = lt_src.build_league_table(db, season.season_id)
    bc = lt_bc.build_league_table(db, season.season_id)
    print("rows:", len(src), len(bc))
    if src and bc:
        print("keys match:", set(src[0].keys()) == set(bc[0].keys()))
        print("last_5 sample:", src[0].get("last_5"))
finally:
    db.close()
