#!/usr/bin/env python3
import json
import urllib.request

with urllib.request.urlopen("http://localhost:8000/fixtures?status=upcoming&limit=8") as r:
    fx = json.load(r)
print("upcoming total:", fx["total"])
for f in fx["fixtures"][:6]:
    print(" ", f["show_at_ms"], f["home_team"]["name"], "vs", f["away_team"]["name"])

with urllib.request.urlopen("http://localhost:8000/live/all") as r:
    live = json.load(r)
for c in live:
    cd = c.get("countdown") or {}
    print(
        c["league_name"],
        "clock=", c["virtual_clock_ms"],
        "next_show=", cd.get("show_at_ms"),
        "until=", cd.get("ms_until_kickoff"),
        "in_window=", cd.get("in_countdown_window"),
    )
