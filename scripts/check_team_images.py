#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.team_fixture_images import (
    TEAM_IMG_DIR,
    FILENAME_ALIASES,
    _stem_key,
    reload_index,
    get_team_image_index,
)

reload_index()
idx = get_team_image_index()
print(f"Mapped teams: {len(idx)}")
for team, url in sorted(idx.items()):
    print(f"  {team}: {url}")

unmapped = []
for path in TEAM_IMG_DIR.iterdir():
    if not path.is_file() or path.name.endswith(":Zone.Identifier"):
        continue
    if path.suffix.lower() not in {".jpg", ".jpeg", ".webp", ".png", ".avif"}:
        continue
    key = _stem_key(path)
    if key not in FILENAME_ALIASES:
        unmapped.append(path.name)

if unmapped:
    print(f"Unmapped files ({len(unmapped)}):")
    for name in sorted(unmapped):
        print(f"  {name} -> slug {_stem_key(Path(name))}")
