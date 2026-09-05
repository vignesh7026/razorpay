"""Live webhook ingestion path -- closes the gap PRD section 8.3 states plainly:
"Razorpay webhooks require a publicly reachable URL; the development sandbox
has none... Detection is therefore driven by the synthetic batch." That's
still true for *this* dev environment, but the ingestion path itself doesn't
have to stay theoretical: this module is a real handler for a
Razorpay-webhook-shaped `payment.failed` event, wired to the exact same
decision engine, executor, and audit log as the batch path. scripts/
simulate_webhooks.py drives it locally to prove the whole loop works
event-by-event, in real time, not just batch-by-batch.

One honest simplification: a real Razorpay webhook payload doesn't carry a
customer's prior-retry history (that's the merchant's own record, not
Razorpay's) -- a production integration would look that up from its own
orders/subscriptions table. This module does the same thing at a small
scale: WEBHOOK_STATE_FILE tracks prior attempts per (customer_id, sku),
exactly like a minimal orders table would.
"""
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.audit_logger import append_record
from app.config import BACKEND_ROOT
from app.decision_engine import decide
from app.razorpay_client import get_client
from app.recovery_executor import execute_decision

WEBHOOK_STATE_FILE = BACKEND_ROOT / "reports" / "webhook_retry_state.json"

# Razorpay's real webhook error_reason codes don't map 1:1 onto this
# project's internal failure_reason categories -- a production system needs
# exactly this kind of translation layer between the raw gateway code and
# an internal category the decision engine can route on.
RAZORPAY_ERROR_REASON_MAP = {
    "card_declined": "card_declined",
    "payment_failed": "card_declined",
    "insufficient_funds": "insufficient_funds",
    "gateway_timeout": "gateway_timeout",
    "otp_timeout_error": "otp_timeout",
    "mandate_insufficient_funds": "mandate_insufficient_funds",
    "mandate_expired": "mandate_expired",
    "checkout_abandoned": "checkout_abandoned",
}


def _load_state() -> dict:
    if not WEBHOOK_STATE_FILE.exists():
        return {}
    return json.loads(WEBHOOK_STATE_FILE.read_text(encoding="utf-8") or "{}")


def _save_state(state: dict) -> None:
    WEBHOOK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    WEBHOOK_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def reset_webhook_state() -> None:
    _save_state({})


class UnhandledWebhookEvent(Exception):
    pass


def handle_razorpay_webhook(payload: dict) -> Optional[dict]:
    """Parses a Razorpay-webhook-shaped payload, runs it through the same
    decide -> execute -> log pipeline the batch uses, and returns the
    resulting audit record. Returns None for event types this demo doesn't
    handle (mirrors a real webhook handler filtering to events it cares
    about).
    """
    event = payload.get("event")
    if event != "payment.failed":
        return None

    entity = payload["payload"]["payment"]["entity"]
    notes = entity.get("notes", {})

    raw_reason = notes.get("failure_reason", "card_declined")
    failure_reason = RAZORPAY_ERROR_REASON_MAP.get(raw_reason, "card_declined")
    is_recurring = str(notes.get("is_recurring", "false")).lower() == "true"

    customer_id = notes.get("customer_id", f"cust_live_{uuid4().hex[:6]}")
    sku = notes.get("sku", "SKU-LIVE")
    state_key = f"{customer_id}:{sku}"

    state = _load_state()
    history = state.get(state_key, {"prior_retry_count": 0, "prior_retry_timestamps": []})

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat().replace("+00:00", "Z")

    transaction = {
        "transaction_id": f"txn_live_{uuid4().hex[:10]}",
        "customer_id": customer_id,
        "customer_name": notes.get("customer_name", "Live Customer"),
        "sku": sku,
        "product_name": notes.get("product_name", "Live Product"),
        "amount_inr": round(entity.get("amount", 0) / 100, 2),
        "product_margin_pct": float(notes.get("product_margin_pct", 0.2)),
        "is_recurring": is_recurring,
        "failure_reason": failure_reason,
        "occurred_at": now_iso,
        "prior_retry_count": history["prior_retry_count"],
        "prior_retry_timestamps": history["prior_retry_timestamps"],
        "status": "at_risk",
        "source": "webhook",
    }

    decision = decide(transaction, now=now)
    client = get_client()
    audit_record = execute_decision(transaction, decision, client)
    audit_record["source"] = "webhook"
    append_record(audit_record)

    state[state_key] = {
        "prior_retry_count": history["prior_retry_count"] + 1,
        "prior_retry_timestamps": history["prior_retry_timestamps"] + [now_iso],
    }
    _save_state(state)

    return audit_record
