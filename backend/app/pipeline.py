"""End-to-end pipeline: generate -> decide -> execute -> log -> report.

This is what both the CLI entrypoint (run.py) and the FastAPI
/api/run-batch route call.
"""
import json
import random

from app.audit_logger import append_record, reset_audit_log
from app.batch_generator import BATCH_REFERENCE_TIME, write_batch
from app.config import RANDOM_SEED, REPORT_JSON_FILE
from app.decision_engine import decide
from app.fraud_detection import annotate_suspected_fraud
from app.razorpay_client import get_client
from app.recovery_executor import execute_decision
from app.report import write_report
from app.run_history import append_snapshot


def run_pipeline(seed: int = RANDOM_SEED) -> dict:
    batch = write_batch(seed=seed)
    annotate_suspected_fraud(batch)  # SR6: cross-transaction pass before any single decision

    reset_audit_log()
    rng = random.Random(seed)
    client = get_client(rng=rng)

    # Decisions are evaluated as of the batch's reference "now" so cooldown
    # math stays reproducible run-to-run (see batch_generator docstring).
    decision_time = BATCH_REFERENCE_TIME

    for transaction in batch:
        decision = decide(transaction, now=decision_time, rng=rng)
        audit_record = execute_decision(transaction, decision, client)
        append_record(audit_record)

    report = write_report()
    report["client_mode"] = client.__class__.__name__
    with open(REPORT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    append_snapshot(report)
    return report


if __name__ == "__main__":
    report = run_pipeline()
    print(
        f"Processed {report['total_transactions']} transactions "
        f"({report['client_mode']}). Recovery rate: {report['recovery_rate_overall'] * 100:.1f}%"
    )
