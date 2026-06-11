import importlib.util
from pathlib import Path

_pyc = Path(".bytecode_archive/workers/game_simulator.cpython-313.pyc")
spec = importlib.util.spec_from_file_location("sim", _pyc)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
names = [n for n in dir(mod) if not n.startswith("_") and callable(getattr(mod, n))]
print(names)
