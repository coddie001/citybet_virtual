#!/usr/bin/env python3
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/live/all", timeout=20) as r:
    cards = json.loads(r.read())
for c in cards:
    fx = c.get("fixture") or {}
    print(c.get("league_name"), c.get("source"), fx.get("status"), fx.get("has_video"))
