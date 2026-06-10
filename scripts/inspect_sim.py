import importlib.util
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
_pyc = _root / ".bytecode_archive" / "workers" / "game_simulator.cpython-313.pyc"
spec = importlib.util.spec_from_file_location("sim", _pyc)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
callables = [n for n in dir(mod) if not n.startswith("_")]
interesting = [n for n in callables if any(k in n.lower() for k in ("main", "run", "queue", "loop", "worker", "process"))]
print("interesting:", interesting)
import inspect
for fn in ("run_simulation", "run_gameweek", "run_queue_continuously", "simulate_next_fixture"):
    if hasattr(mod, fn):
        print(fn, inspect.signature(getattr(mod, fn)))
