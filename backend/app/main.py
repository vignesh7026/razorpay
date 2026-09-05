"""FastAPI service: FR14 -- /api/report, /api/audit-log, /api/run-batch,
plus the "big swing" additions: LLM narratives, the human escalation inbox,
live webhook ingestion, the adaptive intervention bandit, an Ask-the-Agent
Q&A endpoint, and a one-pager export.
"""
import threading

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import bandit
from app.audit_logger import read_all_records
from app.batch_generator import read_batch
from app.config import HAS_REAL_CREDENTIALS, HAS_LLM_CREDENTIALS, REPORT_JSON_FILE
from app.customers import build_customer_detail, build_customer_summaries
from app.decision_engine import PolicyConfig
from app.escalation_store import ActionType, latest_action_by_transaction, record_action
from app.llm_client import get_llm_client
from app.pipeline import run_pipeline
from app.report import build_report
from app.run_history import read_history
from app.simulate import simulate_policy
from app.webhook_handler import handle_razorpay_webhook

app = FastAPI(title="Revenue Recovery Agent API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Narrative generation is only worth calling once per transaction per
# process lifetime -- cache so repeatedly opening the same row in the UI
# doesn't re-spend an LLM call (or re-run the simulated template) each time.
_narrative_cache: dict[str, dict] = {}

# Starlette runs sync `def` routes in a thread pool, so concurrent requests
# genuinely race -- most visibly, the frontend's Promise.all([fetchReport(),
# fetchAuditLog()]) hitting a freshly-deployed (empty reports/) backend at
# the same time, with both requests independently deciding "no data yet"
# and calling run_pipeline(), interleaving writes to the same files. This
# lock plus the double-checked REPORT_JSON_FILE guard makes "ensure the
# pipeline has run" idempotent under concurrency: whichever request gets
# the lock first runs it once, everyone else just waits and then reads.
_pipeline_lock = threading.Lock()


def _client_mode() -> str:
    return "RealRazorpayClient" if HAS_REAL_CREDENTIALS else "SimulatedRazorpayClient"


def ensure_pipeline_has_run() -> None:
    if REPORT_JSON_FILE.exists():
        return
    with _pipeline_lock:
        if REPORT_JSON_FILE.exists():  # re-check: another thread may have just finished
            return
        run_pipeline()


def run_pipeline_exclusive() -> dict:
    """For the explicit POST /api/run-batch -- always re-runs, but still
    takes the lock so it can't interleave with a concurrent lazy trigger
    from another in-flight GET request.
    """
    with _pipeline_lock:
        return run_pipeline()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "client_mode": _client_mode(),
        "llm_mode": "RealLLMClient" if HAS_LLM_CREDENTIALS else "SimulatedLLMClient",
    }


@app.get("/api/report")
def get_report():
    ensure_pipeline_has_run()
    report = build_report()
    report["client_mode"] = _client_mode()
    return report


@app.get("/api/audit-log")
def get_audit_log():
    ensure_pipeline_has_run()
    records = read_all_records()
    return {"count": len(records), "records": records}


@app.post("/api/run-batch")
def run_batch():
    try:
        return run_pipeline_exclusive()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# LLM narratives
# ---------------------------------------------------------------------------


