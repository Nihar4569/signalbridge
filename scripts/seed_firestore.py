"""Seed Google Firestore from the fixtures (MANUAL step - needs cloud auth).

Do NOT run this until you have finished the Firebase setup in
docs/manual_work.md. It is a skeleton that shows how seeding will work.

    python -m scripts.seed_firestore
"""
from __future__ import annotations

import sys

from backend.core import config
from backend.core.store import LocalStore

COLLECTIONS = [
    "products", "locations", "stock_balances", "order_lines",
    "shipments", "supplier_offers", "partners", "events",
]


def main() -> None:
    if not config.GOOGLE_CLOUD_PROJECT:
        print("GOOGLE_CLOUD_PROJECT is not set. See docs/manual_work.md.")
        sys.exit(1)

    # Imported here so the project runs without google-cloud-firestore installed.
    from google.cloud import firestore  # type: ignore

    client = firestore.Client(project=config.GOOGLE_CLOUD_PROJECT)
    local = LocalStore()
    tenant = config.TENANT_ID

    for collection in COLLECTIONS:
        docs = local.list(collection)
        for doc in docs:
            doc_id = _doc_id(collection, doc)
            path = f"tenants/{tenant}/{collection}/{doc_id}"
            client.document(path).set(doc)
        print(f"Seeded {len(docs):>3} docs into {collection}")

    print("\nDone. Firestore now has the demo data.")


def _doc_id(collection: str, doc: dict) -> str:
    if collection == "products":
        return doc["sku"]
    if collection == "locations":
        return doc["location_id"]
    if collection == "stock_balances":
        return f"{doc['location_id']}__{doc['sku']}"
    if collection == "order_lines":
        return doc["line_id"]
    if collection == "shipments":
        return doc["shipment_id"]
    if collection == "supplier_offers":
        return doc["offer_id"]
    if collection == "partners":
        return doc["partner_id"]
    if collection == "events":
        return doc["event_id"]
    raise ValueError(f"No id rule for collection {collection}")


if __name__ == "__main__":
    main()
