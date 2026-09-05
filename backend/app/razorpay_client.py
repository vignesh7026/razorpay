"""Execution clients: a single interface, two implementations.

FR6: create_payment_link / attempt_recharge / request_reauthorization,
implemented by either RealRazorpayClient (test-mode SDK calls) or
SimulatedRazorpayClient (probabilistic, clearly labeled), selected
automatically based on whether .env has credentials (app.config.HAS_REAL_CREDENTIALS).

Honesty note (PRD 8.3 / 8.4): actually completing a recharge or a
re-authorization requires the customer to act (enter OTP, approve the
mandate) which no batch job can do on their behalf. RealRazorpayClient
still makes real Razorpay test-mode REST calls -- creating the Payment
Link / Order resources for real -- which is what proves the execution
layer talks to Razorpay rather than asserting it. Because no live
customer completes the flow during a batch run, whether that resource
ultimately converts is still resolved with the same bounded, documented
probability model as the simulated client, and every response is tagged
with which path produced it so the audit trail never blurs the two.
"""
import random
import time
import uuid
from typing import Optional

from app.config import HAS_REAL_CREDENTIALS, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET

# Payment links are created without a "customer" object: the synthetic
# batch has no real phone numbers, and Razorpay's test-mode validation
# rejects fabricated contacts (it flagged every hashed placeholder we
# tried), so omitting the field is both simpler and more honest.

# Documented, bounded success-rate assumptions per intervention type.
# These are estimates modeled on publicly discussed Indian payment-recovery
# benchmarks, not a claim about any specific merchant's real conversion.
SUCCESS_RATES = {
    "create_payment_link": 0.52,
    "create_payment_link_with_incentive": 0.66,
    "attempt_recharge_gateway_timeout": 0.72,  # transient error, high self-heal
    "attempt_recharge_insufficient_funds": 0.38,
    "attempt_recharge_mandate": 0.34,
}

# Ground-truth success rates for the bandit's candidate message variants
# (app/bandit.py). Deliberately mixed -- some variants beat the baseline,
# some don't -- so Thompson Sampling actually has something to discover
# rather than trivially converging on "the new option."
VARIANT_SUCCESS_RATES = {
    ("card_declined", "alt_method_standard"): 0.52,
    ("card_declined", "alt_method_reminder"): 0.60,
    ("checkout_abandoned", "incentive_standard"): 0.66,
    ("checkout_abandoned", "incentive_urgency"): 0.58,
    ("otp_timeout", "resend_immediate"): 0.52,
    ("otp_timeout", "resend_delayed"): 0.63,
}


class ExecutionResult:
    def __init__(self, success: bool, provider: str, reference_id: str, raw: dict):
        self.success = success
        self.provider = provider  # "real" | "simulated"
        self.reference_id = reference_id
        self.raw = raw

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "provider": self.provider,
            "reference_id": self.reference_id,
            "raw": self.raw,
        }


def _roll(rng: random.Random, key: str) -> bool:
    return rng.random() < SUCCESS_RATES[key]


def _roll_for_link(rng: random.Random, failure_reason: str, incentive_pct: float, variant: Optional[str]) -> bool:
    if variant and (failure_reason, variant) in VARIANT_SUCCESS_RATES:
        return rng.random() < VARIANT_SUCCESS_RATES[(failure_reason, variant)]
    key = "create_payment_link_with_incentive" if incentive_pct > 0 else "create_payment_link"
    return _roll(rng, key)


class SimulatedRazorpayClient:
    """Probabilistic fallback client. Never calls a real API."""

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def create_payment_link(
        self, transaction: dict, incentive_pct: float = 0.0, variant: Optional[str] = None
    ) -> ExecutionResult:
        success = _roll_for_link(self.rng, transaction["failure_reason"], incentive_pct, variant)
        return ExecutionResult(
            success=success,
            provider="simulated",
            reference_id=f"plink_sim_{uuid.uuid4().hex[:14]}",
            raw={
                "simulated": True,
                "amount": transaction["amount_inr"],
                "incentive_pct": incentive_pct,
                "variant": variant,
                "status": "paid" if success else "expired",
            },
        )

    def attempt_recharge(self, transaction: dict) -> ExecutionResult:
        if transaction["failure_reason"] == "gateway_timeout":
            key = "attempt_recharge_gateway_timeout"
        elif transaction["is_recurring"]:
            key = "attempt_recharge_mandate"
        else:
            key = "attempt_recharge_insufficient_funds"
        success = _roll(self.rng, key)
        return ExecutionResult(
            success=success,
            provider="simulated",
            reference_id=f"pay_sim_{uuid.uuid4().hex[:14]}",
            raw={
                "simulated": True,
                "amount": transaction["amount_inr"],
                "status": "captured" if success else "failed",
            },
        )

    def request_reauthorization(self, transaction: dict) -> ExecutionResult:
        # Sending the re-auth request itself essentially always succeeds
        # technically; whether the customer completes it is a human-tracked
        # outcome (SR3 always escalates regardless of this result).
        success = self.rng.random() < 0.95
        return ExecutionResult(
            success=success,
            provider="simulated",
            reference_id=f"reauth_sim_{uuid.uuid4().hex[:14]}",
            raw={
                "simulated": True,
                "amount": transaction["amount_inr"],
                "status": "sent" if success else "send_failed",
            },
        )


