import urllib.request, json

with urllib.request.urlopen("http://localhost:8000/live/all") as r:
    data = json.loads(r.read())

for d in data:
    fixture = d.get('fixture') or {}
    has_video = fixture.get('has_video')
    source = d['source']
    status = fixture.get('status')
    match_id = (fixture.get('match_id') or 'None')[:8]
    home = (fixture.get('home_team') or {}).get('name', '?')
    away = (fixture.get('away_team') or {}).get('name', '?')
    print(f"{d['league_name']:15s} | {source:20s} | has_video={has_video} | status={status} | {home} vs {away}")
