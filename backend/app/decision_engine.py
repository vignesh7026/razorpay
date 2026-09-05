"""Decision engine: transaction -> exactly one intervention decision.

FR3: returns {intervention, rule_fired, escalate, stopping_rule_hit}.
FR4: the failure_reason -> default intervention mapping is table-driven
     (FAILURE_HANDLERS below), not scattered per-transaction logic.
FR5: every decision names the specific rule that fired.

Rule priority (checked in order, first match for the "global override"
tier wins before the per-failure_reason handler runs):
  0. SR6  suspected card-testing pattern -> block + escalate, no exceptions
  1. SR3  mandate_expired always -> request_reauthorization, always escalate
  2. SR1  prior_retry_count >= MAX_RETRIES -> escalate, no more auto-retry
  3. SR5  amount above threshold AND a prior attempt already failed -> escalate
           (the normal intervention still runs; a human is looped in too)
  4. per-failure_reason handler (table below), which itself applies SR2
     (cooldown) and SR4 (margin-floor-capped incentive) where relevant.

Every threshold used below (MAX_RETRIES, cooldown hours, the escalation
amount, the incentive target/margin buffer) is read from a PolicyConfig,
which defaults to the live app.config constants but can be overridden --
see app.simulate, which re-runs this exact function with hypothetical
thresholds to power the dashboard's "what-if" guardrail simulator without
ever touching the real persisted run.
"""
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import (
    ESCALATION_AMOUNT_THRESHOLD_INR,
    INCENTIVE_TARGET_PCT,
    MARGIN_SAFETY_BUFFER_PCT,
    MAX_RETRIES,
    NON_RECURRING_COOLDOWN_HOURS,
    RECURRING_COOLDOWN_HOURS,
)
from app import bandit

INTERVENTION_CREATE_LINK = "create_payment_link"
INTERVENTION_RETRY = "attempt_recharge"
INTERVENTION_REAUTH = "request_reauthorization"
INTERVENTION_MANUAL_REVIEW = "manual_review"
INTERVENTION_BLOCKED = "block_and_escalate"

_DEFAULT_RNG = random.Random()


@dataclass
class PolicyConfig:
    """Every guardrail threshold the decision engine reads, bundled so the
    simulator can pass one hypothetical bundle through `decide()` instead of
    monkeypatching module constants.
    """

    max_retries: int = MAX_RETRIES
    recurring_cooldown_hours: int = RECURRING_COOLDOWN_HOURS
    non_recurring_cooldown_hours: int = NON_RECURRING_COOLDOWN_HOURS
    escalation_amount_threshold_inr: float = ESCALATION_AMOUNT_THRESHOLD_INR
    incentive_target_pct: float = INCENTIVE_TARGET_PCT
    margin_safety_buffer_pct: float = MARGIN_SAFETY_BUFFER_PCT


_DEFAULT_POLICY = PolicyConfig()


@dataclass
class Decision:
    intervention: str
    rule_fired: str
    escalate: bool
    stopping_rule_hit: "str | bool"
    incentive_pct: float = 0.0
    intervention_variant: Optional[str] = None
    notes: str = ""


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _last_attempt_at(transaction: dict) -> Optional[datetime]:
    timestamps = transaction.get("prior_retry_timestamps") or []
    if not timestamps:
        return None
    return max(_parse_ts(t) for t in timestamps)


def _cooldown_hours(transaction: dict, policy: PolicyConfig) -> int:
    return policy.recurring_cooldown_hours if transaction["is_recurring"] else policy.non_recurring_cooldown_hours


def _in_cooldown(transaction: dict, now: datetime, policy: PolicyConfig) -> bool:
    last = _last_attempt_at(transaction)
    if last is None:
        return False
    return now - last < timedelta(hours=_cooldown_hours(transaction, policy))


def _bounded_incentive_pct(margin_pct: float, policy: PolicyConfig) -> float:
    """SR4: an incentive can never be issued at or below the margin floor."""
    max_allowed = margin_pct - policy.margin_safety_buffer_pct
    return round(min(policy.incentive_target_pct, max(max_allowed, 0.0)), 4)


# ---- per-failure_reason handlers (FR4: table-driven) ----------------------

def _handle_checkout_abandoned(txn: dict, now: datetime, rng: random.Random, policy: PolicyConfig) -> Decision:
    incentive = _bounded_incentive_pct(txn["product_margin_pct"], policy)
    variant = bandit.select_variant("checkout_abandoned", rng)
    return Decision(
        intervention=INTERVENTION_CREATE_LINK,
        rule_fired="checkout_abandoned_incentive_link",
        escalate=False,
        stopping_rule_hit=False,
        incentive_pct=incentive,
        intervention_variant=variant,
        notes=f"Payment-link resend with a margin-floor-capped incentive (SR4). Message variant: {bandit.VARIANT_LABELS.get(variant, variant)}.",
    )


def _handle_card_declined(txn: dict, now: datetime, rng: random.Random, policy: PolicyConfig) -> Decision:
    variant = bandit.select_variant("card_declined", rng)
    return Decision(
        intervention=INTERVENTION_CREATE_LINK,
        rule_fired="card_declined_alt_method_link",
        escalate=False,
        stopping_rule_hit=False,
        intervention_variant=variant,
        notes=f"Resend payment link, prompting an alternate payment method. Message variant: {bandit.VARIANT_LABELS.get(variant, variant)}.",
    )


