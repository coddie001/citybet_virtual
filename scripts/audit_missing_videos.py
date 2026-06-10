"""Audit completed/live fixtures with sim data but no MP4 on disk."""
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import SessionLocal, Fixture, GfrDump, Season

VIDEO_DIR = Path(__file__).resolve().parent.parent / "videos"


def fixture_has_video(dump, match_id) -> bool:
    mp4 = VIDEO_DIR / f"{match_id}_full.mp4"
    if mp4.is_file():
        return True
    if dump and dump.video_url and os.path.isfile(dump.video_url):
        return True
    if dump and getattr(dump, "match_video", None):
        return True
    return False


def main():
    db = SessionLocal()
    by_league = defaultdict(
        lambda: {"missing": 0, "has_video": 0, "total": 0, "samples": []}
    )
    try:
        for f in db.query(Fixture).filter(Fixture.status.in_(["completed", "live"])).all():
            dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
            if not dump or not dump.gfr_stats:
                continue
            steps = int(
                dump.gfr_stats.get("total_steps") or dump.gfr_stats.get("steps") or 0
            )
            if steps < 100:
                continue
            season = db.query(Season).filter(Season.season_id == f.season_id).first()
            league = season.tournament_name if season else "unknown"
            by_league[league]["total"] += 1
            if fixture_has_video(dump, f.match_id):
                by_league[league]["has_video"] += 1
            else:
                by_league[league]["missing"] += 1
                if len(by_league[league]["samples"]) < 3:
                    by_league[league]["samples"].append(str(f.match_id))

        print("=== Missing MP4 by league (steps>=100, completed/live) ===")
        tot_m = tot_h = tot_t = 0
        for league in sorted(by_league):
            d = by_league[league]
            tot_m += d["missing"]
            tot_h += d["has_video"]
            tot_t += d["total"]
            print(
                f"{league}: total={d['total']} has_video={d['has_video']} "
                f"MISSING={d['missing']} samples={d['samples']}"
            )
        print(f"GRAND TOTAL: {tot_t} sims, {tot_h} with video, {tot_m} MISSING")
    finally:
        db.close()


if __name__ == "__main__":
    main()
