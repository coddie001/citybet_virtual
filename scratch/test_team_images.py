#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.team_fixture_images import get_team_image_index, reload_index

reload_index()
idx = get_team_image_index()
print("teams indexed:", len(idx))
print("default fallbacks:", sum(1 for v in idx.values() if "default_image" in v))
for team, path in list(idx.items())[:5]:
    print(f"  {team}: {path}")
