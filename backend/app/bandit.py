"""Adaptive intervention selection: Beta-Bernoulli Thompson Sampling across
candidate message variants for a handful of failure types, so the engine
doesn't apply one fixed message forever -- it learns which variant converts
better across successive runs, with state persisted in BANDIT_STATE_FILE.

Scope is deliberately narrow: only failure types where a genuine A/B
question exists (a different message framing of the *same* intervention
type, not a different guardrail) get more than one candidate variant. Every
stopping rule (SR1-SR5) still applies exactly as before and always wins --
the bandit only chooses among variants of an intervention already decided
by the table-driven engine, never around a guardrail.
"""
import json
import random
from typing import Optional

from app.config import BANDIT_STATE_FILE, REPORTS_DIR

VARIANTS: dict[str, list[str]] = {
    "card_declined": ["alt_method_standard", "alt_method_reminder"],
    "checkout_abandoned": ["incentive_standard", "incentive_urgency"],
    "otp_timeout": ["resend_immediate", "resend_delayed"],
}

VARIANT_LABELS: dict[str, str] = {
    "alt_method_standard": "Standard alt-method link",
    "alt_method_reminder": "Alt-method link + reminder framing",
    "incentive_standard": "Standard incentive framing",
    "incentive_urgency": "Urgency-framed incentive",
    "resend_immediate": "Immediate OTP resend",
    "resend_delayed": "Delayed OTP resend (~10 min)",
}


def _load_state() -> dict:
    if not BANDIT_STATE_FILE.exists():
        return {}
    return json.loads(BANDIT_STATE_FILE.read_text(encoding="utf-8") or "{}")


def _save_state(state: dict) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    BANDIT_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def reset_bandit_state() -> None:
    _save_state({})


def _arm_key(failure_reason: str, variant: str) -> str:
    return f"{failure_reason}:{variant}"


def get_arms(failure_reason: str) -> list[str]:
    return VARIANTS.get(failure_reason, [])


def select_variant(failure_reason: str, rng: random.Random) -> Optional[str]:
    """Thompson Sampling: draw one sample from each arm's Beta(alpha, beta)
    posterior and pick the arm with the highest draw. Arms with fewer
    observations have a wider posterior and get sampled more exploratively;
    as evidence accumulates, the better arm's draws start winning more
    consistently -- that convergence is what the Learning view charts.
    """
    arms = get_arms(failure_reason)
    if not arms:
        return None
    state = _load_state()
    best_arm, best_sample = None, -1.0
    for arm in arms:
        params = state.get(_arm_key(failure_reason, arm), {"alpha": 1, "beta": 1})
        sample = rng.betavariate(params["alpha"], params["beta"])
        if sample > best_sample:
            best_sample, best_arm = sample, arm
    return best_arm


def update_arm(failure_reason: str, variant: Optional[str], reward: bool) -> None:
    if not variant:
        return
    state = _load_state()
    key = _arm_key(failure_reason, variant)
    params = state.get(key, {"alpha": 1, "beta": 1})
    params["alpha" if reward else "beta"] += 1
    state[key] = params
    _save_state(state)


def get_all_arm_stats() -> dict:
    """Per failure_reason, each variant's current posterior mean (estimated
    success rate) and observation count -- the Learning view's convergence
    chart renders directly from this.
    """
    state = _load_state()
    result = {}
    for failure_reason, arms in VARIANTS.items():
        result[failure_reason] = []
        for arm in arms:
            params = state.get(_arm_key(failure_reason, arm), {"alpha": 1, "beta": 1})
            alpha, beta = params["alpha"], params["beta"]
            observations = max(alpha + beta - 2, 0)  # minus the uniform prior's pseudo-counts
            result[failure_reason].append(
                {
                    "variant": arm,
                    "label": VARIANT_LABELS.get(arm, arm),
                    "estimated_success_rate": round(alpha / (alpha + beta), 4),
                    "observations": observations,
                    "alpha": alpha,
                    "beta": beta,
                }
            )
    return result
