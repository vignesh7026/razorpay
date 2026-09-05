"""Regression test for a real production bug: the frontend's
Promise.all([fetchReport(), fetchAuditLog()]) hits a cold backend with two
concurrent requests, both see "no report yet", and both used to call
run_pipeline() independently -- racing on the same files. Starlette runs
sync routes in a thread pool, so this is a genuine concurrency bug, not a
hypothetical one. ensure_pipeline_has_run() must serialize this: many
concurrent callers, run_pipeline() executes exactly once.
"""
import threading
import time
from unittest.mock import patch

import pytest

from app import main


@pytest.fixture(autouse=True)
def isolated_report_file(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "REPORT_JSON_FILE", tmp_path / "report.json")
    yield


def test_run_pipeline_executes_exactly_once_under_concurrency():
    call_count = 0
    lock_for_counter = threading.Lock()

    def fake_run_pipeline():
        nonlocal call_count
        with lock_for_counter:
            call_count += 1
        time.sleep(0.05)  # simulate real work, widening the race window
        main.REPORT_JSON_FILE.write_text("{}")
        return {}

    with patch.object(main, "run_pipeline", side_effect=fake_run_pipeline):
        threads = [threading.Thread(target=main.ensure_pipeline_has_run) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

    assert call_count == 1
    assert main.REPORT_JSON_FILE.exists()


def test_ensure_pipeline_has_run_is_a_noop_when_report_already_exists():
    main.REPORT_JSON_FILE.write_text("{}")
    with patch.object(main, "run_pipeline") as mock_run:
        main.ensure_pipeline_has_run()
    mock_run.assert_not_called()


def test_run_pipeline_exclusive_still_always_runs():
    """Unlike ensure_pipeline_has_run, the explicit /api/run-batch path must
    always actually re-run -- it just shouldn't overlap a concurrent lazy
    trigger, which the shared lock guarantees.
    """
    main.REPORT_JSON_FILE.write_text("{}")  # pretend a report already exists
    with patch.object(main, "run_pipeline", return_value={"ok": True}) as mock_run:
        result = main.run_pipeline_exclusive()
    mock_run.assert_called_once()
    assert result == {"ok": True}