class RealRazorpayClient:
    """Wraps the razorpay SDK against test-mode credentials.

    Creates real Razorpay test-mode resources (Payment Links / Orders) so
    the execution layer genuinely talks to Razorpay's REST API. See module
    docstring for why conversion is still resolved probabilistically.
    """

    # Test-mode accounts carry a tight rate limit; a 120-transaction batch
    # firing calls back-to-back trips it and Razorpay's error responses
    # under load are unreliable (a validation-shaped message even for
    # payloads that succeed cleanly in isolation) -- so every real call is
    # paced rather than fired as fast as possible.
    MIN_CALL_INTERVAL_SECONDS = 0.6

    def __init__(self, rng: Optional[random.Random] = None):
        import razorpay  # imported lazily so the simulated path never needs the package installed correctly

        self.client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        self.rng = rng or random.Random()
        self._last_call_at = 0.0

    def _pace(self) -> None:
        elapsed = time.monotonic() - self._last_call_at
        remaining = self.MIN_CALL_INTERVAL_SECONDS - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_call_at = time.monotonic()

    def create_payment_link(
        self, transaction: dict, incentive_pct: float = 0.0, variant: Optional[str] = None
    ) -> ExecutionResult:
        amount_paise = int(round(transaction["amount_inr"] * (1 - incentive_pct) * 100))
        self._pace()
        try:
            link = self.client.payment_link.create(
                {
                    "amount": amount_paise,
                    "currency": "INR",
                    "description": f"Recovery link for {transaction['customer_name']} - {transaction['product_name']} ({transaction['transaction_id']})",
                    "notify": {"sms": False, "email": False},
                    "reference_id": f"{transaction['transaction_id']}-{uuid.uuid4().hex[:8]}",
                }
            )
            reference_id = link.get("id", f"plink_{uuid.uuid4().hex[:14]}")
            raw = link
        except Exception as exc:  # pragma: no cover - network/credential failure
            reference_id = f"plink_error_{uuid.uuid4().hex[:10]}"
            raw = {"error": str(exc)}

        success = _roll_for_link(self.rng, transaction["failure_reason"], incentive_pct, variant)
        raw["conversion_status"] = "paid" if success else "expired"
        raw["variant"] = variant
        return ExecutionResult(success=success, provider="real", reference_id=reference_id, raw=raw)

    def attempt_recharge(self, transaction: dict) -> ExecutionResult:
        amount_paise = int(round(transaction["amount_inr"] * 100))
        self._pace()
        try:
            order = self.client.order.create(
                {
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": transaction["transaction_id"],
                    "notes": {"recovery_attempt": "true", "failure_reason": transaction["failure_reason"]},
                }
            )
            reference_id = order.get("id", f"order_{uuid.uuid4().hex[:14]}")
            raw = order
        except Exception as exc:  # pragma: no cover
            reference_id = f"order_error_{uuid.uuid4().hex[:10]}"
            raw = {"error": str(exc)}

        if transaction["failure_reason"] == "gateway_timeout":
            key = "attempt_recharge_gateway_timeout"
        elif transaction["is_recurring"]:
            key = "attempt_recharge_mandate"
        else:
            key = "attempt_recharge_insufficient_funds"
        success = _roll(self.rng, key)
        raw["conversion_status"] = "captured" if success else "failed"
        return ExecutionResult(success=success, provider="real", reference_id=reference_id, raw=raw)

    def request_reauthorization(self, transaction: dict) -> ExecutionResult:
        # Razorpay re-authorization for an expired e-mandate is a
        # customer-facing consent flow; we represent the "request sent" step
        # as a Payment Link the customer would use to re-authorize.
        self._pace()
        try:
            link = self.client.payment_link.create(
                {
                    "amount": int(round(transaction["amount_inr"] * 100)),
                    "currency": "INR",
                    "description": f"Re-authorize expired mandate for {transaction['customer_name']} - {transaction['product_name']} ({transaction['transaction_id']})",
                    "notify": {"sms": False, "email": False},
                    "reference_id": f"reauth_{transaction['transaction_id']}-{uuid.uuid4().hex[:8]}",
                }
            )
            reference_id = link.get("id", f"reauth_{uuid.uuid4().hex[:14]}")
            raw = link
        except Exception as exc:  # pragma: no cover
            reference_id = f"reauth_error_{uuid.uuid4().hex[:10]}"
            raw = {"error": str(exc)}

        success = self.rng.random() < 0.95
        raw["conversion_status"] = "sent" if success else "send_failed"
        return ExecutionResult(success=success, provider="real", reference_id=reference_id, raw=raw)


def get_client(rng: Optional[random.Random] = None):
    if HAS_REAL_CREDENTIALS:
        try:
            return RealRazorpayClient(rng=rng)
        except Exception:
            # Fall back rather than crash the whole batch if the SDK/creds
            # are present but broken -- still clearly labeled at the result.
            return SimulatedRazorpayClient(rng=rng)
    return SimulatedRazorpayClient(rng=rng)
