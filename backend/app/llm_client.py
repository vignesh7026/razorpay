"""LLM narrative layer: a Real (Claude API) / Simulated client pair,
mirroring razorpay_client.py's pattern exactly -- selected automatically on
whether ANTHROPIC_API_KEY is present, so the dashboard's narrative feature
works out of the box and upgrades to real generation the moment a key is
added, with every response tagged with which path produced it.

This is what turns the decision engine from "a rules table with a nice UI"
into something that reasons in language: per transaction, an LLM call
drafts the actual customer-facing recovery message, a plain-English audit
explanation, and -- for escalated cases -- a briefing a human ops agent can
act on immediately (see app.escalation_store).
"""
import json
from typing import Optional

from pydantic import BaseModel

from app.config import ANTHROPIC_API_KEY, HAS_LLM_CREDENTIALS, LLM_MODEL


class DecisionNarrative(BaseModel):
    customer_message: str
    audit_explanation: str
    escalation_briefing: Optional[str] = None


class NarrativeResult(BaseModel):
    narrative: DecisionNarrative
    provider: str  # "real" | "simulated"


class AskResult(BaseModel):
    answer: str
    provider: str


class OnePagerResult(BaseModel):
    html: str
    provider: str


ASK_SYSTEM_PROMPT = """You are an analyst answering questions about a Revenue Recovery Agent's \
run for an Indian merchant on Razorpay. You are given the full audit log (one JSON record per \
automated decision, execution details trimmed) and the aggregate report for the current batch. \
Answer the user's question grounded ONLY in this data -- cite specific transaction_ids, rupee \
amounts, and rule names where relevant. If the data doesn't support an answer, say so plainly \
instead of guessing. Keep answers concise (a few sentences, or a short list) unless the question \
asks for detail. Never invent transactions or numbers not present in the data."""


def _trim_records_for_context(records: list[dict]) -> list[dict]:
    """Strips the bulky execution.raw Razorpay payloads -- irrelevant to
    answering questions and would otherwise bloat every request's tokens.
    """
    trimmed = []
    for r in records:
        r2 = dict(r)
        execution = r2.get("execution")
        if execution:
            r2["execution"] = {
                "success": execution.get("success"),
                "provider": execution.get("provider"),
            }
        trimmed.append(r2)
    return trimmed


ONEPAGER_SYSTEM_PROMPT = """You write a single self-contained HTML document (inline <style> only, \
no external resources, no JavaScript) summarizing one run of a Revenue Recovery Agent for an \
Indian merchant on Razorpay, suitable for a judge or stakeholder to read or print to PDF. Use the \
report JSON given to you -- every number in the page must come from that JSON, never invented. \
Structure: a header with the total at-risk vs. recovered revenue and overall rate; a table \
segmented by failure_reason (never present only a blended number); the counterfactual baseline \
comparison (naive retry vs. this agent); the margin-adjusted view; the five stopping rules with a \
one-line description each; and the one escalated case given to you, in full. Design: clean, \
print-friendly, dark-on-light, a restrained accent color, system sans-serif font, generous \
whitespace, no emoji. Output ONLY the raw HTML document starting with <!doctype html>."""


def _build_onepager_prompt(report: dict) -> str:
    return json.dumps(report, indent=2, default=str)


SYSTEM_PROMPT = """You are the messaging layer for an automated payment-recovery agent \
used by an Indian e-commerce/subscription merchant on Razorpay. You are given one \
at-risk transaction and the automated decision already made about it. Produce three \
things:

1. customer_message -- the actual message that would be sent to the customer (SMS/email \
tone, under 320 characters, states the amount in rupees, never pressures or shames the \
customer, plain English). If the intervention is "manual_review" or the case is purely \
pending a cooldown, this should be a short internal placeholder like "No customer \
message sent yet -- awaiting cooldown/human review" instead of a fabricated customer text.

2. audit_explanation -- one or two plain-English sentences a non-technical reviewer could \
read to understand why the agent did what it did. Reference the specific rule that fired.

3. escalation_briefing -- ONLY if escalated_to_human is true: a short briefing (2-3 \
sentences) telling a human ops agent exactly what happened, what the automated system \
already tried (or explicitly did not try, and why), and what they should check or decide \
next. If escalated_to_human is false, this field must be null.

Be concrete and specific to the numbers given -- never generic filler."""


