import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core import config
from ..worker.main import signal_scan_loop
from .routers import assistant, dashboard, fulfillments, health, incidents, plans, scan, signals


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Scan weather and news on a timer for as long as this process is up."""
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


@app.get("/")
def root() -> dict:
    return {"service": "signalbridge", "docs": "/docs", "health": "/health"}
