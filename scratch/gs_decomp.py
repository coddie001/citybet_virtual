# Source Generated with Decompyle++
# File: game_simulator.cpython-313.pyc (Python 3.13)

__doc__ = '\nCityBet Virtuals - GFootball Game Simulator (Audited & Restructured)\n===================================================================\nRuns GFootball 11v11 matches with player attributes from the DB\ninfluencing agent actions at each step. Produces .dump traces,\nrenders them to MP4/GIF via draw_match.py, and persists results.\n\nSequential queue: 1 match at a time.\n'
import os
import sys
from pathlib import Path
from typing import Optional
CURRENT_FILE = None(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]
0(str, None(PROJECT_ROOT))
LOCAL_TMARL = PROJECT_ROOT / 'tmarl'
1(str, None(LOCAL_TMARL))
os.environ['PYTHONPATH'] = None(PROJECT_ROOT)
from utils.db import SessionLocal, Season, Team, Player, Fixture, EventMarket, GfrDump
import uuid
import json
import time
import shutil
import random
import pickle
import logging
import traceback
import tempfile
from datetime import datetime
import numpy as np
import torch
DUMP_STORE = PROJECT_ROOT / 'dumps'
VIDEO_STORE = PROJECT_ROOT / 'videos'
ACTOR_PT = PROJECT_ROOT / 'models' / '11_vs_11_kaggle' / 'actor.pt'
# WARNING: Decompyle incomplete
