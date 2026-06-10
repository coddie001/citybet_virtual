"""Loads game_simulator from bytecode archive (full simulator)."""
import importlib.util
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_tmarl = _root / "tmarl"
# Project root first (utils.db); tmarl second (configs) — order matters.
_root_s, _tmarl_s = str(_root), str(_tmarl)
if _root_s not in sys.path:
    sys.path.insert(0, _root_s)
if _tmarl_s not in sys.path:
    sys.path.insert(1, _tmarl_s)
# Spawned child processes need the same paths (sim imports `configs` from tmarl/).
_prev = os.environ.get("PYTHONPATH", "")
os.environ["PYTHONPATH"] = os.pathsep.join(
    [_root_s, _tmarl_s] + ([_prev] if _prev else [])
)

# Bytecode build resolves actor.pt under .bytecode_archive/models — link to real weights.
_model_link = _root / ".bytecode_archive" / "models" / "11_vs_11_kaggle" / "actor.pt"
_model_src = _root / "models" / "11_vs_11_kaggle" / "actor.pt"
if _model_src.is_file():
    _model_link.parent.mkdir(parents=True, exist_ok=True)
    if not _model_link.exists():
        _model_link.symlink_to(_model_src.resolve())

_pyc = _root / ".bytecode_archive" / "workers" / "game_simulator.cpython-313.pyc"
if not _pyc.is_file():
    raise ImportError(f"Missing bytecode archive: {_pyc}")

_spec = importlib.util.spec_from_file_location("workers.game_simulator_impl", _pyc)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

for _name, _val in _mod.__dict__.items():
    if not _name.startswith("_"):
        globals()[_name] = _val

# All MP4s live in project videos/ — never scatter under .bytecode_archive.
from utils.video_paths import VIDEO_DIR as _CANONICAL_VIDEO_DIR

_CANONICAL_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_STORE = _CANONICAL_VIDEO_DIR
if hasattr(_mod, "VIDEO_STORE"):
    _mod.VIDEO_STORE = _CANONICAL_VIDEO_DIR

# Wrap bytecode sim: upcoming until MP4 confirmed; sim starts with 3-min countdown window.
_bytecode_simulate_next_fixture = globals().get("simulate_next_fixture")


def simulate_next_fixture(db):
    """Run sim only after processing countdown began; never leave live without MP4."""
    import time

    from utils.broadcast_gate import finalize_after_sim, fixture_ready_for_sim
    from utils.db import Fixture

    if _bytecode_simulate_next_fixture is None:
        return False

    candidates = (
        db.query(Fixture)
        .filter(Fixture.status == "upcoming")
        .order_by(Fixture.show_at_ms.asc())
        .limit(40)
        .all()
    )
    fixture = None
    for cand in candidates:
        if fixture_ready_for_sim(cand, db):
            fixture = cand
            break
    if not fixture:
        return False

    pred = dict(fixture.predictions or {})
    if not pred.get("_processing_started_at"):
        pred["_processing_started_at"] = time.time()
        fixture.predictions = pred
        fixture.status = "upcoming"
        db.commit()

    try:
        return _bytecode_simulate_next_fixture(db)
    finally:
        from utils.video_faststart import finalize_recent_mp4s

        finalize_recent_mp4s()
        finalize_after_sim(db)


globals()["simulate_next_fixture"] = simulate_next_fixture

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CityBet Virtuals GFR Simulator")
    parser.add_argument(
        "--mode",
        choices=["one", "gameweek", "all"],
        default="one",
        help="one=next fixture, gameweek=full GWK, all=continuous queue",
    )
    parser.add_argument("--gameweek", type=int, default=1)
    parser.add_argument("--max", type=int, default=None)
    args = parser.parse_args()

    if args.mode == "one":
        from utils.db import SessionLocal

        db = SessionLocal()
        try:
            simulate_next_fixture(db)
        finally:
            db.close()
    elif args.mode == "gameweek":
        run_gameweek(args.gameweek)
    elif args.mode == "all":
        run_queue_continuously(max_matches=args.max)
