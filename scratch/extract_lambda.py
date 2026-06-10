#!/usr/bin/env python3
import dis
import marshal
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pyc = ROOT / ".bytecode_archive/utils/league_table.cpython-313.pyc"

with open(pyc, "rb") as f:
    f.read(16)
    code = marshal.load(f)

for const in code.co_consts:
    if isinstance(const, types.CodeType):
        if const.co_name == "build_league_table":
            for inner in const.co_consts:
                if isinstance(inner, types.CodeType) and inner.co_name == "<lambda>":
                    print("lambda at line 129:")
                    dis.dis(inner)
                    print("varnames:", inner.co_varnames)
                    print("consts:", inner.co_consts)
