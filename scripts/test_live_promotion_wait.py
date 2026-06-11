#!/usr/bin/env python3
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.carousel_schedule import promote_preparing_to_live
from utils.db import SessionLocal, Fixture

def fetch_carousel():
    with urllib.request.urlopen("http://127.0.0.1:8000/carousel", timeout=5) as r:
        return json.loads(r.read())

def main():
    print("Waiting up to 70s for scheduled start...")
    for i in range(14):
        db = SessionLocal()
        try:
            n = promote_preparing_to_live(db)
            if n:
                print(f"t+{i*5}s: promoted {n} to live")
        finally:
            db.close()
        data = fetch_carousel()
        for it in data.get("items", []):
            print(
                f"t+{i*5}s:",
                it["status"],
                it["countdown"]["formatted"],
                "kickoff=",
                it["countdown"]["is_kickoff"],
            )
            if it["status"] == "live":
                print("SUCCESS: fixture is live on carousel")
                return 0
        time.sleep(5)
    print("TIMEOUT: fixture did not go live within 70s")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
