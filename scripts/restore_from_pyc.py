#!/usr/bin/env python3
"""
Emergency recovery: recreate .py stubs that load bytecode from .bytecode_archive/.
Never overwrites real source files. Run: venv/bin/python3 scripts/restore_from_pyc.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / ".bytecode_archive"

STUB = '''\
"""RECOVERED STUB — loads bytecode from .bytecode_archive/. Replace with real source when restored."""
import importlib.util
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
_root = _here.parent if _here.name in {{"utils", "workers", "scripts"}} else _here
_pyc = _root / ".bytecode_archive" / "{archive_rel}" / "{pyc_name}"
if not _pyc.is_file():
    raise ImportError(f"Missing bytecode archive: {{_pyc}}")

_spec = importlib.util.spec_from_file_location("{qualname}", _pyc)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["{qualname}"] = _mod
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

for _name, _val in _mod.__dict__.items():
    if not _name.startswith("_"):
        globals()[_name] = _val
'''

# Skip files that have real Python source (not stubs)
SKIP_PATHS = {
    ROOT / "main.py",
    ROOT / "utils" / "virtual_schedule.py",
    ROOT / "utils" / "fixture_timing.py",
    ROOT / "utils" / "fixture_image_search.py",
    ROOT / "utils" / "team_fixture_images.py",
    ROOT / "utils" / "video_compress.py",
    ROOT / "utils" / "fixture_assets.py",
}

# (directory, pyc filename, qualname, output filename, archive subdir)
TARGETS = [
    (ROOT / "utils", "db.cpython-313.pyc", "utils.db", "db.py", "utils"),
    (ROOT / "utils", "draw_match.cpython-313.pyc", "utils.draw_match", "draw_match.py", "utils"),
    (ROOT / "utils", "fc26_loader.cpython-313.pyc", "utils.fc26_loader", "fc26_loader.py", "utils"),
    (ROOT / "utils", "league_table.cpython-313.pyc", "utils.league_table", "league_table.py", "utils"),
    (ROOT / "utils", "seeder.cpython-313.pyc", "utils.seeder", "seeder.py", "utils"),
    (ROOT / "utils", "stats_aggregator.cpython-313.pyc", "utils.stats_aggregator", "stats_aggregator.py", "utils"),
    (ROOT / "workers", "fixture_generator.cpython-313.pyc", "workers.fixture_generator", "fixture_generator.py", "workers"),
    (ROOT / "workers", "game_simulator.cpython-313.pyc", "workers.game_simulator", "game_simulator.py", "workers"),
    (ROOT / "workers", "platform_coordinator.cpython-313.pyc", "workers.platform_coordinator", "platform_coordinator.py", "workers"),
    (ROOT / "workers", "season_manager.cpython-313.pyc", "workers.season_manager", "season_manager.py", "workers"),
]


def _is_real_source(path: Path) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return "RECOVERED STUB" not in text and len(text) > 200


def main():
    restored = 0
    for directory, pyc_name, qualname, out_name, archive_rel in TARGETS:
        out_path = directory / out_name
        if out_path in SKIP_PATHS or _is_real_source(out_path):
            print(f"SKIP (real source): {out_path}")
            continue

        archive_path = ARCHIVE / archive_rel / pyc_name
        src_pyc = directory / "__pycache__" / pyc_name
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        if src_pyc.is_file() and (
            not archive_path.is_file() or src_pyc.stat().st_size > archive_path.stat().st_size
        ):
            archive_path.write_bytes(src_pyc.read_bytes())

        if not archive_path.is_file():
            print(f"SKIP (no archive): {archive_path}")
            continue

        content = STUB.format(pyc_name=pyc_name, qualname=qualname, archive_rel=archive_rel)
        out_path.write_text(content, encoding="utf-8")
        print(f"OK {out_path}")
        restored += 1
    print(f"\nRestored {restored} stub files from {ARCHIVE}")


if __name__ == "__main__":
    main()
