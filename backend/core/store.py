"""The data store.

The whole app reads data through this one tiny interface, so we can swap the
*source* (local JSON files now, Firestore later) without touching any business
logic.

For the base version only `LocalStore` exists. It reads the JSON files in
fixtures/. Each file is a JSON array of documents.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from . import config


class LocalStore:
    """Reads collections from JSON files in fixtures/."""

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.dir = Path(fixtures_dir or config.FIXTURES_DIR)

    def list(self, collection: str) -> list[dict]:
        """Return every document in a collection (e.g. 'products')."""
        path = self.dir / f"{collection}.json"
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def get(self, collection: str, id_field: str, doc_id: str) -> dict | None:
        """Return one document whose `id_field` equals `doc_id`, or None."""
        for doc in self.list(collection):
            if doc.get(id_field) == doc_id:
                return doc
        return None


@lru_cache(maxsize=1)
def get_store() -> LocalStore:
    """Return the shared store instance.

    Later, when DATA_BACKEND == 'firestore', this is where we return a
    FirestoreStore instead. The rest of the code does not change.
    """
    if config.DATA_BACKEND == "firestore":
        raise NotImplementedError(
            "FirestoreStore is not built yet. See docs/manual_work.md. "
            "Set DATA_BACKEND=local to use the bundled fixtures."
        )
    return LocalStore()
