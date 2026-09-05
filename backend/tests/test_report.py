"""report.py must never compute a number the audit log doesn't support
(FR9) -- these tests build a small, hand-checkable fake audit log and
assert every aggregate against arithmetic done independently here.
"""
from app.report import build_report


def audit_record(**overrides) -> dict:
    record = {
        "transaction_id": "txn_test",
        "failure_reason": "card_declined",
        "intervention_chosen": "create_payment_link",
        "rule_fired": "card_declined_alt_method_link",
        "outcome": "recovered",
        "stopping_rule_hit": False,
        "escalated_to_human": False,
        "amount_inr": 1000,
        "timestamp": "2026-08-27T12:00:00Z",
        "recovered_inr": 1000,
        "incentive_pct": 0.0,
        "product_margin_pct": 0.2,
        "is_recurring": False,
        "customer_name": "Test Customer",
        "product_name": "Test Product",
        "rule_notes": "",
        "execution": None,
    }
    record.update(overrides)
    return record


def test_totals_and_rate_are_arithmetically_correct():
    records = [
        audit_record(transaction_id="a", amount_inr=1000, recovered_inr=1000, outcome="recovered"),
        audit_record(transaction_id="b", amount_inr=500, recovered_inr=0, outcome="failed"),
    ]
    report = build_report(records)
    assert report["total_at_risk_inr"] == 1500
    assert report["total_recovered_inr"] == 1000
    assert report["recovery_rate_overall"] == round(1000 / 1500, 4)


def test_segmented_by_failure_reason_never_blends():
    records = [
        audit_record(transaction_id="a", failure_reason="card_declined", amount_inr=1000, recovered_inr=1000, outcome="recovered"),
        audit_record(transaction_id="b", failure_reason="gateway_timeout", amount_inr=1000, recovered_inr=0, outcome="failed"),
    ]
    report = build_report(records)
    assert report["by_failure_reason"]["card_declined"]["rate"] == 1.0
    assert report["by_failure_reason"]["gateway_timeout"]["rate"] == 0.0
    # segments are independent -- a 100% and a 0% segment must not average
    # into the overall rate looking like anything other than 50%
    assert report["recovery_rate_overall"] == 0.5


def test_counts_by_outcome_sum_to_total_records():
    records = [
        audit_record(transaction_id="a", outcome="recovered"),
        audit_record(transaction_id="b", outcome="escalated"),
        audit_record(transaction_id="c", outcome="pending_retry"),
        audit_record(transaction_id="d", outcome="failed"),
    ]
    report = build_report(records)
    assert sum(report["counts_by_outcome"].values()) == 4
    assert report["counts_by_outcome"] == {
        "recovered": 1, "escalated": 1, "pending_retry": 1, "failed": 1,
    }


def test_escalated_example_is_first_escalated_in_log_order_not_cherry_picked():
    records = [
        audit_record(transaction_id="a", outcome="recovered"),
        audit_record(transaction_id="b", outcome="escalated", amount_inr=777),
        audit_record(transaction_id="c", outcome="escalated", amount_inr=999999),
    ]
    report = build_report(records)
    # "b" comes first in log order -- must be picked over "c" even though
    # "c" has a flashier amount, proving the example isn't hand-selected.
    assert report["escalated_example"]["transaction_id"] == "b"


def test_no_escalated_case_yields_none_not_a_crash():
    records = [audit_record(transaction_id="a", outcome="recovered")]
    report = build_report(records)
    assert report["escalated_example"] is None


def test_baseline_comparison_excludes_structurally_unretryable_reasons():
    records = [
        audit_record(transaction_id="a", failure_reason="card_declined", amount_inr=1000, recovered_inr=1000),
        audit_record(transaction_id="b", failure_reason="mandate_expired", amount_inr=1000, recovered_inr=0, outcome="escalated"),
    ]
    report = build_report(records)
    bc = report["baseline_comparison"]
    # only the card_declined amount should count toward the naive baseline;
    # mandate_expired is excluded because a blind retry can't work on it
    expected_naive = 1000 * bc["naive_retry_success_rate_assumed"]
    assert bc["naive_generic_retry_recovered_inr"] == round(expected_naive, 2)
    assert bc["no_action_recovered_inr"] == 0.0


def test_baseline_uplift_is_agent_minus_naive():
    records = [
        audit_record(transaction_id="a", failure_reason="card_declined", amount_inr=1000, recovered_inr=1000),
    ]
    report = build_report(records)
    bc = report["baseline_comparison"]
    assert bc["uplift_vs_naive_retry_inr"] == round(
        bc["agent_recovered_inr"] - bc["naive_generic_retry_recovered_inr"], 2
    )


def test_margin_analysis_only_counts_recovered_records():
    records = [
        audit_record(transaction_id="a", amount_inr=1000, recovered_inr=1000, product_margin_pct=0.5, outcome="recovered"),
        audit_record(transaction_id="b", amount_inr=1000, recovered_inr=0, product_margin_pct=0.5, outcome="failed"),
    ]
    report = build_report(records)
    ma = report["margin_analysis"]
    assert ma["at_risk_profit_inr"] == 1000  # both transactions' amount * margin
    assert ma["recovered_profit_inr"] == 500  # only "a" contributes


def test_margin_analysis_incentive_cost_is_amount_minus_recovered():
    records = [
        audit_record(
            transaction_id="a", amount_inr=1000, recovered_inr=900,
            incentive_pct=0.10, product_margin_pct=0.3, outcome="recovered",
        ),
    ]
    report = build_report(records)
    assert report["margin_analysis"]["total_incentive_cost_inr"] == 100
