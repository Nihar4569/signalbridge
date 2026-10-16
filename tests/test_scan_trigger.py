"""The frontend-triggered scan: throttling and the running-guard."""
from backend.worker import main as worker


def _reset():
    worker._scan_state.update(running=False, started_at=None, finished_at=None,
                              last_summary=None, last_error=None)


def fake_scan():
    return [{"location_id": "A", "news_count": 2}, {"location_id": "B", "news_count": 1}]


def test_first_trigger_runs_and_records_summary():
    _reset()
    out = worker.trigger_scan(scan_fn=fake_scan, background=False)
    assert out["status"] == "started"
    assert out["running"] is False  # finished (ran inline)
    assert out["last_summary"] == {"locations_scanned": 2, "news_found": 3}


def test_refresh_within_window_is_throttled():
    _reset()
    worker.trigger_scan(scan_fn=fake_scan, background=False, min_interval=600)
    out = worker.trigger_scan(scan_fn=fake_scan, background=False, min_interval=600)
    assert out["status"] == "fresh"
    assert out["seconds_since_last_scan"] is not None


def test_zero_interval_allows_immediate_rescan():
    _reset()
    worker.trigger_scan(scan_fn=fake_scan, background=False, min_interval=0)
    out = worker.trigger_scan(scan_fn=fake_scan, background=False, min_interval=0)
    assert out["status"] == "started"


def test_running_guard_blocks_a_second_scan():
    _reset()
    worker._scan_state["running"] = True
    out = worker.trigger_scan(scan_fn=fake_scan, background=False)
    assert out["status"] == "running"


def test_a_failing_scan_never_raises():
    _reset()

    def boom():
        raise RuntimeError("network down")

    out = worker.trigger_scan(scan_fn=boom, background=False, min_interval=0)
    assert out["status"] == "started"
    assert out["last_error"] == "RuntimeError"
    assert worker._scan_state["running"] is False
