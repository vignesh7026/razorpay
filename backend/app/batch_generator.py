"""Synthetic at-risk transaction batch generator.

Models the seven failure_reason categories from PRD section 6.1 with a
realistic-looking Indian e-commerce/subscription distribution, and
deliberately pre-seeds a subset of records with prior retry history so the
stopping rules (max retries, cooldown windows, mandate expiry) have real
cases to fire on in the demo run rather than only theoretical ones
(PRD section 13 risk mitigation).

Reproducible: seeded with RANDOM_SEED (PRD section 8.2).
"""
import json
import random
from datetime import datetime, timedelta, timezone

from app.config import (
    BATCH_FILE,
    BATCH_SIZE,
    CARD_TESTING_MAX_AMOUNT_INR,
    CARD_TESTING_MIN_DISTINCT_CUSTOMERS,
    DATA_DIR,
    RANDOM_SEED,
)

# Fixed anchor so "occurred_at" / retry timestamps are reproducible across
# runs (real-world "now" would break the seeded determinism guarantee).
BATCH_REFERENCE_TIME = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)

# failure_reason -> (weight, is_recurring)
FAILURE_DISTRIBUTION = {
    "card_declined": (0.28, False),
    "checkout_abandoned": (0.20, False),
    "insufficient_funds": (0.15, False),
    "gateway_timeout": (0.10, False),
    "otp_timeout": (0.10, False),
    "mandate_insufficient_funds": (0.11, True),
    "mandate_expired": (0.06, True),
}

PRODUCTS = [
    ("SKU-1001", "Wireless Earbuds Pro", 0.22),
    ("SKU-1002", "Smart Fitness Band", 0.18),
    ("SKU-1003", "Monthly Meal Kit Subscription", 0.12),
    ("SKU-1004", "Premium OTT Plan", 0.55),
    ("SKU-1005", "Yoga Mat Deluxe", 0.30),
    ("SKU-1006", "Electric Kettle 1.5L", 0.15),
    ("SKU-1007", "Cloud Storage 1TB - Annual", 0.62),
    ("SKU-1008", "Running Shoes Elite", 0.25),
    ("SKU-1009", "Skincare Combo Set", 0.35),
    ("SKU-1010", "Home Gym Resistance Bands", 0.28),
    ("SKU-1011", "Language Learning Pro - Yearly", 0.58),
    ("SKU-1012", "Bluetooth Speaker Mini", 0.20),
    ("SKU-1013", "Organic Grocery Box - Weekly", 0.10),
    ("SKU-1014", "Laptop Backpack Urban", 0.24),
    ("SKU-1015", "Air Purifier Compact", 0.16),
    ("SKU-1016", "Kids Learning Tablet", 0.19),
    ("SKU-1017", "Insurance Premium - Health Add-on", 0.08),
    ("SKU-1018", "Coffee Subscription - Monthly", 0.14),
    ("SKU-1019", "Smart Watch Series X", 0.21),
    ("SKU-1020", "Ergonomic Office Chair", 0.27),
]

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Krishna", "Ishaan",
    "Ananya", "Diya", "Saanvi", "Myra", "Aadhya", "Kavya", "Riya", "Priya",
    "Rohan", "Kabir", "Neha", "Pooja", "Sanjay", "Meera", "Aisha", "Farhan",
]
LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Gupta", "Menon", "Rao",
    "Patel", "Singh", "Kulkarni", "Chatterjee", "Bose", "Pillai", "Joshi",
]


def _weighted_choice(rng: random.Random, distribution: dict):
    reasons = list(distribution.keys())
    weights = [distribution[r][0] for r in reasons]
    return rng.choices(reasons, weights=weights, k=1)[0]


def _amount_for(rng: random.Random, is_recurring: bool) -> int:
    if is_recurring:
        # subscription / mandate amounts cluster lower, with occasional
        # higher-value annual plans
        base = rng.choice([149, 199, 299, 499, 999, 1999, 4999, 9999, 14999])
    else:
        base = rng.choice(
            [199, 349, 499, 799, 1299, 1499, 2499, 3999, 5999, 7999, 9999, 15999, 24999]
        )
    jitter = rng.randint(-20, 20)
    return max(99, base + jitter)


