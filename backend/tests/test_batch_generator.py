"""Reproducibility (PRD section 8.2) and the section-11 requirement that
every stopping rule demonstrably fires at least once in the batch run --
checked here instead of only by eyeballing a live run's output.
"""
from app.batch_generator import FAILURE_DISTRIBUTION, generate_batch
from app.decision_engine import decide
from app.batch_generator import BATCH_REFERENCE_TIME


def test_same_seed_produces_identical_batch():
    batch_a = generate_batch(size=120, seed=42)
    batch_b = generate_batch(size=120, seed=42)
    assert batch_a == batch_b


def test_different_seed_produces_different_batch():
    batch_a = generate_batch(size=120, seed=42)
    batch_b = generate_batch(size=120, seed=7)
    assert batch_a != batch_b


def test_all_seven_failure_reasons_are_represented():
    batch = generate_batch(size=120, seed=42)
    reasons_present = {t["failure_reason"] for t in batch}
    assert reasons_present == set(FAILURE_DISTRIBUTION.keys())


def test_recurring_flag_matches_failure_reason_table():
    batch = generate_batch(size=120, seed=42)
    for txn in batch:
        expected_recurring = FAILURE_DISTRIBUTION[txn["failure_reason"]][1]
        assert txn["is_recurring"] == expected_recurring


def test_every_stopping_rule_fires_at_least_once_in_the_seeded_batch():
    """Integration check for PRD section 11: 'every stopping rule
    demonstrably fires at least once in the batch run.' Runs the real
    decision engine over the real seeded batch, not a hand-picked fixture.
    """
    batch = generate_batch(size=120, seed=42)
    decisions = [decide(txn, now=BATCH_REFERENCE_TIME) for txn in batch]

    stopping_rules_hit = {d.stopping_rule_hit for d in decisions if d.stopping_rule_hit}
    assert "max_retries" in stopping_rules_hit  # SR1
    assert "cooldown_active" in stopping_rules_hit  # SR2
    assert "mandate_expired_no_auto_retry" in stopping_rules_hit  # SR3
    assert "high_value_threshold" in stopping_rules_hit  # SR5

    # SR4 (margin floor) isn't a stopping_rule_hit value -- it's a cap
    # applied on every checkout_abandoned decision -- so check it directly:
    incentive_decisions = [d for d in decisions if d.incentive_pct > 0]
    assert len(incentive_decisions) > 0
    assert all(d.incentive_pct <= 0.10 for d in decisions)
