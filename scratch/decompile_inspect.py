#!/usr/bin/env python3
"""Inspect bytecode for league_table and team_fixture_images."""
import dis
import marshal
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dump_code(code, indent=0):
    prefix = "  " * indent
    print(f"{prefix}=== {code.co_name} ({code.co_filename}) ===")
    print(f"{prefix}vars: {code.co_varnames}")
    print(f"{prefix}consts:")
    for i, c in enumerate(code.co_consts):
        if isinstance(c, types.CodeType):
            print(f"{prefix}  [{i}] <code {c.co_name}>")
        else:
            print(f"{prefix}  [{i}] {repr(c)[:120]}")
    dis.dis(code)
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            dump_code(c, indent + 1)


def main():
    targets = [
        ROOT / ".bytecode_archive/utils/league_table.cpython-313.pyc",
        ROOT / "utils/__pycache__/team_fixture_images.cpython-313.pyc",
        ROOT / "utils/__pycache__/fixture_image_search.cpython-313.pyc",
    ]
    for p in targets:
        if not p.is_file():
            print(f"MISSING: {p}")
            continue
        print("\n" + "=" * 80)
        print(p)
        with open(p, "rb") as f:
            f.read(16)
            code = marshal.load(f)
        dump_code(code)


if __name__ == "__main__":
    main()
