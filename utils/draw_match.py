"""RECOVERED STUB — loads bytecode from .bytecode_archive/. Replace with real source when restored."""
import importlib.util
import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
_root = _here.parent if _here.name in {"utils", "workers", "scripts"} else _here
_pyc = _root / ".bytecode_archive" / "utils" / "draw_match.cpython-313.pyc"
if not _pyc.is_file():
    raise ImportError(f"Missing bytecode archive: {_pyc}")

_spec = importlib.util.spec_from_file_location("utils.draw_match", _pyc)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["utils.draw_match"] = _mod
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

for _name, _val in _mod.__dict__.items():
    if not _name.startswith("_"):
        globals()[_name] = _val
