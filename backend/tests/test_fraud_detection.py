"""SR6: card-testing pattern detection -- a cross-transaction pass, unlike
every other rule which only ever looks at one transaction at a time.
"""
from datetime import timedelta

from app.batch_generator import BATCH_REFERENCE_TIME
from app.decision_engine import decide
from app.fraud_detection import annotate_suspected_fraud, detect_card_testing_pattern


def _card_declined_txn(txn_id, customer_id, amount, minutes_ago, **overrides):
    ts = (BATCH_REFERENCE_TIME - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")
    txn = {
        "transaction_id": txn_id,
        "customer_id": customer_id,
        "customer_name": "Test",
        "sku": "SKU-1",
        "product_name": "P",
        "amount_inr": amount,
        "product_margin_pct": 0.2,
        "is_recurring": False,
        "failure_reason": "card_declined",
        "occurred_at": ts,
        "prior_retry_count": 0,
        "prior_retry_timestamps": [],
        "status": "at_risk",
    }
    txn.update(overrides)
    return txn


def test_burst_of_distinct_customers_low_amount_tight_window_is_flagged():
    batch = [_card_declined_txn(f"txn_{i}", f"cust_{i}", 199, minutes_ago=i) for i in range(5)]
    flagged = detect_card_testing_pattern(batch)
    assert flagged == {t["transaction_id"] for t in batch}


def test_same_customer_repeating_is_not_flagged():
    # one customer, many attempts -- not a card-testing shape (only 1 distinct customer)
    batch = [_card_declined_txn(f"txn_{i}", "cust_same", 199, minutes_ago=i) for i in range(6)]
    assert detect_card_testing_pattern(batch) == set()


def test_high_amount_burst_is_not_flagged():
    batch = [_card_declined_txn(f"txn_{i}", f"cust_{i}", 9999, minutes_ago=i) for i in range(6)]
    assert detect_card_testing_pattern(batch) == set()


def test_distinct_customers_spread_far_apart_in_time_is_not_flagged():
    batch = [_card_declined_txn(f"txn_{i}", f"cust_{i}", 199, minutes_ago=i * 60) for i in range(6)]
    assert detect_card_testing_pattern(batch) == set()


def test_below_threshold_distinct_customer_count_is_not_flagged():
    batch = [_card_declined_txn(f"txn_{i}", f"cust_{i}", 199, minutes_ago=i) for i in range(3)]
    assert detect_card_testing_pattern(batch) == set()


def test_non_card_declined_transactions_are_ignored():
    batch = [
        _card_declined_txn(f"txn_{i}", f"cust_{i}", 199, minutes_ago=i, failure_reason="gateway_timeout")
        for i in range(6)
    ]
    assert detect_card_testing_pattern(batch) == set()


def test_annotate_sets_flag_on_batch_in_place():
    batch = [_card_declined_txn(f"txn_{i}", f"cust_{i}", 199, minutes_ago=i) for i in range(5)]
    batch.append(_card_declined_txn("txn_clean", "cust_clean", 9999, minutes_ago=0))
    annotate_suspected_fraud(batch)
    assert all(t["suspected_fraud"] for t in batch[:5])
    assert batch[-1]["suspected_fraud"] is False


def test_sr6_overrides_every_other_rule_in_decide():
    txn = _card_declined_txn("txn_x", "cust_x", 199, minutes_ago=0, suspected_fraud=True, prior_retry_count=0)
    decision = decide(txn, now=BATCH_REFERENCE_TIME)
    assert decision.intervention == "block_and_escalate"
    assert decision.escalate is True
    assert decision.stopping_rule_hit == "suspected_fraud"
    assert decision.rule_fired == "suspected_card_testing_blocked"


def test_sr6_wins_even_for_mandate_expired():
    txn = _card_declined_txn(
        "txn_y", "cust_y", 199, minutes_ago=0,
        failure_reason="mandate_expired", is_recurring=True, suspected_fraud=True,
    )
    decision = decide(txn, now=BATCH_REFERENCE_TIME)
    # SR6 must win even over SR3, which would otherwise always claim mandate_expired
    assert decision.rule_fired == "suspected_card_testing_blocked"


def test_decide_without_suspected_fraud_flag_is_unaffected():
    txn = _card_declined_txn("txn_z", "cust_z", 199, minutes_ago=0)
    decision = decide(txn, now=BATCH_REFERENCE_TIME)
    assert decision.rule_fired == "card_declined_alt_method_link"
