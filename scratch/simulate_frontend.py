"""
Simulates exactly what the React mapLiveCard logic does:
- accepts virtual_replay sources with has_video=true
- rejects fixtures with has_video=false
"""
import urllib.request, json

REPLAY_SOURCES = {'virtual_replay', 'virtual_completed', 'latest_completed'}

with urllib.request.urlopen("http://localhost:8000/live/all") as r:
    data = json.loads(r.read())

print("=== Frontend simulation: mapLiveCard result ===")
print()
for d in data:
    fixture = d.get('fixture') or {}
    source = d['source']
    has_video = fixture.get('has_video', False)
    status = fixture.get('status', '')
    home = (fixture.get('home_team') or {}).get('name', '?')
    away = (fixture.get('away_team') or {}).get('name', '?')
    score = fixture.get('score', '0-0')
    match_id = fixture.get('match_id', '')

    is_stream_live = source == 'live_status' or status == 'live'
    is_replay = source in REPLAY_SOURCES
    
    # This is the mapLiveCard filter
    accepted = (is_stream_live or is_replay) and has_video
    is_fallback = is_replay

    print(f"League: {d['league_name']}")
    print(f"  source={source}, has_video={has_video}, accepted={accepted}, isFallback={is_fallback}")
    if accepted:
        print(f"  → SHOWS IN DRAWER: {home} {score} {away}")
        print(f"  → video URL: /api/video/{match_id}")
    else:
        print(f"  → HIDDEN (no video or not live/replay)")
    print()
