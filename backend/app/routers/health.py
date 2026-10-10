from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Liveness check used by Cloud Run and the dashboard."""
    return {"status": "ok"}
