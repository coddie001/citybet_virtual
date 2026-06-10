"""Pre-frontend platform health audit."""
from utils.db import SessionLocal, Season, Fixture, GfrDump, EventMarket, Team, Player

db = SessionLocal()

print("=== SEASONS (4 leagues expected) ===")
seasons = db.query(Season).all()
for s in seasons:
    teams = db.query(Team).filter(Team.season_id == s.season_id).count()
    fx_total = db.query(Fixture).filter(Fixture.season_id == s.season_id).count()
    fx_done = db.query(Fixture).filter(Fixture.season_id == s.season_id, Fixture.status == "completed").count()
    fx_up = db.query(Fixture).filter(Fixture.season_id == s.season_id, Fixture.status == "upcoming").count()
    fx_err = db.query(Fixture).filter(Fixture.season_id == s.season_id, Fixture.status == "error").count()
    print(
        f"  {s.tournament_name}: status={s.season_status} "
        f"gwk={s.current_gwk}/{s.cum_gwk} teams={teams} "
        f"fixtures={fx_total} done={fx_done} upcoming={fx_up} error={fx_err}"
    )

total = db.query(Fixture).count()
pred_null = db.query(Fixture).filter(Fixture.predictions.is_(None)).count()
out_null = db.query(Fixture).filter(Fixture.outcome.is_(None)).count()
out_set = db.query(Fixture).filter(Fixture.outcome.isnot(None)).count()
completed = db.query(Fixture).filter(Fixture.status == "completed").count()
completed_no_out = db.query(Fixture).filter(Fixture.status == "completed", Fixture.outcome.is_(None)).count()
show_at_zero = db.query(Fixture).filter(Fixture.show_at_ms == 0).count()
no_image = db.query(Fixture).filter(Fixture.fixture_image_url.is_(None)).count()

print("\n=== FIXTURES JSON / TIMING / IMAGES ===")
print(f"  total={total}")
print(f"  predictions_null={pred_null}  outcome_set={out_set}  outcome_null={out_null}")
print(f"  completed={completed}  completed_without_outcome={completed_no_out}")
print(f"  show_at_ms_zero={show_at_zero}  fixture_image_url_null={no_image}")

f = db.query(Fixture).filter(Fixture.status == "completed", Fixture.outcome.isnot(None)).first()
if f:
    print(f"  sample outcome: {f.outcome}")
f2 = db.query(Fixture).filter(Fixture.predictions.isnot(None)).first()
if f2:
    print(f"  sample predictions: {f2.predictions}")

players = db.query(Player).count()
with_face = db.query(Player).filter(Player.player_face_url.isnot(None)).count()
dumps = db.query(GfrDump).count()
with_video = db.query(GfrDump).filter(GfrDump.match_video.isnot(None)).count()

print("\n=== PLAYERS / DUMPS / MARKETS ===")
print(f"  players={players} with_face_url={with_face}")
print(f"  gfr_dumps={dumps} with_video_blob={with_video}")
print(f"  markets open={db.query(EventMarket).filter(EventMarket.status=='open').count()}")
print(f"  markets settled={db.query(EventMarket).filter(EventMarket.status=='settled').count()}")

db.close()
