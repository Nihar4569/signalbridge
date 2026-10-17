"""The data store.

The whole app reads (and occasionally writes) through this interface so we can
swap the *source* — local JSON fixtures vs Google Cloud Firestore — without
touching domain math.

Paths in Firestore (docs/schema.md):
    tenants/{tenant_id}/{collection}/{doc_id}
"""
from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from . import config

LIST_CACHE_SECONDS = 15


@runtime_checkable
class DataStore(Protocol):
    """Minimal store contract used by domain/, app/, worker/."""

    backend_name: str

    def list(self, collection: str) -> list[dict]:
        """Return every document in a collection."""
        ...

    def get(self, collection: str, id_field: str, doc_id: str) -> dict | None:
        """Return one document whose `id_field` equals `doc_id`, or None."""
        ...

    def get_by_id(self, collection: str, doc_id: str) -> dict | None:
        """Return one document by its Firestore / natural document id."""
        ...

    def upsert(self, collection: str, doc_id: str, data: dict) -> None:
        """Create or overwrite a document."""
        ...

    def delete(self, collection: str, doc_id: str) -> None:
        """Delete a document if it exists."""
        ...


class LocalStore:
    """Reads collections from JSON files in fixtures/.

    Writes go to an in-memory overlay so approve/reserve can persist operations
    during a process lifetime without mutating the fixture files on disk.
    """

    backend_name = "local"

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.dir = Path(fixtures_dir or config.FIXTURES_DIR)
        self._memory: dict[str, dict[str, dict]] = {}
        self._file_cache: dict[str, list[dict]] = {}

    def _load_file(self, collection: str) -> list[dict]:
        # Parse each fixture file once per process (fixtures don't change at
        # runtime); keeps the dashboard fast when many plans are built in a row.
        cached = self._file_cache.get(collection)
        if cached is not None:
            return cached
        path = self.dir / f"{collection}.json"
        docs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        self._file_cache[collection] = docs
        return docs

    def list(self, collection: str) -> list[dict]:
        from backend.models import doc_id_for

        docs = {doc_id_for(collection, d): dict(d) for d in self._load_file(collection)}
        for doc_id, data in self._memory.get(collection, {}).items():
            docs[doc_id] = dict(data)
        return list(docs.values())

    def get(self, collection: str, id_field: str, doc_id: str) -> dict | None:
        for doc in self.list(collection):
            if doc.get(id_field) == doc_id:
                return doc
        return None

    def get_by_id(self, collection: str, doc_id: str) -> dict | None:
        mem = self._memory.get(collection, {})
        if doc_id in mem:
            return dict(mem[doc_id])
        from backend.models import doc_id_for

        for doc in self._load_file(collection):
            if doc_id_for(collection, doc) == doc_id:
                return dict(doc)
        return None

    def upsert(self, collection: str, doc_id: str, data: dict) -> None:
        self._memory.setdefault(collection, {})[doc_id] = dict(data)

    def delete(self, collection: str, doc_id: str) -> None:
        coll = self._memory.get(collection)
        if coll and doc_id in coll:
            del coll[doc_id]


class SnapshotStore(LocalStore):
    """A private, disposable snapshot. Missing collections never fall back to disk."""

    backend_name = "snapshot"

    def __init__(self, collections: dict[str, list[dict]]) -> None:
        super().__init__()
        self._file_cache = deepcopy(collections)

    def _load_file(self, collection: str) -> list[dict]:
        return self._file_cache.get(collection, [])


class FirestoreStore:
    """Reads/writes tenant-scoped collections in Cloud Firestore.

    Auth: Application Default Credentials, or the Firestore emulator when
    FIRESTORE_EMULATOR_HOST is set (picked up automatically by the SDK).
    """

    backend_name = "firestore"

    def __init__(
        self,
        *,
        project: str | None = None,
        tenant_id: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.tenant_id = tenant_id or config.TENANT_ID
        self.project = project or config.GOOGLE_CLOUD_PROJECT
        self._cache: dict[str, tuple[float, list[dict]]] = {}
        if client is not None:
            self._client = client
        else:
            if not self.project and not config.FIRESTORE_EMULATOR_HOST:
                raise RuntimeError(
                    "GOOGLE_CLOUD_PROJECT is required for DATA_BACKEND=firestore. "
                    "See docs/manual_work.md."
                )
            from google.cloud import firestore

            # The SDK treats an empty FIRESTORE_EMULATOR_HOST (as in .env.example) as "use emulator at ''".
            if not config.FIRESTORE_EMULATOR_HOST:
                os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
            kwargs: dict[str, Any] = {}
            if self.project:
                kwargs["project"] = self.project
            self._client = firestore.Client(**kwargs)

    def _coll(self, collection: str):
        return (
            self._client.collection("tenants")
            .document(self.tenant_id)
            .collection(collection)
        )

    def list(self, collection: str) -> list[dict]:
        # One page builds several plans, each reading the same collections; cache briefly.
        hit = self._cache.get(collection)
        if hit and time.monotonic() - hit[0] < LIST_CACHE_SECONDS:
            return [dict(d) for d in hit[1]]
        out = [dict(snap.to_dict() or {}) for snap in self._coll(collection).stream()]
        self._cache[collection] = (time.monotonic(), out)
        return [dict(d) for d in out]

    def get(self, collection: str, id_field: str, doc_id: str) -> dict | None:
        by_id = self.get_by_id(collection, doc_id)
        if by_id is not None and by_id.get(id_field) == doc_id:
            return by_id
        for doc in self.list(collection):
            if doc.get(id_field) == doc_id:
                return doc
        return None

    def get_by_id(self, collection: str, doc_id: str) -> dict | None:
        snap = self._coll(collection).document(doc_id).get()
        if not snap.exists:
            return None
        return dict(snap.to_dict() or {})

    def upsert(self, collection: str, doc_id: str, data: dict) -> None:
        self._coll(collection).document(doc_id).set(dict(data))
        self._cache.pop(collection, None)

    def delete(self, collection: str, doc_id: str) -> None:
        self._coll(collection).document(doc_id).delete()
        self._cache.pop(collection, None)

    def batch_upsert(self, collection: str, items: list[tuple[str, dict]]) -> int:
        """Write many docs efficiently (chunks of 400; Firestore limit is 500)."""
        if not items:
            return 0
        written = 0
        batch = self._client.batch()
        pending = 0
        coll = self._coll(collection)
        for doc_id, data in items:
            batch.set(coll.document(doc_id), dict(data))
            pending += 1
            written += 1
            if pending >= 400:
                batch.commit()
                batch = self._client.batch()
                pending = 0
        if pending:
            batch.commit()
        self._cache.pop(collection, None)
        return written

    def ping(self) -> bool:
        """Cheap connectivity check against the tenant root doc."""
        self._client.collection("tenants").document(self.tenant_id).get()
        return True


@lru_cache(maxsize=1)
def get_store() -> LocalStore | FirestoreStore:
    """Return the shared store instance for this process.

    DATA_BACKEND=local      → LocalStore (fixtures/)
    DATA_BACKEND=firestore  → FirestoreStore (tenants/{TENANT_ID}/...)
    """
    backend = (config.DATA_BACKEND or "local").strip().lower()
    if backend == "firestore":
        return FirestoreStore()
    if backend == "local":
        return LocalStore()
    raise ValueError(
        f"Unknown DATA_BACKEND={config.DATA_BACKEND!r}. Use 'local' or 'firestore'."
    )


def reset_store_cache() -> None:
    """Clear the cached store (tests / after env changes)."""
    get_store.cache_clear()