def _build_user_prompt(transaction: dict, decision_context: dict) -> str:
    payload = {
        "transaction_id": transaction.get("transaction_id"),
        "customer_name": transaction.get("customer_name"),
        "product_name": transaction.get("product_name"),
        "amount_inr": transaction.get("amount_inr"),
        "failure_reason": transaction.get("failure_reason"),
        "is_recurring": transaction.get("is_recurring"),
        "prior_retry_count": transaction.get("prior_retry_count"),
        "intervention_chosen": decision_context.get("intervention_chosen"),
        "rule_fired": decision_context.get("rule_fired"),
        "outcome": decision_context.get("outcome"),
        "stopping_rule_hit": decision_context.get("stopping_rule_hit"),
        "escalated_to_human": decision_context.get("escalated_to_human"),
        "incentive_pct": decision_context.get("incentive_pct"),
        "rule_notes": decision_context.get("rule_notes"),
    }
    return json.dumps(payload, indent=2)


class SimulatedLLMClient:
    """Template-based fallback. Clearly labeled, never calls a real API."""

    def generate_narrative(self, transaction: dict, decision_context: dict) -> NarrativeResult:
        amount = transaction.get("amount_inr", 0)
        product = transaction.get("product_name", "your order")
        customer_first = (transaction.get("customer_name") or "there").split(" ")[0]
        intervention = decision_context.get("intervention_chosen", "")
        escalated = bool(decision_context.get("escalated_to_human"))
        rule = decision_context.get("rule_fired", "")
        incentive_pct = decision_context.get("incentive_pct") or 0

        if decision_context.get("stopping_rule_hit") == "cooldown_active":
            customer_message = "No customer message sent yet -- awaiting cooldown before the next automated retry."
        elif intervention == "manual_review":
            customer_message = "No customer message sent yet -- this case is queued for manual review."
        elif intervention == "request_reauthorization":
            customer_message = (
                f"Hi {customer_first}, your saved payment method for {product} has expired. "
                f"Please re-authorize it to continue -- amount due: Rs {amount:,.0f}."
            )
        elif intervention == "create_payment_link" and incentive_pct > 0:
            customer_message = (
                f"Hi {customer_first}, complete your order for {product} in the next 24h and save "
                f"{incentive_pct * 100:.0f}% -- Rs {amount * (1 - incentive_pct):,.0f} instead of Rs {amount:,.0f}."
            )
        elif intervention == "create_payment_link":
            customer_message = (
                f"Hi {customer_first}, we couldn't complete your payment of Rs {amount:,.0f} for {product}. "
                f"Here's a fresh link to try again with a different method."
            )
        else:
            customer_message = (
                f"Hi {customer_first}, we're retrying your payment of Rs {amount:,.0f} for {product} now."
            )

        audit_explanation = (
            f"Rule `{rule}` fired for this {transaction.get('failure_reason', 'failure')} case, "
            f"routing it to `{intervention}`."
        )
        if escalated:
            audit_explanation += " A human is also being looped in per the applicable stopping rule."

        escalation_briefing = None
        if escalated:
            escalation_briefing = (
                f"Transaction {transaction.get('transaction_id')} (Rs {amount:,.0f}, {product}) was "
                f"escalated by rule `{rule}`. The automated path chosen was `{intervention}`; review the "
                f"transaction's history and confirm whether to approve that path, override it, or contact "
                f"the customer directly."
            )

        return NarrativeResult(
            narrative=DecisionNarrative(
                customer_message=customer_message,
                audit_explanation=audit_explanation,
                escalation_briefing=escalation_briefing,
            ),
            provider="simulated",
        )

    def answer_question(self, question: str, report: dict, records: list[dict], history: list[dict]) -> AskResult:
        q = question.lower()

        def fmt(n):
            return f"Rs {n:,.0f}"

        if "escalat" in q:
            example = report.get("escalated_example")
            answer = (
                f"{report['counts_by_outcome'].get('escalated', 0)} transactions were escalated to a "
                f"human this run, totalling the amounts flagged by SR1/SR3/SR5."
            )
            if example:
                answer += (
                    f" Example: {example['transaction_id']} ({fmt(example['amount_inr'])}, "
                    f"{example['failure_reason']}) -- rule `{example['rule_fired']}`."
                )
            return AskResult(answer=answer, provider="simulated")

        if "baseline" in q or "naive" in q or "uplift" in q:
            bc = report["baseline_comparison"]
            answer = (
                f"This agent recovered {fmt(bc['agent_recovered_inr'])} vs. an estimated "
                f"{fmt(bc['naive_generic_retry_recovered_inr'])} for a naive retry-everything "
                f"strategy -- an uplift of {fmt(bc['uplift_vs_naive_retry_inr'])}"
                + (f" ({bc['uplift_vs_naive_retry_pct'] * 100:.0f}%)." if bc["uplift_vs_naive_retry_pct"] else ".")
            )
            return AskResult(answer=answer, provider="simulated")

        if "margin" in q or "profit" in q:
            ma = report["margin_analysis"]
            answer = (
                f"Recovered gross profit is {fmt(ma['recovered_profit_inr'])} against "
                f"{fmt(ma['at_risk_profit_inr'])} at-risk profit ({ma['margin_recovery_rate'] * 100:.1f}% margin "
                f"recovery rate); total incentive cost paid out was {fmt(ma['total_incentive_cost_inr'])}."
            )
            return AskResult(answer=answer, provider="simulated")

        if "best" in q or "highest" in q or "worst" in q or "lowest" in q:
            buckets = report["by_failure_reason"]
            best = max(buckets.items(), key=lambda kv: kv[1]["rate"])
            worst = min(buckets.items(), key=lambda kv: kv[1]["rate"])
            answer = (
                f"Highest recovery rate: {best[0]} at {best[1]['rate'] * 100:.1f}%. "
                f"Lowest: {worst[0]} at {worst[1]['rate'] * 100:.1f}%."
            )
            return AskResult(answer=answer, provider="simulated")

        if "rate" in q or "recover" in q:
            answer = (
                f"Overall recovery rate is {report['recovery_rate_overall'] * 100:.1f}% "
                f"({fmt(report['total_recovered_inr'])} of {fmt(report['total_at_risk_inr'])} at risk)."
            )
            return AskResult(answer=answer, provider="simulated")

        return AskResult(
            answer=(
                "This is the simulated fallback -- it only recognizes a few keywords "
                "(recovery rate, escalated, baseline/uplift, margin/profit, best/worst failure reason). "
                "Add ANTHROPIC_API_KEY to backend/.env for free-form Q&A over the full audit log."
            ),
            provider="simulated",
        )

    def generate_onepager_html(self, report: dict) -> OnePagerResult:
        return OnePagerResult(html=_render_onepager_template(report), provider="simulated")


