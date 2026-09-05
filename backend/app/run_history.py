"""Run history: an append-only snapshot log, one entry per real pipeline
run. Every other view in this project only ever shows "this run" -- the
bandit (app/bandit.py) is the one thing that persists and learns across
runs, but nothing visualizes whether that learning actually shows up in
the aggregate outcome. This module is what lets the Learning view prove it
does: recovery rate trending across successive runs is the one piece of
evidence "the agent gets better over time" that per-arm posteriors alone
don't provide.
"""
import json
from datetime import datetime, timezone

from app.config import REPORTS_DIR, RUN_HISTORY_FILE


def append_snapshot(report: dict) -> dict:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    existing = read_history()
    snapshot = {
        "run_number": len(existing) + 1,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "client_mode": report.get("client_mode"),
        "total_transactions": report["total_transactions"],
        "total_at_risk_inr": report["total_at_risk_inr"],
        "total_recovered_inr": report["total_recovered_inr"],
        "recovery_rate_overall": report["recovery_rate_overall"],
        "counts_by_outcome": report["counts_by_outcome"],
    }
    with open(RUN_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot) + "\n")
    return snapshot


def read_history() -> list[dict]:
    if not RUN_HISTORY_FILE.exists():
        return []
    snapshots = []
    with open(RUN_HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                snapshots.append(json.loads(line))
    return snapshots


def reset_history() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    RUN_HISTORY_FILE.write_text("", encoding="utf-8")
