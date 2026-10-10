from fastapi import FastAPI

from .routers import health, incidents, plans

app = FastAPI(
    title="SignalBridge API",
    version="0.1.0",
    description="Turn a disruption into a traceable inventory recovery plan.",
)

app.include_router(health.router)
app.include_router(incidents.router)
app.include_router(plans.router)


@app.get("/")
def root() -> dict:
    return {"service": "signalbridge", "docs": "/docs", "health": "/health"}
