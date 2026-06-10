from utils.fc26_loader import build_roster_from_fc26
import json

roster, rating = build_roster_from_fc26("Premier League", "Manchester City")
print(f"Man City squad rating: {rating}\n")
for p in roster:
    print(f"{p['role']:3} {p['player_name'][:30]:30} OVR={p['gfr_attributes']['overall']} "
          f"vel={p['velocity']} shoot={p['rewards']['shooting_reward']}")