def _handle_insufficient_funds(txn: dict, now: datetime, rng: random.Random, policy: PolicyConfig) -> Decision:
    if _in_cooldown(txn, now, policy):
        return Decision(
            intervention=INTERVENTION_RETRY,
            rule_fired="insufficient_funds_cooldown_active",
            escalate=False,
            stopping_rule_hit="cooldown_active",
            notes=f"Within {_cooldown_hours(txn, policy)}h cooldown since last attempt (SR2); no auto-retry yet.",
        )
    return Decision(
        intervention=INTERVENTION_RETRY,
        rule_fired="insufficient_funds_delayed_retry",
        escalate=False,
        stopping_rule_hit=False,
        notes="Cooldown elapsed; delayed retry attempted.",
    )


def _handle_gateway_timeout(txn: dict, now: datetime, rng: random.Random, policy: PolicyConfig) -> Decision:
    return Decision(
        intervention=INTERVENTION_RETRY,
        rule_fired="gateway_timeout_immediate_retry",
        escalate=False,
        stopping_rule_hit=False,
        notes="Transient gateway error; single immediate retry, no cooldown.",
    )


def _handle_otp_timeout(txn: dict, now: datetime, rng: random.Random, policy: PolicyConfig) -> Decision:
    variant = bandit.select_variant("otp_timeout", rng)
    return Decision(
        intervention=INTERVENTION_CREATE_LINK,
        rule_fired="otp_timeout_link_resend",
        escalate=False,
        stopping_rule_hit=False,
        intervention_variant=variant,
        notes=f"Customer likely missed the OTP window; resend a fresh payment link. Message variant: {bandit.VARIANT_LABELS.get(variant, variant)}.",
    )


def _handle_mandate_insufficient_funds(txn: dict, now: datetime, rng: random.Random, policy: PolicyConfig) -> Decision:
    if _in_cooldown(txn, now, policy):
        return Decision(
            intervention=INTERVENTION_RETRY,
            rule_fired="mandate_cooldown_active",
            escalate=False,
            stopping_rule_hit="cooldown_active",
            notes=f"Within {_cooldown_hours(txn, policy)}h recurring-debit cooldown (SR2); no auto-retry yet.",
        )
    return Decision(
        intervention=INTERVENTION_RETRY,
        rule_fired="mandate_insufficient_funds_capped_retry",
        escalate=False,
        stopping_rule_hit=False,
        notes="Cooldown elapsed; capped retry attempted (subject to SR1 max-retry ceiling).",
    )


FAILURE_HANDLERS = {
    "checkout_abandoned": _handle_checkout_abandoned,
    "card_declined": _handle_card_declined,
    "insufficient_funds": _handle_insufficient_funds,
    "gateway_timeout": _handle_gateway_timeout,
    "otp_timeout": _handle_otp_timeout,
    "mandate_insufficient_funds": _handle_mandate_insufficient_funds,
    # mandate_expired is handled entirely by the SR3 global override below.
}


def decide(
    transaction: dict,
    now: Optional[datetime] = None,
    rng: Optional[random.Random] = None,
    policy: Optional[PolicyConfig] = None,
) -> Decision:
    now = now or datetime.now(timezone.utc)
    rng = rng or _DEFAULT_RNG
    policy = policy or _DEFAULT_POLICY

    # --- SR6: suspected card-testing pattern always wins ------------------
    if transaction.get("suspected_fraud"):
        return Decision(
            intervention=INTERVENTION_BLOCKED,
            rule_fired="suspected_card_testing_blocked",
            escalate=True,
            stopping_rule_hit="suspected_fraud",
            notes=(
                "Part of a cross-transaction pattern flagged by the card-testing guardrail "
                "(many distinct customers, low amounts, tight time window) -- this is a narrow "
                "pattern check, not a fraud model. No automated recovery action is taken; blocked "
                "and escalated for manual review (SR6)."
            ),
        )

    # --- SR3: mandate expiry never auto-retries -----------------------
    if transaction["failure_reason"] == "mandate_expired":
        return Decision(
            intervention=INTERVENTION_REAUTH,
            rule_fired="mandate_expired_requires_reauth",
            escalate=True,
            stopping_rule_hit="mandate_expired_no_auto_retry",
            notes="Compliant action for an expired mandate is re-authorization, never a blind retry (SR3).",
        )

    # --- SR1: max retries -----------------------------------------------
    if transaction["prior_retry_count"] >= policy.max_retries:
        return Decision(
            intervention=INTERVENTION_MANUAL_REVIEW,
            rule_fired="max_retries_exceeded",
            escalate=True,
            stopping_rule_hit="max_retries",
            notes=f"prior_retry_count={transaction['prior_retry_count']} >= {policy.max_retries}; a 4th attempt is never automatic (SR1).",
        )

    # --- per-failure_reason table-driven handler -------------------------
    handler = FAILURE_HANDLERS[transaction["failure_reason"]]
    decision = handler(transaction, now, rng, policy)

    # --- SR5: mandatory human escalation for high-value repeat failures --
    if (
        transaction["amount_inr"] > policy.escalation_amount_threshold_inr
        and transaction["prior_retry_count"] >= 1
        and not decision.escalate
    ):
        decision.escalate = True
        decision.rule_fired = f"high_value_prior_failure_escalation+{decision.rule_fired}"
        decision.stopping_rule_hit = decision.stopping_rule_hit or "high_value_threshold"
        decision.notes += (
            f" Also escalated: amount_inr={transaction['amount_inr']} > "
            f"{policy.escalation_amount_threshold_inr} with a prior failed attempt (SR5)."
        )

    return decision