def _make_retry_history(rng: random.Random, occurred_at: datetime, count: int,
                         spacing_hours_choices: list[int]) -> list[str]:
    timestamps = []
    cursor = occurred_at
    for _ in range(count):
        gap = rng.choice(spacing_hours_choices)
        cursor = cursor - timedelta(hours=gap)
        timestamps.append(cursor.isoformat().replace("+00:00", "Z"))
    return list(reversed(timestamps))


def generate_batch(size: int = BATCH_SIZE, seed: int = RANDOM_SEED) -> list[dict]:
    rng = random.Random(seed)
    transactions = []

    for i in range(size):
        failure_reason = _weighted_choice(rng, FAILURE_DISTRIBUTION)
        is_recurring = FAILURE_DISTRIBUTION[failure_reason][1]

        sku, product_name, margin = rng.choice(PRODUCTS)
        margin_jitter = rng.uniform(-0.03, 0.03)
        product_margin_pct = round(min(0.65, max(0.05, margin + margin_jitter)), 3)

        amount_inr = _amount_for(rng, is_recurring)

        customer_name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"

        # --- deliberate retry-history seeding (PRD 13 risk mitigation) ---
        # ~28% of records carry prior attempts so cooldown / max-retry /
        # high-value-escalation rules have concrete cases to fire on.
        #
        # Retry timestamps are anchored backward from BATCH_REFERENCE_TIME
        # ("now", when the agent is deciding) rather than from occurred_at,
        # since cooldown (SR2) is evaluated as a gap from "now" -- an
        # attempt from days ago is stale regardless of when the original
        # failure occurred. occurred_at is then placed before the earliest
        # retry so the timeline stays causally consistent.
        prior_retry_count = 0
        prior_retry_timestamps: list[str] = []
        roll = rng.random()

        if failure_reason == "mandate_expired":
            # mandate expiry is inherently a "prior lapse" case
            prior_retry_count = rng.choice([0, 1, 2])
            if prior_retry_count:
                prior_retry_timestamps = _make_retry_history(
                    rng, BATCH_REFERENCE_TIME, prior_retry_count, [30, 40, 50]
                )
        elif roll < 0.10:
            # exhausted retries -> exercises SR1 max-retry escalation
            prior_retry_count = 3
            spacing = [26, 30] if is_recurring else [1, 3, 5]
            prior_retry_timestamps = _make_retry_history(
                rng, BATCH_REFERENCE_TIME, prior_retry_count, spacing
            )
        elif roll < 0.22:
            # 1-2 prior attempts, spaced OUTSIDE the cooldown window ->
            # engine should attempt another retry
            prior_retry_count = rng.choice([1, 2])
            spacing = [30, 36, 48] if is_recurring else [3, 4, 6]
            prior_retry_timestamps = _make_retry_history(
                rng, BATCH_REFERENCE_TIME, prior_retry_count, spacing
            )
        elif roll < 0.32:
            # 1 prior attempt, spaced INSIDE the cooldown window ->
            # exercises SR2 pending_retry
            prior_retry_count = 1
            spacing = [4, 8, 12] if is_recurring else [0, 1]
            prior_retry_timestamps = _make_retry_history(
                rng, BATCH_REFERENCE_TIME, prior_retry_count, spacing
            )

        if prior_retry_timestamps:
            earliest_retry = _parse_batch_ts(prior_retry_timestamps[0])
            occurred_at = earliest_retry - timedelta(hours=rng.randint(6, 72))
        else:
            occurred_at = BATCH_REFERENCE_TIME - timedelta(
                hours=rng.randint(1, 14 * 24), minutes=rng.randint(0, 59)
            )

        # Nudge some high-amount + prior-failure records to exercise SR5
        # (mandatory escalation above the rupee threshold).
        if prior_retry_count >= 1 and rng.random() < 0.35 and amount_inr < 5000:
            amount_inr = rng.choice([5499, 6999, 8999, 11999, 17999])

        transactions.append(
            {
                "transaction_id": f"txn_{i + 1:04d}",
                "customer_id": f"cust_{(i % 87) + 1:04d}",
                "customer_name": customer_name,
                "sku": sku,
                "product_name": product_name,
                "amount_inr": amount_inr,
                "product_margin_pct": product_margin_pct,
                "is_recurring": is_recurring,
                "failure_reason": failure_reason,
                "occurred_at": occurred_at.isoformat().replace("+00:00", "Z"),
                "prior_retry_count": prior_retry_count,
                "prior_retry_timestamps": prior_retry_timestamps,
                "status": "at_risk",
            }
        )

    _guarantee_cooldown_coverage(rng, transactions)
    _seed_card_testing_burst(rng, transactions)
    return transactions


