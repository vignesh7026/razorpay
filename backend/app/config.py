"""Central constants for the decision/execution engine.

Every numeric guardrail lives here so the stopping rules in decision_engine.py
read as policy lookups, not magic numbers scattered through the codebase.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_ROOT / ".env")

DATA_DIR = BACKEND_ROOT / "data"
REPORTS_DIR = BACKEND_ROOT / "reports"
BATCH_FILE = DATA_DIR / "batch.json"
AUDIT_LOG_FILE = REPORTS_DIR / "audit_log.jsonl"
REPORT_JSON_FILE = REPORTS_DIR / "report.json"
REPORT_MD_FILE = REPORTS_DIR / "report.md"

RANDOM_SEED = 42
BATCH_SIZE = 120

# SR1 - no transaction is auto-retried more than this many times.
MAX_RETRIES = 3

# SR2 - cooldown windows before a retry may be attempted again.
RECURRING_COOLDOWN_HOURS = 24  # e-mandate / recurring debit retry spacing
NON_RECURRING_COOLDOWN_HOURS = 2  # insufficient_funds delayed retry

# SR4 - margin floor guardrail for incentives offered on recovery nudges.
INCENTIVE_TARGET_PCT = 0.10
MARGIN_SAFETY_BUFFER_PCT = 0.05  # keep at least this much margin after discount

# SR5 - mandatory human escalation above this amount, if a prior attempt failed.
ESCALATION_AMOUNT_THRESHOLD_INR = float(
    os.getenv("ESCALATION_AMOUNT_THRESHOLD_INR", "5000")
)

# Counterfactual baseline (report.py): what a "just retry everything the same
# generic way" strategy -- no per-failure-type routing, no cooldown respect,
# no alternate-method prompt, no incentive -- would recover, so the report
# can show the decision engine's uplift over a naive strategy rather than
# only an absolute recovered-rupee number. Deliberately below every
# specialized SUCCESS_RATES entry in razorpay_client.py (a blind retry with
# no smart routing converts worse than a tailored intervention).
NAIVE_RETRY_SUCCESS_RATE = 0.22

# failure_reason values where a blind retry cannot structurally work at all
# (not just "worse" -- would fail outright), so the naive baseline is 0 for
# these rather than the flat NAIVE_RETRY_SUCCESS_RATE:
#   - checkout_abandoned: there is no failed payment to retry, only an
#     abandoned cart -- "retry" isn't a meaningful action.
#   - mandate_expired: Razorpay rejects a recharge against an expired
#     mandate token outright; re-authorization is structurally required (SR3).
NAIVE_RETRY_IMPOSSIBLE_REASONS = {"checkout_abandoned", "mandate_expired"}

# SR6 - lightweight pattern-based abuse guardrail, deliberately narrow in
# scope (see decision_engine.py SR6 docstring for why this is not, and does
# not claim to be, a fraud model -- that's explicitly out of scope per the
# PRD). A "card testing" signature: an abnormal number of DISTINCT customers
# all hitting card_declined at suspiciously low amounts inside a short
# rolling window.
CARD_TESTING_WINDOW_MINUTES = 15
CARD_TESTING_MIN_DISTINCT_CUSTOMERS = 4
CARD_TESTING_MAX_AMOUNT_INR = 500

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
HAS_REAL_CREDENTIALS = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
HAS_LLM_CREDENTIALS = bool(ANTHROPIC_API_KEY)
LLM_MODEL = "claude-opus-5"

ESCALATION_ACTIONS_FILE = REPORTS_DIR / "escalation_actions.jsonl"
BANDIT_STATE_FILE = REPORTS_DIR / "bandit_state.json"
RUN_HISTORY_FILE = REPORTS_DIR / "run_history.jsonl"
