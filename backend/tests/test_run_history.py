"""Run history: append-only, sequential run_number, never mutates old
entries -- the Learning view's trend chart depends on both properties.
"""
import pytest

from app import run_history


@pytest.fixture(autouse=True)
def isolated_history_file(tmp_path, monkeypatch):
    monkeypatch.setattr(run_history, "RUN_HISTORY_FILE", tmp_path / "run_history.jsonl")
    yield


def _fake_report(**overrides):
    report = {
        "client_mode": "SimulatedRazorpayClient",
        "total_transactions": 120,
        "total_at_risk_inr": 100000,
        "total_recovered_inr": 30000,
        "recovery_rate_overall": 0.3,
        "counts_by_outcome": {"recovered": 40, "escalated": 30, "failed": 45, "pending_retry": 5},
    }
    report.update(overrides)
    return report


def test_empty_history_returns_empty_list():
    assert run_history.read_history() == []


def test_append_snapshot_assigns_sequential_run_numbers():
    s1 = run_history.append_snapshot(_fake_report())
    s2 = run_history.append_snapshot(_fake_report())
    s3 = run_history.append_snapshot(_fake_report())
    assert [s1["run_number"], s2["run_number"], s3["run_number"]] == [1, 2, 3]


def test_read_history_returns_all_snapshots_in_order():
    run_history.append_snapshot(_fake_report(recovery_rate_overall=0.2))
    run_history.append_snapshot(_fake_report(recovery_rate_overall=0.35))
    history = run_history.read_history()
    assert len(history) == 2
    assert [h["recovery_rate_overall"] for h in history] == [0.2, 0.35]


def test_snapshot_captures_the_fields_the_trend_chart_needs():
    snapshot = run_history.append_snapshot(_fake_report())
    for field in (
        "run_number", "timestamp", "client_mode", "total_transactions",
        "total_at_risk_inr", "total_recovered_inr", "recovery_rate_overall", "counts_by_outcome",
    ):
        assert field in snapshot


def test_reset_history_clears_all_snapshots():
    run_history.append_snapshot(_fake_report())
    run_history.append_snapshot(_fake_report())
    run_history.reset_history()
    assert run_history.read_history() == []


def test_append_never_mutates_earlier_snapshots():
    first = run_history.append_snapshot(_fake_report(recovery_rate_overall=0.1))
    run_history.append_snapshot(_fake_report(recovery_rate_overall=0.9))
    history = run_history.read_history()
    assert history[0]["recovery_rate_overall"] == 0.1
    assert history[0]["run_number"] == first["run_number"]
