#!/usr/bin/env python3
"""Audit fixture counts per season — detect duplicates."""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.db import SessionLocal, Season, Team, Fixture

db = SessionLocal()
try:
    total = db.query(Fixture).count()
    print(f"TOTAL FIXTURES IN DB: {total}\n")

    for season in db.query(Season).filter(Season.season_status == "active").order_by(Season.tournament_name).all():
        teams = db.query(Team).filter(Team.season_id == season.season_id).count()
        fixtures = db.query(Fixture).filter(Fixture.season_id == season.season_id).all()
        n = len(fixtures)
        gws = sorted({f.gameweek for f in fixtures})
        expected_double_rr = teams * (teams - 1) if teams else 0
        expected_single_rr = teams * (teams - 1) // 2 if teams else 0

        print(f"{season.tournament_name}")
        print(f"  Teams: {teams}")
        print(f"  Fixtures in DB: {n}")
        print(f"  Gameweeks: {min(gws) if gws else 0}–{max(gws) if gws else 0} ({len(gws)} rounds)")
        print(f"  Expected double round-robin (home+away): {expected_double_rr}")
        print(f"  Expected single round-robin: {expected_single_rr}")

        # Duplicate pairings (same home/away/gameweek)
        pair_keys = [
            (str(f.home_team_id), str(f.away_team_id), f.gameweek) for f in fixtures
        ]
        dup_gwk = {k: v for k, v in Counter(pair_keys).items() if v > 1}
        if dup_gwk:
            print(f"  DUPLICATE home/away/gameweek rows: {len(dup_gwk)}")

        # Same pairing twice in season (any gameweek) — should be exactly 2 in double RR
        pairing = Counter(
            tuple(sorted([str(f.home_team_id), str(f.away_team_id)])) for f in fixtures
        )
        wrong = {k: v for k, v in pairing.items() if v != 2}
        if wrong:
            print(f"  Pairings not appearing exactly twice: {len(wrong)} (sample counts: {list(wrong.values())[:5]})")
        else:
            print(f"  Pairings: each plays exactly twice (home+away) ✓")
        print()

    # All seasons including inactive?
    other = db.query(Season).filter(Season.season_status != "active").count()
    if other:
        extra = db.query(Fixture).join(Season).filter(Season.season_status != "active").count()
        print(f"Non-active seasons: {other}, their fixtures: {extra}")
finally:
    db.close()
