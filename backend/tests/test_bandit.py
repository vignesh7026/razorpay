"""Beta-Bernoulli bandit correctness: arm updates, posterior convergence,
and that a failure_reason outside VARIANTS never gets a variant at all
(the bandit is opt-in per failure type, not global)."""
import random

import pytest

from app import bandit


@pytest.fixture(autouse=True)
def isolated_bandit_state(tmp_path, monkeypatch):
    """Every test gets its own empty state file -- never touch the real
    persisted reports/bandit_state.json.
    """
    monkeypatch.setattr(bandit, "BANDIT_STATE_FILE", tmp_path / "bandit_state.json")
    yield


def test_failure_reason_without_variants_returns_none():
    rng = random.Random(1)
    assert bandit.select_variant("gateway_timeout", rng) is None


def test_failure_reason_with_variants_returns_one_of_them():
    rng = random.Random(1)
    variant = bandit.select_variant("card_declined", rng)
    assert variant in bandit.get_arms("card_declined")


def test_update_arm_increments_alpha_on_reward():
    bandit.update_arm("card_declined", "alt_method_standard", reward=True)
    stats = bandit.get_all_arm_stats()
    arm = next(a for a in stats["card_declined"] if a["variant"] == "alt_method_standard")
    assert arm["alpha"] == 2  # prior alpha=1, plus one reward
    assert arm["beta"] == 1
    assert arm["observations"] == 1


def test_update_arm_increments_beta_on_no_reward():
    bandit.update_arm("card_declined", "alt_method_standard", reward=False)
    stats = bandit.get_all_arm_stats()
    arm = next(a for a in stats["card_declined"] if a["variant"] == "alt_method_standard")
    assert arm["alpha"] == 1
    assert arm["beta"] == 2


def test_update_arm_with_no_variant_is_a_noop():
    bandit.update_arm("gateway_timeout", None, reward=True)
    # should not raise, and should not create any state
    stats = bandit.get_all_arm_stats()
    assert "gateway_timeout" not in stats  # not a bandit-managed failure_reason


def test_posterior_mean_converges_toward_true_rate_with_enough_observations():
    """Feed the bandit a known 80%-success stream for one arm and confirm
    its posterior mean lands near 0.8, not just "some number changed."
    """
    rng = random.Random(7)
    for _ in range(500):
        reward = rng.random() < 0.8
        bandit.update_arm("card_declined", "alt_method_reminder", reward=reward)

    stats = bandit.get_all_arm_stats()
    arm = next(a for a in stats["card_declined"] if a["variant"] == "alt_method_reminder")
    assert arm["estimated_success_rate"] == pytest.approx(0.8, abs=0.06)


def test_thompson_sampling_favors_the_better_arm_over_many_selections():
    """Pre-seed one arm with strong evidence of a high success rate and a
    second arm with strong evidence of a low one; selection should then
    favor the better arm the large majority of the time.
    """
    for _ in range(60):
        bandit.update_arm("otp_timeout", "resend_delayed", reward=True)  # looks great
    for _ in range(60):
        bandit.update_arm("otp_timeout", "resend_immediate", reward=False)  # looks bad

    rng = random.Random(3)
    picks = [bandit.select_variant("otp_timeout", rng) for _ in range(200)]
    favored_share = picks.count("resend_delayed") / len(picks)
    assert favored_share > 0.9
