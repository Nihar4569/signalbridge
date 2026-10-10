from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import health, incidents, plans, signals

app = FastAPI(
    title="SignalBridge API",
    version="0.1.0",
    description="Turn a disruption into a traceable inventory recovery plan.",
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


@app.get("/")
def root() -> dict:
    return {"service": "signalbridge", "docs": "/docs", "health": "/health"}
