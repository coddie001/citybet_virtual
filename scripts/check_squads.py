#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils.db import SessionLocal, Team, Player
from utils.fc26_loader import build_roster_from_fc26

db = SessionLocal()
for club in ["Ipswich Town", "Liverpool", "Las Palmas", "Manchester United"]:
    t = db.query(Team).filter(Team.team_name == club).first()
    if not t:
        print(f"{club}: NO TEAM")
        continue
    names = [p.player_name for p in db.query(Player).filter(Player.team_id == t.team_id).all()]
    fc26, _ = build_roster_from_fc26(t.league_name, t.team_name)
    fc26_names = [p["player_name"] for p in fc26] if fc26 else ["FALLBACK"]
    print(f"\n{club} ({t.league_name}) DB: {names[:6]}...")
    print(f"  FC26 would be: {fc26_names[:6]}...")
db.close()
