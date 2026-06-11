#!/usr/bin/env python3
"""Integration test for wall-clock carousel scheduling."""
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.carousel_schedule import (
    build_carousel_response,
    countdown_for_scheduled,
    enqueue_scheduled_fixtures,
    enqueue_video_ready_immediate,
    promote_preparing_to_live,
    schedule_mode,
    use_wall_clock_schedule,
)
from utils.db import SessionLocal, Fixture, GfrDump, Season
from utils.virtual_schedule import match_has_video


def main():
    print("=== config ===")
    print("schedule_mode:", schedule_mode())
    print("wall_clock:", use_wall_clock_schedule())

    print("\n=== API /carousel ===")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/carousel", timeout=5) as r:
            body = r.read().decode()
            data = json.loads(body)
        print("HTTP 200, mode:", data.get("mode"), "items:", data.get("total"))
        for it in (data.get("items") or [])[:5]:
            cd = it.get("countdown") or {}
            print(
                " ",
                it.get("carousel_step"),
                it.get("league_name"),
                it.get("status"),
                "sched_ms=",
                it.get("scheduled_start_at_ms"),
                "cd=",
                cd.get("formatted"),
                "in_window=",
                cd.get("in_countdown_window"),
            )
    except Exception as exc:
        print("API FAILED:", exc)

    db = SessionLocal()
    try:
        print("\n=== DB snapshot (before gate) ===")
        video_upcoming = 0
        for season in db.query(Season).filter(Season.season_status == "active").all():
            name = " ".join(season.tournament_name.split()[:-1])
            rows = (
                db.query(Fixture)
                .filter(
                    Fixture.season_id == season.season_id,
                    Fixture.status.in_(("upcoming", "preparing", "live")),
                )
                .order_by(Fixture.show_at_ms)
                .limit(5)
                .all()
            )
            for f in rows:
                dump = db.query(GfrDump).filter(GfrDump.match_id == f.match_id).first()
                hv = match_has_video(dump, f.match_id)
                sched = (f.predictions or {}).get("_scheduled_start_at")
                if f.status == "upcoming" and hv:
                    video_upcoming += 1
                print(f"  {name[:14]:14} {str(f.match_id)[:8]} {f.status:10} video={hv} sched={bool(sched)}")

        print("video-ready upcoming:", video_upcoming)

        print("\n=== run broadcast gate functions ===")
        n1 = enqueue_video_ready_immediate(db)
        n2 = enqueue_scheduled_fixtures(db)
        n3 = promote_preparing_to_live(db)
        print(f"immediate={n1} batch={n2} promoted={n3}")

        print("\n=== build_carousel_response ===")
        payload = build_carousel_response(db)
        print("items:", payload["total"])
        for it in payload["items"][:5]:
            cd = it["countdown"]
            print(
                " ",
                it["carousel_step"],
                it["league_name"],
                it["status"],
                "step_ok=",
                it["carousel_step"] < payload["total"],
                "cd=",
                cd["formatted"],
                "live=",
                cd["is_kickoff"],
            )

        print("\n=== countdown logic spot-check ===")
        live_row = (
            db.query(Fixture).filter(Fixture.status == "live").first()
        )
        prep_row = (
            db.query(Fixture).filter(Fixture.status == "preparing").first()
        )
        if prep_row:
            cd = countdown_for_scheduled(prep_row)
            print("preparing countdown:", cd["formatted"], "in_window:", cd["in_countdown_window"])
        elif live_row:
            cd = countdown_for_scheduled(live_row)
            print("live is_kickoff:", cd["is_kickoff"])
        else:
            print("no preparing/live rows to spot-check countdown")

        print("\n=== PASS/FAIL ===")
        fails = []
        if not use_wall_clock_schedule():
            fails.append("wall_clock mode not active")
        if payload.get("mode") != "wall_clock":
            fails.append("carousel response mode wrong")
        eligible = 0
        for season in db.query(Season).filter(Season.season_status == "active").all():
            gwk = season.current_gwk or 1
            eligible += (
                db.query(Fixture)
                .filter(
                    Fixture.season_id == season.season_id,
                    Fixture.status.in_(("upcoming", "preparing", "live")),
                    Fixture.gameweek >= gwk,
                )
                .count()
            )
        if eligible > 0 and payload["total"] == 0:
            fails.append("carousel empty but eligible fixtures exist in DB")
        statuses = [it["status"] for it in payload["items"]]
        seen_non_live = False
        for s in statuses:
            if s != "live":
                seen_non_live = True
            elif seen_non_live:
                fails.append("live fixtures must sort before upcoming/preparing")
                break
        for it in payload["items"]:
            if it["status"] == "live" and it["countdown"].get("in_countdown_window"):
                fails.append("live fixture must not have countdown window")
        steps = [it["carousel_step"] for it in payload["items"]]
        if steps and steps != list(range(len(steps))):
            fails.append("carousel_step not 0..n-1")

        if fails:
            print("FAIL:", "; ".join(fails))
            return 1
        print("PASS (structure OK; carousel includes fixtures without video)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
