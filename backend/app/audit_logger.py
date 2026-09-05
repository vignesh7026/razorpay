"""JSONL audit log: append-during-run, read-in-full for reporting/API.

FR8/FR9: one record per decision, and the single source of truth the
report is computed from -- report.py never derives a number the log
doesn't support.
"""
import json

from app.config import AUDIT_LOG_FILE, REPORTS_DIR


def reset_audit_log() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_LOG_FILE.write_text("", encoding="utf-8")


def append_record(record: dict) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def read_all_records() -> list[dict]:
    if not AUDIT_LOG_FILE.exists():
        return []
    records = []
    with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
