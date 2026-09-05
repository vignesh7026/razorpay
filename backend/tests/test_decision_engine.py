"""Every stopping rule (SR1-SR5) gets a direct, isolated test here -- this
is what makes 'engine correctness' a checkable claim per PRD section 8.1/8.2
rather than something only demonstrated by eyeballing a batch run.
"""
from datetime import timedelta

import pytest

from app.decision_engine import (
    INTERVENTION_CREATE_LINK,
    INTERVENTION_MANUAL_REVIEW,
    INTERVENTION_REAUTH,
    INTERVENTION_RETRY,
    decide,
)


# --- SR1: max retries -------------------------------------------------------

def test_sr1_max_retries_escalates(txn_factory, now):
    txn = txn_factory(failure_reason="insufficient_funds", prior_retry_count=3)
    decision = decide(txn, now=now)
    assert decision.escalate is True
    assert decision.stopping_rule_hit == "max_retries"
    assert decision.rule_fired == "max_retries_exceeded"
    assert decision.intervention == INTERVENTION_MANUAL_REVIEW


def test_sr1_below_ceiling_does_not_escalate(txn_factory, now):
    txn = txn_factory(failure_reason="insufficient_funds", prior_retry_count=2)
    decision = decide(txn, now=now)
    assert decision.stopping_rule_hit != "max_retries"


# --- SR2: cooldown window ----------------------------------------------------

def test_sr2_inside_cooldown_yields_pending(txn_factory, now):
    recent = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    txn = txn_factory(
        failure_reason="insufficient_funds",
        prior_retry_count=1,
        prior_retry_timestamps=[recent],
    )
    decision = decide(txn, now=now)
    assert decision.stopping_rule_hit == "cooldown_active"
    assert decision.escalate is False


def test_sr2_outside_cooldown_allows_retry(txn_factory, now):
    stale = (now - timedelta(hours=6)).isoformat().replace("+00:00", "Z")
    txn = txn_factory(
        failure_reason="insufficient_funds",
        prior_retry_count=1,
        prior_retry_timestamps=[stale],
    )
    decision = decide(txn, now=now)
    assert decision.stopping_rule_hit != "cooldown_active"
    assert decision.intervention == INTERVENTION_RETRY


def test_sr2_recurring_uses_longer_cooldown(txn_factory, now):
    # 6h ago clears the 2h non-recurring cooldown but not the 24h recurring one
    six_hours_ago = (now - timedelta(hours=6)).isoformat().replace("+00:00", "Z")
    txn = txn_factory(
        failure_reason="mandate_insufficient_funds",
        is_recurring=True,
        prior_retry_count=1,
        prior_retry_timestamps=[six_hours_ago],
    )
    decision = decide(txn, now=now)
    assert decision.stopping_rule_hit == "cooldown_active"


# --- SR3: mandate expiry never auto-retries ---------------------------------

def test_sr3_mandate_expired_always_reauth_and_escalates(txn_factory, now):
    txn = txn_factory(failure_reason="mandate_expired", is_recurring=True)
    decision = decide(txn, now=now)
    assert decision.intervention == INTERVENTION_REAUTH
    assert decision.escalate is True
    assert decision.stopping_rule_hit == "mandate_expired_no_auto_retry"
    assert decision.rule_fired == "mandate_expired_requires_reauth"


def test_sr3_overrides_even_with_no_prior_attempts(txn_factory, now):
    # mandate_expired must never fall through to a generic retry path,
    # regardless of retry history.
    txn = txn_factory(failure_reason="mandate_expired", is_recurring=True, prior_retry_count=0)
    decision = decide(txn, now=now)
    assert decision.intervention == INTERVENTION_REAUTH


# --- SR4: margin floor on incentives -----------------------------------------

def test_sr4_incentive_capped_by_thin_margin(txn_factory, now):
    # margin 6% - 5% safety buffer leaves only 1% headroom, below the 10% target
    txn = txn_factory(failure_reason="checkout_abandoned", product_margin_pct=0.06)
    decision = decide(txn, now=now)
    assert decision.incentive_pct < 0.10
    assert decision.incentive_pct == pytest.approx(0.01)


def test_sr4_zero_incentive_when_margin_below_buffer(txn_factory, now):
    txn = txn_factory(failure_reason="checkout_abandoned", product_margin_pct=0.02)
    decision = decide(txn, now=now)
    assert decision.incentive_pct == 0.0


def test_sr4_full_incentive_when_margin_is_healthy(txn_factory, now):
    txn = txn_factory(failure_reason="checkout_abandoned", product_margin_pct=0.40)
    decision = decide(txn, now=now)
    assert decision.incentive_pct == 0.10  # INCENTIVE_TARGET_PCT, uncapped


# --- SR5: mandatory high-value escalation ------------------------------------

def test_sr5_high_value_with_prior_failure_escalates(txn_factory, now):
    txn = txn_factory(failure_reason="card_declined", amount_inr=9999, prior_retry_count=1)
    decision = decide(txn, now=now)
    assert decision.escalate is True
    assert "high_value_prior_failure_escalation" in decision.rule_fired
    # the underlying intervention still runs -- SR5 loops in a human
    # alongside the normal recovery path, it doesn't replace it.
    assert decision.intervention == INTERVENTION_CREATE_LINK


def test_sr5_high_value_without_prior_failure_does_not_escalate(txn_factory, now):
    txn = txn_factory(failure_reason="card_declined", amount_inr=9999, prior_retry_count=0)
    decision = decide(txn, now=now)
    assert decision.escalate is False


def test_sr5_low_value_with_prior_failure_does_not_escalate(txn_factory, now):
    txn = txn_factory(failure_reason="card_declined", amount_inr=499, prior_retry_count=1)
    decision = decide(txn, now=now)
    assert decision.escalate is False


# --- table-driven mapping (FR4): each failure_reason routes correctly ------

def test_gateway_timeout_routes_to_immediate_retry(txn_factory, now):
    txn = txn_factory(failure_reason="gateway_timeout")
    decision = decide(txn, now=now)
    assert decision.intervention == INTERVENTION_RETRY
    assert decision.rule_fired == "gateway_timeout_immediate_retry"


def test_otp_timeout_routes_to_link_resend(txn_factory, now):
    txn = txn_factory(failure_reason="otp_timeout")
    decision = decide(txn, now=now)
    assert decision.intervention == INTERVENTION_CREATE_LINK
    assert decision.rule_fired == "otp_timeout_link_resend"


def test_card_declined_routes_to_alt_method_link(txn_factory, now):
    txn = txn_factory(failure_reason="card_declined")
    decision = decide(txn, now=now)
    assert decision.intervention == INTERVENTION_CREATE_LINK
    assert decision.rule_fired == "card_declined_alt_method_link"