def _render_onepager_template(report: dict) -> str:
    def inr(n):
        return f"Rs {n:,.0f}"

    rows = "".join(
        f"<tr><td>{reason}</td><td>{b['count']}</td><td>{inr(b['at_risk_inr'])}</td>"
        f"<td>{inr(b['recovered_inr'])}</td><td>{b['rate'] * 100:.1f}%</td></tr>"
        for reason, b in report["by_failure_reason"].items()
    )
    ex = report.get("escalated_example")
    ex_html = (
        f"<p><strong>{ex['transaction_id']}</strong> &mdash; {ex['customer_name']}, {ex['product_name']}<br>"
        f"Amount at risk: {inr(ex['amount_inr'])} &middot; Rule fired: <code>{ex['rule_fired']}</code><br>"
        f"{ex['rule_notes']}</p>"
        if ex
        else "<p>No escalated case in this run.</p>"
    )
    bc, ma = report["baseline_comparison"], report["margin_analysis"]

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Revenue Recovery Agent -- Run Summary</title>
<style>
  body {{ font-family: -apple-system, 'Segoe UI', sans-serif; color: #171717; max-width: 780px;
          margin: 48px auto; padding: 0 24px; line-height: 1.55; }}
  h1 {{ font-size: 22px; margin-bottom: 2px; }}
  .sub {{ color: #6b6b6b; font-size: 13px; margin-bottom: 28px; }}
  .kpis {{ display: flex; gap: 20px; margin-bottom: 28px; }}
  .kpi {{ flex: 1; border: 1px solid #e3e3e3; border-radius: 10px; padding: 14px 16px; }}
  .kpi .label {{ font-size: 11px; text-transform: uppercase; color: #8a8a8a; }}
  .kpi .value {{ font-size: 20px; font-weight: 700; margin-top: 4px; }}
  h2 {{ font-size: 15px; margin-top: 32px; border-bottom: 1px solid #e3e3e3; padding-bottom: 6px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #eee; }}
  th {{ color: #8a8a8a; font-weight: 600; text-transform: uppercase; font-size: 10.5px; }}
  .rules li {{ margin-bottom: 6px; font-size: 13px; }}
  code {{ background: #f3f3f1; padding: 1px 5px; border-radius: 4px; font-size: 12px; }}
  .footer {{ margin-top: 36px; font-size: 11px; color: #999; }}
</style></head>
<body>
  <h1>Revenue Recovery Agent -- Run Summary</h1>
  <div class="sub">Generated {report['generated_at']} &middot; {report['total_transactions']} transactions</div>

  <div class="kpis">
    <div class="kpi"><div class="label">At-risk</div><div class="value">{inr(report['total_at_risk_inr'])}</div></div>
    <div class="kpi"><div class="label">Recovered</div><div class="value">{inr(report['total_recovered_inr'])}</div></div>
    <div class="kpi"><div class="label">Recovery rate</div><div class="value">{report['recovery_rate_overall'] * 100:.1f}%</div></div>
  </div>

  <h2>Recovery rate by failure reason</h2>
  <table><tr><th>Reason</th><th>Count</th><th>At risk</th><th>Recovered</th><th>Rate</th></tr>{rows}</table>

  <h2>Counterfactual baseline</h2>
  <p>No action: {inr(bc['no_action_recovered_inr'])} &middot; Naive generic retry: {inr(bc['naive_generic_retry_recovered_inr'])}
  &middot; This agent: {inr(bc['agent_recovered_inr'])} &mdash;
  <strong>+{inr(bc['uplift_vs_naive_retry_inr'])} uplift</strong> over naive retry.</p>

  <h2>Margin-adjusted view</h2>
  <p>Recovered gross profit: {inr(ma['recovered_profit_inr'])} of {inr(ma['at_risk_profit_inr'])} at-risk profit
  ({ma['margin_recovery_rate'] * 100:.1f}%). Total incentive cost paid out: {inr(ma['total_incentive_cost_inr'])}.</p>

  <h2>Guardrails</h2>
  <ul class="rules">
    <li><strong>SR1 &mdash; Max retries:</strong> no transaction auto-retried more than 3 times.</li>
    <li><strong>SR2 &mdash; Cooldown:</strong> retries respect a cooldown window before firing again.</li>
    <li><strong>SR3 &mdash; Mandate expiry:</strong> always re-authorization, never a blind retry.</li>
    <li><strong>SR4 &mdash; Margin floor:</strong> incentives capped so they never cut into product margin.</li>
    <li><strong>SR5 &mdash; High-value escalation:</strong> amount + prior failure mandatorily loops in a human.</li>
  </ul>

  <h2>Escalated case (surfaced in full, not cherry-picked)</h2>
  {ex_html}

  <div class="footer">Synthetic batch, seeded and reproducible. Audit log is the single source of truth for every number above.</div>
</body></html>"""


class RealLLMClient:
    def __init__(self):
        import anthropic  # imported lazily so the simulated path never needs the package configured

        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self._fallback = SimulatedLLMClient()

    def generate_narrative(self, transaction: dict, decision_context: dict) -> NarrativeResult:
        try:
            response = self.client.messages.parse(
                model=LLM_MODEL,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_user_prompt(transaction, decision_context)}],
                output_format=DecisionNarrative,
            )
            return NarrativeResult(narrative=response.parsed_output, provider="real")
        except Exception:  # pragma: no cover - network/API failure
            # Fall back rather than break the UI if the call fails; still
            # clearly labeled as simulated in the response.
            return self._fallback.generate_narrative(transaction, decision_context)

    def answer_question(self, question: str, report: dict, records: list[dict], history: list[dict]) -> AskResult:
        try:
            context = {
                "report": report,
                "audit_log": _trim_records_for_context(records),
            }
            system = [
                {"type": "text", "text": ASK_SYSTEM_PROMPT},
                {
                    "type": "text",
                    "text": "DATA:\n" + json.dumps(context, indent=2, default=str),
                    "cache_control": {"type": "ephemeral"},
                },
            ]
            messages = list(history) + [{"role": "user", "content": question}]
            response = self.client.messages.create(
                model=LLM_MODEL,
                max_tokens=1024,
                system=system,
                messages=messages,
            )
            text = next((b.text for b in response.content if b.type == "text"), "")
            return AskResult(answer=text, provider="real")
        except Exception:  # pragma: no cover - network/API failure
            return self._fallback.answer_question(question, report, records, history)

    def generate_onepager_html(self, report: dict) -> OnePagerResult:
        try:
            response = self.client.messages.create(
                model=LLM_MODEL,
                max_tokens=16000,
                system=ONEPAGER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_onepager_prompt(report)}],
            )
            html = next((b.text for b in response.content if b.type == "text"), "")
            if "<html" not in html.lower():
                raise ValueError("model did not return an HTML document")
            return OnePagerResult(html=html, provider="real")
        except Exception:  # pragma: no cover - network/API failure
            return self._fallback.generate_onepager_html(report)


def get_llm_client():
    if HAS_LLM_CREDENTIALS:
        try:
            return RealLLMClient()
        except Exception:
            return SimulatedLLMClient()
    return SimulatedLLMClient()
