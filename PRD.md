# PRD — Revenue Recovery Agent

**Program:** Razorpay AI Builder Program — Track 03, AI Revenue Recovery
**Author:** Vigneshwaran G
**Status:** In development
**Doc version:** 1.0

---

## 1. Problem statement

Revenue loss on a merchant's payments stack rarely happens as one clean
event. It shows up as a failed card charge, an abandoned checkout, a bounced
recurring/mandate debit, or an overdue invoice — each with a different root
cause and a different correct response. Today this is either not handled at
all (the revenue is just lost) or handled manually and inconsistently.

Track 03's own evaluation bar makes the actual failure mode explicit:
*"Don't just identify the problem... measured money recovered... compliant
escalation, stopping rules, and an audit trail."* Most attempts at this
class of problem stop at detection. This PRD defines a system that closes
the loop: detect → decide the right intervention → execute it against
Razorpay → log why → report what was actually recovered, in ₹, on a batch.

## 2. Goals

- **G1.** Detect at-risk revenue across a representative batch of
  transactions covering the failure types listed in Track 03's example
  directions (payment failures, checkout abandonment, failed
  subscriptions/mandates).
- **G2.** For each at-risk transaction, choose one specific, explainable
  recovery intervention — never a generic "retry."
- **G3.** Execute that intervention against Razorpay (test mode), for real
  when test-mode credentials are supplied, against a labeled simulated
  fallback otherwise.
- **G4.** Enforce hard stopping rules so the agent cannot retry indefinitely,
  discount below margin, or act unsupervised past a defined risk threshold.
- **G5.** Produce an audit trail sufficient to answer, for any transaction,
  "why did the agent do that."
- **G6.** Report a **segmented, honest** recovery metric — not one blended,
  cherry-pickable number.
- **G7.** Present all of the above in a small working dashboard, so the
  system reads as a product, not a script's console output.

## 3. Non-goals

