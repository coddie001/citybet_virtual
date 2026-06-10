#!/usr/bin/env python3
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.db import Season, SessionLocal

BASE = "http://localhost:8000"


def get(path: str):
    with urllib.request.urlopen(f"{BASE}{path}") as resp:
        return json.load(resp)


def main():
    db = SessionLocal()
    try:
        season = db.query(Season).first()
        if not season:
            print("No season")
            return
        sid = str(season.season_id)
    finally:
        db.close()

    table = get(f"/seasons/{sid}/table")
    row = table["table"][0]
    print("table OK:", row["team_name"], row.get("last_5"))

    fixtures = get(f"/fixtures?season_id={sid}&limit=3")
    print("fixtures OK:", len(fixtures.get("fixtures", [])))

    results = get(f"/results?season_id={sid}&limit=3")
    print("results OK:", len(results.get("results", [])))

    scorers = get(f"/stats/top-scorers?season_id={sid}")
    print("scorers OK:", len(scorers.get("scorers", [])))


if __name__ == "__main__":
    main()
