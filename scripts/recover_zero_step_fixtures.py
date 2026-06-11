#!/usr/bin/env python3
"""One-shot: re-queue live/preparing fixtures with steps < 100 for simulation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.broadcast_gate import recover_fixtures_needing_sim
from utils.db import SessionLocal


def main() -> int:
    db = SessionLocal()
    try:
        n = recover_fixtures_needing_sim(db)
        print(f"recover_fixtures_needing_sim: {n} change(s)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
