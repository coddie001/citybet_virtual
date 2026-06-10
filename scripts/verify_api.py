"""Quick smoke test of frontend API endpoints."""
import json
import uuid
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def check(path, **params):
    r = client.get(path, params=params)
    print(f"{path} -> {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data if not isinstance(data, list) else data[:2], indent=2)[:600])
    else:
        print(r.text[:200])
    print()

check("/health")
check("/leagues")
leagues = client.get("/leagues").json()
if leagues:
    sid = leagues[0]["season_id"]
    lname = leagues[0]["league_name"]
    check(f"/leagues/{lname}/teams")
    check(f"/seasons/{sid}/table")
    check("/fixtures", season_id=sid, limit=3)
    check("/results", season_id=sid, limit=3)
    check("/stats/top-scorers", season_id=sid, limit=5)
    check("/live/now", season_id=sid)
    check("/live/all")
    teams = client.get(f"/leagues/{lname}/teams").json().get("teams", [])
    if teams:
        check(f"/teams/{teams[0]['team_id']}/players")
