"""Shared dependencies for API routes (data store, and later: auth)."""
from __future__ import annotations

from ..core.store import get_store


def store_dep():
    """FastAPI dependency that hands routes the data store."""
    return get_store()


# TODO (see docs/manual_work.md): add a Firebase Auth check here that verifies
# the caller's token and tenant membership before any write.
