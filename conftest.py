"""
pytest conftest.py - shared fixtures for CityBet Virtuals test suite
"""
import os
import sys
from pathlib import Path

# Ensure project root is on path before any test collection
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Set dummy SDL env vars so pygame doesn't try to open a display during tests
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
