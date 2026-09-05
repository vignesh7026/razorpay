from app.customers import build_customer_detail, build_customer_summaries


def _record(**overrides):
    r = {
        "transaction_id": "txn_1",
        "customer_id": "cust_1",
        "customer_name": "Test Customer",
        "amount_inr": 1000,
        "recovered_inr": 0,
        "outcome": "failed",
        "timestamp": "2026-08-27T12:00:00Z",
        "source": None,
    }
    r.update(overrides)
    return r


def test_groups_records_by_customer_id_not_name():
    records = [
        _record(transaction_id="a", customer_id="cust_1", customer_name="Same Name"),
        _record(transaction_id="b", customer_id="cust_2", customer_name="Same Name"),
    ]
    summaries = build_customer_summaries(records)
    assert len(summaries) == 2


def test_repeat_flag_true_only_with_multiple_transactions():
    records = [
        _record(transaction_id="a", customer_id="cust_1"),
        _record(transaction_id="b", customer_id="cust_1"),
        _record(transaction_id="c", customer_id="cust_2"),
    ]
    summaries = {s["customer_id"]: s for s in build_customer_summaries(records)}
    assert summaries["cust_1"]["is_repeat"] is True
    assert summaries["cust_1"]["transaction_count"] == 2
    assert summaries["cust_2"]["is_repeat"] is False


def test_sorted_by_escalation_count_then_at_risk_amount():
    records = [
        _record(transaction_id="a", customer_id="cust_low", amount_inr=100, outcome="failed"),
        _record(transaction_id="b", customer_id="cust_high", amount_inr=50000, outcome="escalated"),
    ]
    summaries = build_customer_summaries(records)
    assert summaries[0]["customer_id"] == "cust_high"


def test_detail_returns_none_for_unknown_customer():
    assert build_customer_detail([_record()], "no_such_customer") is None


def test_detail_includes_transactions_sorted_by_timestamp():
    records = [
        _record(transaction_id="b", customer_id="cust_1", timestamp="2026-08-27T12:05:00Z"),
        _record(transaction_id="a", customer_id="cust_1", timestamp="2026-08-27T12:00:00Z"),
    ]
    detail = build_customer_detail(records, "cust_1")
    assert [t["transaction_id"] for t in detail["transactions"]] == ["a", "b"]


def test_has_live_activity_reflects_webhook_source():
    records = [_record(customer_id="cust_1", source="webhook")]
    summaries = build_customer_summaries(records)
    assert summaries[0]["has_live_activity"] is True
