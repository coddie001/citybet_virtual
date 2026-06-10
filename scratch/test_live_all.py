#!/usr/bin/env python3
import json
import sys
import urllib.request

url = "http://localhost:8000/live/all"
try:
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read().decode())
except Exception as exc:
    print("API_NOT_RUNNING", exc)
    sys.exit(1)

print("leagues:", len(data), [c["league_name"] for c in data])
for card in data:
    fx = card.get("fixture")
    if not fx:
        continue
    sync = fx.get("match_sync")
    print(
        card["league_name"],
        fx.get("match_id"),
        "match_sync=",
        "yes" if sync else "no",
        "goals=",
        len((sync or {}).get("goal_events") or []),
    )
    break
