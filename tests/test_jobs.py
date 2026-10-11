"""In-app weather/news timer and which locations it watches."""
import asyncio

from backend.core import config
from backend.core.store import LocalStore
from backend.worker.main import signal_scan_loop
from backend.worker.route_monitor import signal_scan_location_ids


def test_signal_scan_locations_include_port_and_destination(monkeypatch):
    store = LocalStore()
    monkeypatch.setattr("backend.worker.route_monitor.get_store", lambda: store)
    assert signal_scan_location_ids() == ["IN-JNPA", "WH-MUM"]


def test_signal_scan_loop_runs_until_stopped(monkeypatch):
    calls = {"n": 0}

    def fake_scan():
        calls["n"] += 1

    monkeypatch.setattr("backend.worker.main.scan_route_signals", fake_scan)
    monkeypatch.setattr(config, "SIGNAL_SCAN_INTERVAL_SECONDS", 0)

    async def run():
        stop = asyncio.Event()
        task = asyncio.create_task(signal_scan_loop(stop))
        for _ in range(50):
            if calls["n"] >= 1:
                break
            await asyncio.sleep(0.01)
        stop.set()
        await task

    asyncio.run(run())
    assert calls["n"] >= 1
