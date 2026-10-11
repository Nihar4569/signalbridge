"""Seed Google Firestore from fixtures/ (needs cloud auth or emulator).

    # real cloud (ADC + GOOGLE_CLOUD_PROJECT)
    python -m scripts.seed_firestore

    # emulator
    set FIRESTORE_EMULATOR_HOST=localhost:8080
    python -m scripts.seed_firestore

Writes to: tenants/{TENANT_ID}/{collection}/{doc_id}
Validates each doc against backend.models before writing.
"""
from __future__ import annotations

import argparse
import sys

from backend.core import config
from backend.core.store import FirestoreStore, LocalStore, reset_store_cache
from backend.models import SEED_COLLECTIONS, doc_id_for, parse_doc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed Firestore from fixtures/")
    parser.add_argument(
        "--tenant",
        default=config.TENANT_ID,
        help=f"Tenant id (default: {config.TENANT_ID})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print paths only; do not write",
    )
    args = parser.parse_args(argv)

    local = LocalStore()
    total = 0
    prepared: dict[str, list[tuple[str, dict]]] = {}

    for collection in SEED_COLLECTIONS:
        items: list[tuple[str, dict]] = []
        for raw in local._load_file(collection):
            try:
                doc = parse_doc(collection, raw)
                did = doc_id_for(collection, doc)
            except Exception as exc:  # noqa: BLE001 — show which fixture failed
                print(f"  VALIDATION FAIL {collection}: {exc}")
                return 1
            items.append((did, doc))
            total += 1
        prepared[collection] = items
        print(f"  prepared {len(items):>3} docs → tenants/{args.tenant}/{collection}/")

    if args.dry_run:
        print(f"\nDry run OK — {total} documents would be written.")
        return 0

    if not config.GOOGLE_CLOUD_PROJECT and not config.FIRESTORE_EMULATOR_HOST:
        print(
            "Set GOOGLE_CLOUD_PROJECT (cloud) or FIRESTORE_EMULATOR_HOST (emulator).\n"
            "See docs/manual_work.md."
        )
        return 1

    store = FirestoreStore(tenant_id=args.tenant)
    store._client.collection("tenants").document(args.tenant).set(
        {
            "tenant_id": args.tenant,
            "name": "SignalBridge demo tenant",
            "seeded_from": "fixtures/",
        },
        merge=True,
    )

    written = 0
    for collection, items in prepared.items():
        n = store.batch_upsert(collection, items)
        written += n
        print(f"  seeded  {n:>3} docs → tenants/{args.tenant}/{collection}/")

    reset_store_cache()
    print(
        f"\nDone. Wrote {written} documents to project "
        f"{config.GOOGLE_CLOUD_PROJECT or '(emulator)'} "
        f"as tenant '{args.tenant}'."
    )
    print("Set DATA_BACKEND=firestore in .env to use this data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
