#!/usr/bin/env python3
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.match_sync import build_match_sync_payload

mid = uuid.UUID("eaf97341-1672-464b-b8ff-727466e8cd9a")
stats = json.loads((ROOT / "dumps" / str(mid) / "_stats.json").read_text())
print(json.dumps(build_match_sync_payload(mid, stats), indent=2))
