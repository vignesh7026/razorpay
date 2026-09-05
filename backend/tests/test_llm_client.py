"""SimulatedLLMClient must stay fully functional with no API key configured
-- these tests exercise the keyword-matched Q&A fallback and the one-pager
HTML template renderer without ever hitting the network.
"""
import pytest

from app.llm_client import SimulatedLLMClient
from app.report import build_report


def _sample_records():
    return [
        {
            "transaction_id": "txn_a",
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
            "product_margin_pct": 0.3,
            "is_recurring": False,
            "customer_name": "A",
            "product_name": "P",
            "rule_notes": "",
            "execution": None,
        },
        {
            "transaction_id": "txn_b",
            "failure_reason": "mandate_expired",
            "intervention_chosen": "request_reauthorization",
            "rule_fired": "mandate_expired_requires_reauth",
            "outcome": "escalated",
            "stopping_rule_hit": "mandate_expired_no_auto_retry",
            "escalated_to_human": True,
            "amount_inr": 2000,
            "timestamp": "2026-08-27T12:01:00Z",
            "recovered_inr": 0,
            "incentive_pct": 0.0,
            "product_margin_pct": 0.3,
            "is_recurring": True,
            "customer_name": "B",
            "product_name": "Q",
            "rule_notes": "escalated notes",
            "execution": None,
        },
    ]


@pytest.fixture
def client():
    return SimulatedLLMClient()


@pytest.fixture
def report():
    return build_report(_sample_records())


def test_answer_recovery_rate_question(client, report):
    result = client.answer_question("what's the recovery rate?", report, _sample_records(), [])
    assert result.provider == "simulated"
    assert "33.3%" in result.answer


def test_answer_escalation_question_cites_example(client, report):
    result = client.answer_question("which cases were escalated?", report, _sample_records(), [])
    assert "txn_b" in result.answer
    assert "1" in result.answer  # one escalated count


def test_answer_baseline_question(client, report):
    result = client.answer_question("what's the uplift over the naive baseline?", report, _sample_records(), [])
    assert "uplift" in result.answer.lower()


def test_answer_margin_question(client, report):
    result = client.answer_question("how much profit was recovered?", report, _sample_records(), [])
    assert "profit" in result.answer.lower()


def test_answer_unrecognized_question_gives_honest_fallback(client, report):
    result = client.answer_question("what's the weather today?", report, _sample_records(), [])
    assert "simulated fallback" in result.answer.lower()
    assert "ANTHROPIC_API_KEY" in result.answer


def test_onepager_html_contains_real_numbers(client, report):
    result = client.generate_onepager_html(report)
    assert result.provider == "simulated"
    assert "<!doctype html>" in result.html.lower()
    assert "txn_b" in result.html  # the escalated example is included in full
    assert "card_declined" in result.html


def test_onepager_html_has_no_escalated_case_message_when_none_exist(client):
    report = build_report([_sample_records()[0]])  # only the recovered record
    result = client.generate_onepager_html(report)
    assert "No escalated case" in result.html
