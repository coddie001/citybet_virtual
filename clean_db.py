"""
CityBet Virtuals - Database Reset / Clean Slate
================================================
Wipes all simulation *results* so the queue can be re-run from scratch with the
fixed actor-vs-actor engine, WITHOUT deleting your seasons / teams / players /
fixtures themselves.

What it does:
  * Every fixture            -> status='upcoming', settled=False, score='0-0',
                               outcome=None
  * Every event_market       -> status='open', winning_selection=False
  * Every gfr_dump row       -> DELETED (videos/stats blobs)
  * Every season             -> current_gwk reset to 1

Options:
  --reset-tired   also reset every player's tired_factor back to 0.000
  --wipe-files    also delete the on-disk dumps/ and videos/ contents

Usage (from project root, inside the venv):
    venv/bin/python3 clean_db.py
    venv/bin/python3 clean_db.py --reset-tired --wipe-files
"""

import argparse
import shutil
from pathlib import Path

from utils.db import SessionLocal, Season, Fixture, EventMarket, GfrDump, Player

PROJECT_ROOT = Path(__file__).resolve().parent


def clean_database(reset_tired: bool = False) -> None:
    db = SessionLocal()
    try:
        # 1. Drop all simulation dumps (videos + stats).
        n_dumps = db.query(GfrDump).delete(synchronize_session=False)
        print(f"  Deleted {n_dumps} gfr_dump rows (videos/stats).")

        # 2. Reset every fixture back to a clean 'upcoming' state.
        fixtures = db.query(Fixture).all()
        for f in fixtures:
            f.status = "upcoming"
            f.settled = False
            f.score = "0-0"
            f.outcome = None
        print(f"  Reset {len(fixtures)} fixtures -> upcoming (score 0-0, no outcome).")

        # 3. Reopen every market.
        markets = db.query(EventMarket).all()
        for m in markets:
            m.status = "open"
            m.winning_selection = False
        print(f"  Reopened {len(markets)} event_markets.")

        # 4. Rewind every season to gameweek 1.
        seasons = db.query(Season).all()
        for s in seasons:
            s.current_gwk = 1
        print(f"  Reset current_gwk=1 for {len(seasons)} seasons.")

        # 5. Optionally reset accumulated tiredness.
        if reset_tired:
            players = db.query(Player).all()
            for p in players:
                p.tired_factor = 0.000
            print(f"  Reset tired_factor=0 for {len(players)} players.")

        db.commit()
        print("\n[OK] Database is clean. The queue will re-simulate from scratch.")
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] Rolled back: {exc}")
        raise
    finally:
        db.close()


def wipe_files() -> None:
    for sub in ("dumps", "videos"):
        target = PROJECT_ROOT / sub
        if target.exists():
            for child in target.iterdir():
                try:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                except Exception as exc:
                    print(f"  Could not remove {child}: {exc}")
            print(f"  Wiped on-disk contents of {sub}/")
        target.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Reset CityBet Virtuals simulation results.")
    ap.add_argument("--reset-tired", action="store_true",
                    help="Also reset every player's tired_factor to 0.")
    ap.add_argument("--wipe-files", action="store_true",
                    help="Also delete on-disk dumps/ and videos/ contents.")
    args = ap.parse_args()

    print("Cleaning database…")
    clean_database(reset_tired=args.reset_tired)
    if args.wipe_files:
        print("\nWiping on-disk artifacts…")
        wipe_files()
    print("\nDone. You can now run:  ./run.sh")
