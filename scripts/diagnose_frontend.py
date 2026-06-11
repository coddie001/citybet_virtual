#!/usr/bin/env python3
"""Quick API + carousel diagnostic."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read().decode())

def main():
    try:
        carousel = get("/carousel")
        leagues = get("/leagues")
    except Exception as exc:
        print("API DOWN:", exc)
        return 1

    items = carousel.get("items") or []
    print("carousel mode:", carousel.get("mode"), "total:", carousel.get("total"))
    print("leagues:", len(leagues))
    statuses = {}
    for it in items:
        statuses[it.get("status")] = statuses.get(it.get("status"), 0) + 1
    print("item statuses:", statuses)
    print("has_video count:", sum(1 for i in items if i.get("has_video")))
    if items:
        it = items[0]
        print("sample:", it.get("league_name"), it.get("status"), "step", it.get("carousel_step"))
        print("  sched_ms:", it.get("scheduled_start_at_ms"))
        print("  home:", (it.get("home_team") or {}).get("name"))

    try:
        live = get("/live/all")
        print("live/all cards:", len(live))
    except Exception as exc:
        print("live/all failed:", exc)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
