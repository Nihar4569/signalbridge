import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..core import config
from ..worker.main import signal_scan_loop
from .routers import (
    assistant,
    dashboard,
    decision_demo,
    fulfillments,
    health,
    incidents,
    plans,
    scan,
    signals,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Optional in-process scan timer, running while this process is up.

    Off by default (interval 0): to stay on the free tier we trigger scans from
    the frontend on page load instead (see routers/scan.py). In production this
    loop — or Google Cloud Scheduler calling POST /scan on a cron — keeps the
    live weather + news data fresh with no one watching.
    """
    stop = asyncio.Event()
    task = None
    if config.SIGNAL_SCAN_INTERVAL_SECONDS > 0:
        task = asyncio.create_task(signal_scan_loop(stop))
    yield
    stop.set()
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="SignalBridge API",
    version="0.1.0",
    description="Turn a disruption into a traceable inventory recovery plan.",
    lifespan=lifespan,
)

# Allow the local frontend (any origin) to call the API. Dev/prototype only —
# tighten this to the real dashboard URL before going public.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(incidents.router)
app.include_router(plans.router)
app.include_router(signals.router)
app.include_router(dashboard.router)
app.include_router(fulfillments.router)
app.include_router(assistant.router)
app.include_router(scan.router)
app.include_router(decision_demo.router)


# Serve the built dashboard (frontend/dist) from this same service when present,
# so one Cloud Run URL hosts both the API and the UI. Local dev without a build
# keeps the JSON root below.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@app.get("/", include_in_schema=False)
def root():
    if _DIST.is_dir():
        return FileResponse(str(_DIST / "index.html"))
    return {"service": "signalbridge", "docs": "/docs", "health": "/health"}


if _DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        target = _DIST / full_path
        if full_path and target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(_DIST / "index.html"))
