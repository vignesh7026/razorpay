"""Guardrail policy simulator: re-runs the real decision engine over the
current batch under a hypothetical PolicyConfig, without touching the
persisted audit log, bandit state, or escalation actions -- the "what-if"
sliders in the dashboard call this, not app.pipeline.

Deliberately uses expected-value arithmetic instead of a random rollout:
per-transaction outcome is drawn from a Bernoulli trial in the real
pipeline (so re-running "what if max_retries were 5" would also reshuffle
every random outcome, making the delta noisy and hard to attribute to the
policy change alone). Here every transaction contributes
amount * (success probability) as a continuous expectation, so moving one
slider produces a stable, smooth, attributable change in the projected
numbers -- appropriate for an interactive tool, not a replacement for the
real probabilistic execution path.
"""
from datetime import datetime

from app.batch_generator import BATCH_REFERENCE_TIME
from app.fraud_detection import annotate_suspected_fraud
from app.decision_engine import (
    INTERVENTION_BLOCKED,
    INTERVENTION_CREATE_LINK,
    INTERVENTION_MANUAL_REVIEW,
    INTERVENTION_REAUTH,
    INTERVENTION_RETRY,
    Decision,
    PolicyConfig,
    decide,
)
from app.razorpay_client import SUCCESS_RATES

FAILURE_REASON_ORDER = [
    "card_declined",
    "checkout_abandoned",
    "insufficient_funds",
    "gateway_timeout",
    "otp_timeout",
    "mandate_insufficient_funds",
    "mandate_expired",
]


def _success_probability(transaction: dict, decision: Decision) -> float:
    if decision.intervention == INTERVENTION_CREATE_LINK:
        return SUCCESS_RATES["create_payment_link_with_incentive" if decision.incentive_pct > 0 else "create_payment_link"]
    if decision.intervention == INTERVENTION_RETRY:
        if transaction["failure_reason"] == "gateway_timeout":
            return SUCCESS_RATES["attempt_recharge_gateway_timeout"]
        if transaction["is_recurring"]:
            return SUCCESS_RATES["attempt_recharge_mandate"]
        return SUCCESS_RATES["attempt_recharge_insufficient_funds"]
    return 0.0  # reauth / manual_review / blocked never count as recovered


def _expected_outcome(transaction: dict, decision: Decision) -> tuple[str, float]:
    """Returns (bucketed_outcome_for_display, expected_recovered_inr)."""
    if decision.stopping_rule_hit == "cooldown_active":
        return "pending_retry", 0.0
    if decision.intervention in (INTERVENTION_MANUAL_REVIEW, INTERVENTION_BLOCKED):
        return "escalated", 0.0

    p = _success_probability(transaction, decision)
    expected = transaction["amount_inr"] * (1 - decision.incentive_pct) * p if decision.intervention == INTERVENTION_CREATE_LINK else transaction["amount_inr"] * p

    if decision.escalate:
        return "escalated", 0.0  # matches the real executor: escalated cases never count as recovered
    return ("recovered" if p >= 0.5 else "failed"), round(expected, 2)


def simulate_policy(batch: list[dict], policy: PolicyConfig, decision_time: datetime = BATCH_REFERENCE_TIME) -> dict:
    # suspected_fraud flags aren't persisted to data/batch.json (they're
    # computed fresh in-memory each real run) -- re-derive them here so SR6
    # participates in the what-if just like every other rule. Deterministic
    # given the same batch, so this is safe to redo on every call.
    annotate_suspected_fraud(batch)

    total_at_risk = 0.0
    total_recovered = 0.0
    counts_by_outcome: dict[str, int] = {}
    by_reason: dict[str, dict] = {r: {"at_risk_inr": 0.0, "recovered_inr": 0.0, "count": 0} for r in FAILURE_REASON_ORDER}

    for txn in batch:
        decision = decide(txn, now=decision_time, policy=policy)
        outcome, expected_recovered = _expected_outcome(txn, decision)

        total_at_risk += txn["amount_inr"]
        total_recovered += expected_recovered
        counts_by_outcome[outcome] = counts_by_outcome.get(outcome, 0) + 1

        bucket = by_reason.setdefault(txn["failure_reason"], {"at_risk_inr": 0.0, "recovered_inr": 0.0, "count": 0})
        bucket["at_risk_inr"] += txn["amount_inr"]
        bucket["recovered_inr"] += expected_recovered
        bucket["count"] += 1

    for bucket in by_reason.values():
        bucket["rate"] = round(bucket["recovered_inr"] / bucket["at_risk_inr"], 4) if bucket["at_risk_inr"] else 0.0
        bucket["at_risk_inr"] = round(bucket["at_risk_inr"], 2)
        bucket["recovered_inr"] = round(bucket["recovered_inr"], 2)

    return {
        "total_transactions": len(batch),
        "total_at_risk_inr": round(total_at_risk, 2),
        "total_recovered_inr": round(total_recovered, 2),
        "recovery_rate_overall": round(total_recovered / total_at_risk, 4) if total_at_risk else 0.0,
        "counts_by_outcome": counts_by_outcome,
        "by_failure_reason": by_reason,
    }