- Not building a general-purpose fraud/risk model (that's Track 02).
- Not reconciling settlements or ledgers (that's Track 04).
- Not handling every Razorpay decline code — scope is capped to the seven
  failure types in §6.1, and that cap is stated, not hidden.
- Not a production deployment. No public webhook endpoint is stood up (see
  §8.3 for why); this is a batch-run demonstration system.
- Not optimizing for UI polish over engine correctness — see §12 (time
  allocation), where the dashboard is intentionally the smallest line item.

## 4. Users / who this is for

| User | What they need from this system |
|---|---|
| Merchant ops person (the persona this agent serves) | recovered revenue, without manual chasing, without being blindsided by an agent doing something risky unsupervised |
| Program judges / reviewers | a working system, a trustworthy number, visible reasoning, evidence of production-mindedness |
| Future-you / a mentor reading the code | a codebase that reads like a real service, not a hackathon script |

## 5. Why Track 03, and why this shape of solution

Covered in full in the project README; summarized here because it drives
every requirement below: the track is won on **completeness of the loop**,
not on any single clever step. Every requirement in this document exists to
make one specific link in that loop real rather than asserted:
detect → decide → execute → log → report, with guardrails at the decide and
execute steps.

## 6. Scope

### 6.1 Failure types in scope

| failure_reason | recurring? | intervention |
|---|---|---|
| `checkout_abandoned` | no | payment-link resend + bounded incentive |
| `card_declined` | no | resend payment link on alternate method |
| `insufficient_funds` | no | delayed retry after cooldown |
| `gateway_timeout` | no | single immediate retry |
| `otp_timeout` | no | payment-link resend |
| `mandate_expired` | yes | re-authorization request (never a blind retry) |
| `mandate_insufficient_funds` | yes | retry after cooldown, capped attempts |

### 6.2 In scope

- Synthetic batch generation (120 transactions) modeling the distribution
  above, with realistic amounts, product margins, and a subset pre-seeded
  with prior retry history (so escalation rules have real cases to fire on,
  not just first-attempt cases).
- Decision engine + stopping rules (§7).
- Execution against Razorpay test-mode Orders/Payment Links/Subscriptions
  APIs, or a simulated client when no keys are configured.
- Structured audit log, one record per decision.
- Metrics report: aggregate + segmented recovery rate, one deliberately
  surfaced escalated/unrecovered case.
- A small dashboard (FastAPI + React) rendering the above.

### 6.3 Out of scope

- Real merchant PII or production data.
- Live webhook ingestion (no public endpoint in the dev environment — see
  §8.3).
- Any interaction with real customers; all "notify"/"nudge" actions are
  simulated or sent to test-mode sandboxes only.

## 7. Functional requirements

### 7.1 Detection

- FR1. System ingests a batch of at-risk transaction records (synthetic,
  schema in §9.1).
- FR2. Each record carries enough state (`prior_retry_count`,
  `prior_retry_timestamps`, `is_recurring`, `amount_inr`,
  `product_margin_pct`) for the decision engine to make a stateful decision,
  not just a stateless classification.

### 7.2 Decision engine

- FR3. Given a transaction, the engine returns exactly one decision:
  `{intervention, rule_fired, escalate: bool, stopping_rule_hit: bool|reason}`.
- FR4. The mapping from `failure_reason` to default intervention is
  table-driven (§6.1), not hardcoded per-transaction logic scattered through
  the codebase.
- FR5. Every decision names the specific rule that fired (see §7.4 for the
  rule list) — this is what makes the audit log explain "why," not just
  "what."

### 7.3 Execution

- FR6. Execution calls a single client interface
  (`create_payment_link`, `attempt_recharge`, `request_reauthorization`)
  implemented by either `RealRazorpayClient` (test-mode SDK calls) or
  `SimulatedRazorpayClient` (probabilistic, clearly labeled), selected
  automatically based on whether `.env` has credentials.
- FR7. Every execution attempt's result (success/fail + provider response
  or simulated equivalent) is captured before the audit log is written —
  the log reflects what actually happened, not what was intended.

### 7.4 Stopping rules (guardrails) — these are requirements, not defaults

- **SR1 — Max retries.** No transaction is auto-retried more than **3**
  times. A 4th attempt is never automatic; it escalates.
- **SR2 — Recurring-payment cooldown.** For `is_recurring` transactions, a
  retry is not attempted inside the cooldown window since the last attempt
  (models RBI's recurring-payment/e-mandate retry constraints). Inside the
  cooldown, the outcome is `pending_retry`, not a forced attempt.
- **SR3 — Mandate expiry never auto-retries.** `mandate_expired` always
  routes to `request_reauthorization` and always escalates — this is a
  case where the compliant action is fundamentally different from a retry,
  not just a slower version of one.
- **SR4 — Margin floor.** Any incentive/discount offered as part of a
  recovery nudge is capped so it can never be issued at or below the
  product's margin floor.
- **SR5 — Mandatory human escalation.** Escalation is triggered by: max
  retries reached, `mandate_expired`, or `amount_inr` above a configured
  rupee threshold combined with at least one prior failed attempt.
  Escalation is a first-class logged outcome, not a silent drop.

### 7.5 Audit trail

- FR8. One JSONL record per decision with fields:
  `transaction_id, failure_reason, intervention_chosen, rule_fired,
  outcome, stopping_rule_hit, escalated_to_human, amount_inr, timestamp`.
- FR9. The audit log is the single source of truth for the report (§7.6) —
  the report never computes a number the log doesn't support.

### 7.6 Reporting

- FR10. Total at-risk revenue vs. total recovered revenue, in ₹ and %.
- FR11. Recovery rate **segmented by `failure_reason`** — required, not
  optional, specifically to avoid a single cherry-pickable headline number.
- FR12. Exactly one escalated/unrecovered case is surfaced in full detail
  in the report (this directly satisfies the "one failure handled
  gracefully" requirement from the track's own bar).
- FR13. Output as both machine-readable (`report.json`) and human-readable
  (`report.md`) artifacts.

### 7.7 Dashboard

- FR14. FastAPI service exposes `/api/report`, `/api/audit-log`, and
  `/api/run-batch` (re-runs the pipeline and returns fresh results).
- FR15. React frontend renders: KPI tiles (at-risk vs. recovered ₹),
  a categorical bar chart of recovery rate by `failure_reason`, and an
  audit-trail table with the escalated case visually flagged.
- FR16. Charts and color use follow the validated categorical palette
  (colorblind-safe, direct-labeled) rather than an arbitrary color choice.

## 8. Non-functional requirements

### 8.1 Explainability
Every automated action must be traceable to a named rule (§7.4) via the
audit log. "The model decided" is not an acceptable audit entry — "rule
`insufficient_funds_cooldown` fired because prior attempt was 2h ago" is.

### 8.2 Reproducibility
The synthetic batch is seeded (`random.seed(42)`) so the reported numbers
are re-runnable and checkable, not a one-time lucky output.

### 8.3 No live webhook dependency
Razorpay webhooks require a publicly reachable URL; the development sandbox
has none. Detection is therefore driven by the synthetic batch standing in
for webhook payloads, while **execution still calls real Razorpay test-mode
REST endpoints** via the SDK when credentials are present — so the
"real API" requirement is satisfied at the execution layer even though
detection is batch-driven rather than webhook-driven. This tradeoff is
stated explicitly rather than glossed over.

### 8.4 Honesty over polish
Per the time allocation in §12, the dashboard is the smallest investment.
If a tradeoff must be made under time pressure, engine correctness and
audit-log completeness win over dashboard polish.

## 9. Data model

### 9.1 Transaction record (synthetic batch)

```json
{
  "transaction_id": "txn_...",
  "customer_id": "cust_...",
  "customer_name": "...",
  "sku": "SKU-1001",
  "product_name": "...",
  "amount_inr": 1499,
  "product_margin_pct": 0.22,
  "is_recurring": false,
  "failure_reason": "card_declined",
  "occurred_at": "2026-08-24T10:00:00Z",
  "prior_retry_count": 0,
  "prior_retry_timestamps": [],
  "status": "at_risk"
}
```

### 9.2 Audit log record

```json
{
  "transaction_id": "txn_...",
  "failure_reason": "mandate_expired",
  "intervention_chosen": "request_reauthorization",
  "rule_fired": "mandate_expired_requires_reauth",
  "outcome": "escalated",
  "stopping_rule_hit": true,
  "escalated_to_human": true,
  "amount_inr": 9999,
  "timestamp": "2026-08-27T06:12:00Z"
}
```

### 9.3 Report schema (`report.json`)

```json
{
  "total_at_risk_inr": 0,
  "total_recovered_inr": 0,
  "recovery_rate_overall": 0.0,
  "by_failure_reason": {
    "card_declined": {"at_risk_inr": 0, "recovered_inr": 0, "rate": 0.0, "count": 0}
  },
  "escalated_example": { "...one full audit record..." },
  "counts_by_outcome": {"recovered": 0, "escalated": 0, "pending_retry": 0}
}
```

## 10. System architecture

```
┌───────────────────────┐
│ batch_generator.py     │  synthetic at-risk batch (data/batch.json)
└───────────┬───────────┘
            ▼
┌───────────────────────┐     ┌──────────────────────────┐
│ decision_engine.py     │────▶│ stopping rules (§7.4)      │
└───────────┬───────────┘     └──────────────────────────┘
            ▼
┌───────────────────────┐     ┌──────────────────────────┐
│ recovery_executor.py   │────▶│ razorpay_client.py         │
└───────────┬───────────┘     │  Real (test-mode SDK)  or  │
            ▼                  │  Simulated (fallback)      │
┌───────────────────────┐     └──────────────────────────┘
│ audit_logger.py         │  reports/audit_log.jsonl
└───────────┬───────────┘
            ▼
┌───────────────────────┐
│ report.py                │  reports/report.json, report.md
└───────────┬───────────┘
            ▼
┌───────────────────────┐     ┌──────────────────────────┐
│ FastAPI service           │────▶│ React + Vite dashboard     │
│ /api/report, /audit-log,  │    │ KPI tiles, recovery chart, │
│ /run-batch                │    │ audit table                    │
└───────────────────────┘     └──────────────────────────┘
```

## 11. Success metrics (for this submission)

- A believable, segmented recovery-rate number the judges can trust at a
  glance (not one blended headline figure).
- Every stopping rule (§7.4) demonstrably fires at least once in the batch
  run, with a visible audit entry.
- The escalated-case example (FR12) is a real, non-cherry-picked record
  pulled from the actual run.
- The dashboard runs end-to-end from a fresh clone in under 5 minutes
  (`pip install`, `.env` copy, `npm install`, one run command).

## 12. Timeline (10 days)

| Days | Focus | % of effort |
|---|---|---|
| 1–5 | Engine: client wrapper, decision engine + stopping rules, executor, audit logger, report generator, end-to-end run | 60% |
| 6–7 | FastAPI service + React dashboard | 20% |
| 8 | Polish the one escalated failure-case example | 10% |
| 9 | README, safety-design writeup, demo recording | (part of above) |
| 10 | Buffer | 10% |

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| No real Razorpay test keys available in time | `SimulatedRazorpayClient` fallback keeps the full loop demonstrable regardless |
| Synthetic data reads as "made up" to judges | Batch is modeled on publicly documented Indian payment-failure patterns, seeded/reproducible, and the README states this plainly rather than implying real merchant data |
| Frontend scope creep eats engine time | Time-boxed to 20% (§12); FR14–16 are intentionally minimal (3 endpoints, 3 UI elements) |
| A stopping rule looks good on paper but never actually fires in the demo batch | Batch generator deliberately pre-seeds some transactions with prior retry history so max-retry and mandate-expiry escalation paths are exercised, not just theoretical |

## 14. Open questions

- Exact rupee threshold for SR5 (mandatory escalation) — currently proposed
  at ₹5,000; confirm against realistic Indian e-commerce order values before
  finalizing.
- Whether to attempt real Razorpay test-mode credentials before the demo
  recording, or ship on the simulated client and state that clearly.
