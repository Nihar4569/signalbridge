"""Tests run on the small, fixed dataset in tests/fixtures/, not on fixtures/.

fixtures/ is a snapshot of the real Firestore data and changes whenever the
real data changes; tests must not.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.core import config

config.FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def fixed_planner_clock(monkeypatch):
    """The legacy fixture quotes are valid on 10 October. Expiry tests pass an explicit clock."""
    from backend.domain import planner

    monkeypatch.setattr(planner, "utc_now", lambda: datetime(2026, 10, 10, 12, tzinfo=timezone.utc))
