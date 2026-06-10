#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.fixture_image_search import resolve_fixture_image_url

for pair in [("Liverpool", "Crystal Palace"), ("Real Madrid", "Barcelona")]:
    url = resolve_fixture_image_url(pair[0], pair[1], force_search=True)
    print(f"{pair[0]} vs {pair[1]} -> {url}")
