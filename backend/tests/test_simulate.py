"""The policy simulator must respond to threshold changes in the expected
direction, deterministically (no random-trial noise), and must never touch
the real persisted files.
"""
from app.batch_generator import generate_batch
from app.decision_engine import PolicyConfig
from app.simulate import simulate_policy


def test_same_policy_gives_identical_results_across_calls():
    batch = generate_batch(size=60, seed=42)
    policy = PolicyConfig()
    r1 = simulate_policy(batch, policy)
    r2 = simulate_policy(batch, policy)
    assert r1 == r2  # no randomness -- pure expected-value arithmetic


def test_looser_max_retries_never_increases_escalation_count():
    batch = generate_batch(size=120, seed=42)
    tight = simulate_policy(batch, PolicyConfig(max_retries=1))
    loose = simulate_policy(batch, PolicyConfig(max_retries=10))
    # a tighter ceiling can only escalate as many or more transactions on
    # the max-retries path than a looser one
    assert loose.get("counts_by_outcome", {}).get("escalated", 0) <= tight.get("counts_by_outcome", {}).get("escalated", 0)


def test_higher_escalation_threshold_reduces_or_holds_escalations():
    batch = generate_batch(size=120, seed=42)
    low_threshold = simulate_policy(batch, PolicyConfig(escalation_amount_threshold_inr=100))
    high_threshold = simulate_policy(batch, PolicyConfig(escalation_amount_threshold_inr=10_000_000))
    assert (
        high_threshold["counts_by_outcome"].get("escalated", 0)
        <= low_threshold["counts_by_outcome"].get("escalated", 0)
    )


def test_zero_cooldown_never_produces_pending_retry():
    batch = generate_batch(size=120, seed=42)
    result = simulate_policy(batch, PolicyConfig(recurring_cooldown_hours=0, non_recurring_cooldown_hours=0))
    assert result["counts_by_outcome"].get("pending_retry", 0) == 0


def test_segmented_by_failure_reason_present_for_every_category():
    batch = generate_batch(size=120, seed=42)
    result = simulate_policy(batch, PolicyConfig())
    from app.simulate import FAILURE_REASON_ORDER

    for reason in FAILURE_REASON_ORDER:
        assert reason in result["by_failure_reason"]


def test_total_at_risk_matches_sum_of_batch_amounts():
    batch = generate_batch(size=60, seed=42)
    result = simulate_policy(batch, PolicyConfig())
    assert result["total_at_risk_inr"] == round(sum(t["amount_inr"] for t in batch), 2)
