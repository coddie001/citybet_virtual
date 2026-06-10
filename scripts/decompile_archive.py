#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / ".bytecode_archive"
OUT = ROOT / "recovered"
PYC = ROOT / "venv/bin/decompyle3"


def main():
    OUT.mkdir(exist_ok=True)
    ok = 0
    for pyc in sorted(ARCHIVE.rglob("*.pyc")):
        rel = pyc.relative_to(ARCHIVE)
        out = OUT / rel.with_suffix(".py")
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            r = subprocess.run([str(PYC), str(pyc)], capture_output=True, text=True, timeout=120)
            if r.returncode == 0 and r.stdout.strip():
                out.write_text(r.stdout, encoding="utf-8")
                print(f"OK {out}")
                ok += 1
            else:
                print(f"FAIL {pyc}: {r.stderr[:200]}")
        except Exception as e:
            print(f"ERR {pyc}: {e}")
    print(f"\nDecompiled {ok} files → {OUT}")


if __name__ == "__main__":
    main()
