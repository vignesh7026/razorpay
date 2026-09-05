from datetime import datetime, timedelta, timezone

import pytest

NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def now():
    return NOW


def make_txn(**overrides) -> dict:
    """Builds a transaction dict with the schema decision_engine expects,
    overridable per test so each test only specifies what it cares about.
    """
    txn = {
        "transaction_id": "txn_test",
        "customer_id": "cust_test",
        "customer_name": "Test Customer",
        "sku": "SKU-TEST",
        "product_name": "Test Product",
        "amount_inr": 1000,
        "product_margin_pct": 0.30,
        "is_recurring": False,
        "failure_reason": "card_declined",
        "occurred_at": (NOW - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "prior_retry_count": 0,
        "prior_retry_timestamps": [],
        "status": "at_risk",
    }
    txn.update(overrides)
    return txn


@pytest.fixture
def txn_factory():
    return make_txn
