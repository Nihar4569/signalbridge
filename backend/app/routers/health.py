from fastapi import APIRouter

from ...core import config
from ...core.store import get_store

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness check used by Cloud Run and the dashboard."""
    store = get_store()
    info = {
        "status": "ok",
        "data_backend": getattr(store, "backend_name", config.DATA_BACKEND),
        "tenant_id": config.TENANT_ID,
    }
    if store.backend_name == "firestore":
        try:
            store.ping()
            info["firestore"] = "reachable"
            info["project"] = config.GOOGLE_CLOUD_PROJECT or None
            info["emulator"] = bool(config.FIRESTORE_EMULATOR_HOST)
        except Exception as exc:  # noqa: BLE001 — surface connectivity issues
            info["status"] = "degraded"
            info["firestore"] = f"error: {type(exc).__name__}"
    return info