@app.get("/api/narrative/{transaction_id}")
def get_narrative(transaction_id: str):
    if transaction_id in _narrative_cache:
        return _narrative_cache[transaction_id]

    record = next((r for r in read_all_records() if r["transaction_id"] == transaction_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="transaction not found in audit log")

    client = get_llm_client()
    result = client.generate_narrative(record, record)
    response = {
        "transaction_id": transaction_id,
        "provider": result.provider,
        **result.narrative.model_dump(),
    }
    _narrative_cache[transaction_id] = response
    return response


# ---------------------------------------------------------------------------
# Human escalation inbox
# ---------------------------------------------------------------------------


class EscalationActionRequest(BaseModel):
    action: ActionType
    note: str = ""


@app.get("/api/escalations")
def get_escalations():
    ensure_pipeline_has_run()
    records = [r for r in read_all_records() if r["outcome"] == "escalated"]
    actions = latest_action_by_transaction()
    items = []
    for r in records:
        latest = actions.get(r["transaction_id"])
        items.append(
            {
                **r,
                "resolution_status": latest["action"] if latest else "open",
                "resolution_note": latest["note"] if latest else "",
                "resolution_timestamp": latest["timestamp"] if latest else None,
            }
        )
    open_count = sum(1 for i in items if i["resolution_status"] == "open")
    return {"count": len(items), "open_count": open_count, "items": items}


@app.post("/api/escalations/{transaction_id}/action")
def post_escalation_action(transaction_id: str, body: EscalationActionRequest):
    record = next((r for r in read_all_records() if r["transaction_id"] == transaction_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="transaction not found in audit log")
    if record["outcome"] != "escalated":
        raise HTTPException(status_code=400, detail="transaction was not escalated")
    return record_action(transaction_id, body.action, body.note)


# ---------------------------------------------------------------------------
# Live webhook ingestion
# ---------------------------------------------------------------------------


@app.post("/webhooks/razorpay")
def razorpay_webhook(payload: dict):
    try:
        result = handle_razorpay_webhook(payload)
    except (KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"malformed webhook payload: {exc}")
    if result is None:
        return {"status": "ignored", "reason": "unhandled event type"}
    return result


# ---------------------------------------------------------------------------
# Adaptive intervention selection (bandit)
# ---------------------------------------------------------------------------


@app.get("/api/bandit-state")
def get_bandit_state():
    return bandit.get_all_arm_stats()


# ---------------------------------------------------------------------------
# Ask the Agent -- natural-language Q&A over the audit log
# ---------------------------------------------------------------------------


class AskMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AskRequest(BaseModel):
    question: str
    history: list[AskMessage] = []


@app.post("/api/ask")
def ask_agent(body: AskRequest):
    ensure_pipeline_has_run()
    records = read_all_records()
    report = build_report(records)
    client = get_llm_client()
    result = client.answer_question(
        body.question, report, records, [m.model_dump() for m in body.history]
    )
    return result.model_dump()


# ---------------------------------------------------------------------------
# One-pager export
# ---------------------------------------------------------------------------


@app.get("/api/onepager")
def get_onepager():
    ensure_pipeline_has_run()
    records = read_all_records()
    report = build_report(records)
    client = get_llm_client()
    result = client.generate_onepager_html(report)
    return result.model_dump()


# ---------------------------------------------------------------------------
# Guardrail policy simulator ("what-if" sliders)
# ---------------------------------------------------------------------------


class SimulateRequest(BaseModel):
    max_retries: int = PolicyConfig.max_retries
    recurring_cooldown_hours: int = PolicyConfig.recurring_cooldown_hours
    non_recurring_cooldown_hours: int = PolicyConfig.non_recurring_cooldown_hours
    escalation_amount_threshold_inr: float = PolicyConfig.escalation_amount_threshold_inr
    incentive_target_pct: float = PolicyConfig.incentive_target_pct
    margin_safety_buffer_pct: float = PolicyConfig.margin_safety_buffer_pct


@app.post("/api/simulate")
def post_simulate(body: SimulateRequest):
    batch = read_batch()
    policy = PolicyConfig(**body.model_dump())
    return simulate_policy(batch, policy)


@app.get("/api/simulate/defaults")
def get_simulate_defaults():
    return PolicyConfig().__dict__


# ---------------------------------------------------------------------------
# Customer 360
# ---------------------------------------------------------------------------


@app.get("/api/customers")
def get_customers():
    ensure_pipeline_has_run()
    records = read_all_records()
    return {"customers": build_customer_summaries(records)}


@app.get("/api/customers/{customer_id}")
def get_customer_detail(customer_id: str):
    records = read_all_records()
    detail = build_customer_detail(records, customer_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="customer not found in audit log")
    return detail


# ---------------------------------------------------------------------------
# Run history -- the learning curve across successive real pipeline runs
# ---------------------------------------------------------------------------


@app.get("/api/run-history")
def get_run_history():
    ensure_pipeline_has_run()
    history = read_history()
    return {"count": len(history), "runs": history}
