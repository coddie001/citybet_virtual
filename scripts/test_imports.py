import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
tmarl = root / "tmarl"
sys.path.insert(0, str(root))
sys.path.insert(1, str(tmarl))

import utils.db
import configs
print("utils.db and configs ok")
