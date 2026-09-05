"""Turns a Decision into an actual execution attempt and a full audit record.

FR7: the execution result (success/fail + provider response or simulated
equivalent) is captured before the audit log is written, so the log
reflects what actually happened rather than what was intended.
"""
from datetime import datetime, timezone

from app import bandit
from app.decision_engine import (
    INTERVENTION_BLOCKED,
    INTERVENTION_CREATE_LINK,
    INTERVENTION_MANUAL_REVIEW,
    INTERVENTION_REAUTH,
    INTERVENTION_RETRY,
    Decision,
)


def execute_decision(transaction: dict, decision: Decision, client) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    execution_result = None
    recovered_inr = 0.0

    if decision.stopping_rule_hit == "cooldown_active":
        outcome = "pending_retry"

    elif decision.intervention in (INTERVENTION_MANUAL_REVIEW, INTERVENTION_BLOCKED):
        outcome = "escalated"

    else:
        if decision.intervention == INTERVENTION_CREATE_LINK:
            execution_result = client.create_payment_link(
                transaction, incentive_pct=decision.incentive_pct, variant=decision.intervention_variant
            )
        elif decision.intervention == INTERVENTION_RETRY:
            execution_result = client.attempt_recharge(transaction)
        elif decision.intervention == INTERVENTION_REAUTH:
            execution_result = client.request_reauthorization(transaction)
        else:  # pragma: no cover - defensive, table above is exhaustive
            raise ValueError(f"Unhandled intervention: {decision.intervention}")

        if decision.escalate:
            outcome = "escalated"
        elif execution_result.success:
            outcome = "recovered"
            if decision.intervention == INTERVENTION_CREATE_LINK and decision.incentive_pct:
                recovered_inr = round(transaction["amount_inr"] * (1 - decision.incentive_pct), 2)
            else:
                recovered_inr = float(transaction["amount_inr"])
        else:
            outcome = "failed"

        # Feed the bandit: did this specific message variant actually lead
        # to recovered revenue? Escalated cases still count -- SR5 loops in
        # a human in parallel with the intervention, it doesn't replace it.
        bandit.update_arm(
            transaction["failure_reason"],
            decision.intervention_variant,
            reward=(outcome == "recovered"),
        )

    audit_record = {
        "transaction_id": transaction["transaction_id"],
        "failure_reason": transaction["failure_reason"],
        "intervention_chosen": decision.intervention,
        "rule_fired": decision.rule_fired,
        "outcome": outcome,
        "stopping_rule_hit": decision.stopping_rule_hit,
        "escalated_to_human": decision.escalate,
        "amount_inr": transaction["amount_inr"],
        "timestamp": now_iso,
        # bonus fields beyond the FR8 minimum -- useful for the report/UI,
        # and kept on the same record so the log stays the single source
        # of truth (FR9) rather than the report re-deriving them elsewhere.
        "recovered_inr": recovered_inr,
        "incentive_pct": decision.incentive_pct,
        "intervention_variant": decision.intervention_variant,
        "product_margin_pct": transaction["product_margin_pct"],
        "prior_retry_count": transaction["prior_retry_count"],
        "is_recurring": transaction["is_recurring"],
        "customer_id": transaction["customer_id"],
        "customer_name": transaction["customer_name"],
        "product_name": transaction["product_name"],
        "rule_notes": decision.notes,
        "execution": execution_result.to_dict() if execution_result else None,
    }
    return audit_record
