"""SR6: a lightweight, pattern-based abuse guardrail -- NOT a fraud model.

The PRD is explicit that general-purpose fraud/risk modeling is out of
scope (that's Track 02). This module does one narrow, transparent thing: it
flags an abnormal number of DISTINCT customers all hitting card_declined at
suspiciously low amounts inside a short rolling time window -- a classic
"card testing" traffic shape (an attacker validating stolen card numbers
with small probe charges) -- and nothing else. It never scores an
individual customer as fraudulent; it only flags a cross-transaction
*pattern*, which is why detection has to run as a pass over the whole batch
before any single transaction's decision is made, unlike every other rule
in decision_engine.py which only ever looks at one transaction at a time.
"""
from datetime import datetime, timedelta

from app.config import (
    CARD_TESTING_MAX_AMOUNT_INR,
    CARD_TESTING_MIN_DISTINCT_CUSTOMERS,
    CARD_TESTING_WINDOW_MINUTES,
)


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def detect_card_testing_pattern(batch: list[dict]) -> set[str]:
    """Returns the set of transaction_ids that fall inside a detected
    card-testing burst: a sliding window (CARD_TESTING_WINDOW_MINUTES) that
    contains at least CARD_TESTING_MIN_DISTINCT_CUSTOMERS distinct
    customer_ids, each a card_declined transaction at or under
    CARD_TESTING_MAX_AMOUNT_INR.
    """
    candidates = sorted(
        (
            t
            for t in batch
            if t["failure_reason"] == "card_declined" and t["amount_inr"] <= CARD_TESTING_MAX_AMOUNT_INR
        ),
        key=lambda t: t["occurred_at"],
    )
    if len(candidates) < CARD_TESTING_MIN_DISTINCT_CUSTOMERS:
        return set()

    window = timedelta(minutes=CARD_TESTING_WINDOW_MINUTES)
    flagged: set[str] = set()
    left = 0
    for right in range(len(candidates)):
        right_time = _parse_ts(candidates[right]["occurred_at"])
        while _parse_ts(candidates[left]["occurred_at"]) < right_time - window:
            left += 1
        window_slice = candidates[left : right + 1]
        distinct_customers = {t["customer_id"] for t in window_slice}
        if len(distinct_customers) >= CARD_TESTING_MIN_DISTINCT_CUSTOMERS:
            flagged.update(t["transaction_id"] for t in window_slice)

    return flagged


def annotate_suspected_fraud(batch: list[dict]) -> list[dict]:
    """Mutates and returns the batch, setting suspected_fraud=True on every
    transaction caught in a detected card-testing burst -- decide() reads
    this flag rather than re-running cross-transaction detection itself.
    """
    flagged_ids = detect_card_testing_pattern(batch)
    for txn in batch:
        txn["suspected_fraud"] = txn["transaction_id"] in flagged_ids
    return batch
