#!/usr/bin/env python3
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pyc = ROOT / ".bytecode_archive/utils/team_fixture_images.cpython-313.pyc"
spec = importlib.util.spec_from_file_location("tfi", pyc)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

print("FILENAME_ALIASES =", repr(mod.FILENAME_ALIASES))
print("EXT_PRIORITY =", repr(mod.EXT_PRIORITY))