def _seed_card_testing_burst(rng: random.Random, transactions: list[dict]) -> None:
    """Repurposes a handful of existing card_declined records into a tight
    burst -- distinct customers, low amounts, minutes apart -- so SR6 (the
    card-testing guardrail in app.fraud_detection) has a real pattern to
    catch in the seeded batch, not just a theoretical one (same convention
    as _guarantee_cooldown_coverage above, per PRD section 11).
    """
    burst_size = CARD_TESTING_MIN_DISTINCT_CUSTOMERS + 1
    candidates = [t for t in transactions if t["failure_reason"] == "card_declined"][:burst_size]
    if len(candidates) < burst_size:
        return

    low_amounts = [99, 149, 199, 249, 299]
    for i, txn in enumerate(candidates):
        txn["customer_id"] = f"cust_cardtest_{i:02d}"
        txn["amount_inr"] = rng.choice(low_amounts)
        txn["occurred_at"] = (BATCH_REFERENCE_TIME - timedelta(minutes=i * 2)).isoformat().replace("+00:00", "Z")
        txn["prior_retry_count"] = 0
        txn["prior_retry_timestamps"] = []


def _guarantee_cooldown_coverage(rng: random.Random, transactions: list[dict]) -> None:
    """Force at least two cooldown-eligible failure types into an
    inside-cooldown state so SR2 (pending_retry) demonstrably fires at
    least once, rather than leaving it to chance whether the weighted
    random draw happens to land there (PRD section 11 requirement that
    every stopping rule fires at least once in the batch run).
    """
    targets = {"insufficient_funds": False, "mandate_insufficient_funds": False}
    for txn in transactions:
        reason = txn["failure_reason"]
        if reason in targets and not targets[reason]:
            spacing_hours = 6 if txn["is_recurring"] else 1
            txn["prior_retry_count"] = 1
            txn["prior_retry_timestamps"] = _make_retry_history(
                rng, BATCH_REFERENCE_TIME, 1, [spacing_hours]
            )
            occurred_at = _parse_batch_ts(txn["prior_retry_timestamps"][0]) - timedelta(
                hours=rng.randint(6, 72)
            )
            txn["occurred_at"] = occurred_at.isoformat().replace("+00:00", "Z")
            targets[reason] = True
        if all(targets.values()):
            break


def _parse_batch_ts(ts: str):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def write_batch(size: int = BATCH_SIZE, seed: int = RANDOM_SEED) -> list[dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    batch = generate_batch(size=size, seed=seed)
    with open(BATCH_FILE, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2)
    return batch


def read_batch() -> list[dict]:
    """Reads the currently persisted batch (from the last run_pipeline call),
    generating one first if none exists yet. Used by app.simulate, which
    must run against the exact same batch the real report was computed
    from -- never a freshly regenerated one -- for the "what-if" delta to
    be a fair comparison.
    """
    if not BATCH_FILE.exists():
        return write_batch()
    with open(BATCH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    batch = write_batch()
    print(f"Wrote {len(batch)} synthetic transactions to {BATCH_FILE}")
