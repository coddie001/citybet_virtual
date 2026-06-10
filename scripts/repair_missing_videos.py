"""Render MP4 for GfrDump rows that have sim data but no video file."""
import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import SessionLocal, GfrDump
from utils.video_repair import repair_one, _dump_steps
from utils.virtual_schedule import match_has_video


def find_candidates(db, limit: int | None = None) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    for dump in db.query(GfrDump).all():
        if _dump_steps(dump) < 100:
            continue
        if match_has_video(dump, dump.match_id):
            continue
        ids.append(dump.match_id)
        if limit and len(ids) >= limit:
            break
    return ids


def main():
    parser = argparse.ArgumentParser(description="Repair missing match videos")
    parser.add_argument("--match-id", action="append", dest="match_ids", default=[])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--all", action="store_true", help="Repair all candidates")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.match_ids:
            targets = [uuid.UUID(m) for m in args.match_ids]
        elif args.all:
            targets = find_candidates(db)
        else:
            targets = find_candidates(db, limit=args.limit or 1)

        ok = fail = 0
        for mid in targets:
            print(f"  rendering {mid} ...")
            if repair_one(db, mid):
                ok += 1
                print(f"  OK {mid}")
            else:
                fail += 1
                print(f"  FAILED/skipped {mid}")
        print(f"Done: {ok} repaired, {fail} failed/skipped")
    finally:
        db.close()


if __name__ == "__main__":
    main()
