#!/usr/bin/env python3
"""One-shot: mark overdue upcoming fixtures for sim + run broadcast gate."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.db import SessionLocal
from workers.platform_coordinator import run_broadcast_gate


def main():
    db = SessionLocal()
    try:
        n = run_broadcast_gate(db)
        print(f"broadcast_gate changes: {n}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
