#!/usr/bin/env python3
import dis
import importlib.util
import marshal
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pyc = ROOT / ".bytecode_archive/utils/league_table.cpython-313.pyc"

with open(pyc, "rb") as f:
    f.read(16)
    code = marshal.load(f)

for const in code.co_consts:
    if isinstance(const, types.CodeType) and const.co_name in {
        "_result_for_team",
        "build_team_form",
        "build_league_table",
        "build_leaderboard_payload",
        "persist_league_table",
    }:
        print("=" * 60, const.co_name)
        dis.dis(const)
