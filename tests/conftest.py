"""Tests run on the small, fixed dataset in tests/fixtures/, not on fixtures/.

fixtures/ is a snapshot of the real Firestore data and changes whenever the
real data changes; tests must not.
"""
from pathlib import Path

from backend.core import config

config.FIXTURES_DIR = Path(__file__).parent / "fixtures"
