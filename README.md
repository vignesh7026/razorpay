# Revenue Recovery Agent

AI Revenue Recovery system built for Razorpay AI Builder Program — Track 03.
Detects at-risk revenue across a synthetic transaction batch *and* live
webhook events, decides one specific recovery intervention per transaction
(never a generic "retry"), executes it, drafts the actual customer-facing
message and a human-readable explanation via Claude, logs why, and reports
what was actually recovered — with hard stopping rules an agent cannot
cross, and a human escalation queue for the cases it won't touch alone.
Full spec in [PRD.md](PRD.md).

## Architecture

```
backend/            Python engine + FastAPI service
  app/
    config.py             constants: max retries, cooldowns, margin floor, thresholds
    batch_generator.py    synthetic 120-txn batch (seeded, reproducible)
    decision_engine.py    failure_reason -> intervention, stopping rules (SR1-SR6), PolicyConfig
    bandit.py             Thompson Sampling over candidate message variants
    fraud_detection.py    SR6: cross-transaction card-testing pattern detection
    simulate.py           "what-if" guardrail policy simulator (expected-value, no side effects)
    customers.py          Customer 360: groups the audit log by customer_id
    razorpay_client.py    RealRazorpayClient (test-mode SDK) / SimulatedRazorpayClient
    llm_client.py         RealLLMClient (Claude) / SimulatedLLMClient -- narratives, Q&A, one-pager
    recovery_executor.py  runs the decision, builds the audit record, updates the bandit
    audit_logger.py       JSONL audit log -- single source of truth
    escalation_store.py   append-only human-action log layered on escalated cases
    webhook_handler.py    live payment.failed webhook -> decide -> execute -> log
    report.py             report.json / report.md, incl. baseline & margin analysis
    pipeline.py           wires generate -> decide -> execute -> log -> report
    main.py               FastAPI routes (below)
  scripts/simulate_webhooks.py   streams live synthetic webhook traffic for a demo
  data/batch.json
  reports/audit_log.jsonl, report.json, report.md, bandit_state.json, escalation_actions.jsonl
  tests/                  pytest: every stopping rule, the bandit, the simulator, fraud detection,
                           customer grouping, report aggregation, LLM fallbacks

frontend/            React + Vite dashboard
  src/components/    Overview (gauge, KPIs, baseline/margin analysis, trend chart),
                     Guardrails, Escalation Inbox, Adaptive Learning, Transaction
                     Galaxy (3D), Guardrail Simulator, Customers (360), Audit trail
                     (+ Decision Tree Visualizer), command palette, Reasoning
                     Console, Ask-the-Agent chat, One-pager export -- cross-filtering
                     between the tabular views
  src/lib/           API client, shared rule-matching logic, formatting
  src/**/*.test.ts(x) vitest + Testing Library
```

### API routes

| Route | What it does |
|---|---|
| `GET /api/report` | segmented recovery report, incl. `baseline_comparison` and `margin_analysis` |
| `GET /api/audit-log` | full audit log |
| `POST /api/run-batch` | regenerates the batch and re-runs the whole pipeline |
| `GET /api/narrative/{transaction_id}` | Claude-drafted (or simulated) customer message + explanation + escalation briefing |
| `GET /api/escalations` | escalated cases + their human resolution status |
| `POST /api/escalations/{transaction_id}/action` | approve / override / resolve an escalated case |
| `POST /webhooks/razorpay` | live `payment.failed` ingestion — same engine, real time |
| `GET /api/bandit-state` | current posterior (estimated success rate) per message variant |
| `POST /api/ask` | natural-language Q&A over the live audit log (Claude, or a keyword-matched fallback) |
| `GET /api/onepager` | a self-contained, printable HTML run summary (Claude-authored, or template-rendered) |
| `POST /api/simulate` | "what-if" projected impact of hypothetical guardrail thresholds, no side effects |
| `GET /api/customers` / `GET /api/customers/{id}` | audit log grouped by customer_id, with per-customer detail |
| `GET /api/run-history` | a snapshot per real pipeline run — the data behind the Learning view's trend chart |

## Running it

**Backend**

```bash
cd backend
python -m venv venv
source venv/Scripts/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # optional: add Razorpay TEST-mode keys, ANTHROPIC_API_KEY
python -m app.pipeline         # runs the engine once, writes reports/
uvicorn app.main:app --port 8000 --reload
```

**Frontend** (separate terminal)

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173, proxies /api -> :8000
```

**Live webhook demo** (optional, separate terminal, backend must be running)

```bash
cd backend
python scripts/simulate_webhooks.py --count 30 --interval 2.0
```

Toggle "Live feed" on in the dashboard header first to watch transactions
land in real time — new rows carry a green live-flag dot.

**Tests**

```bash
cd backend && pytest                 # 72 tests: every stopping rule, the bandit, the simulator,
                                      # fraud detection, customer grouping, run history, report math, LLM fallbacks
cd frontend && npm test              # 18 tests: rule matching, filtering, formatting
```

Without Razorpay credentials in `backend/.env`, execution runs on
`SimulatedRazorpayClient` automatically. Without `ANTHROPIC_API_KEY`,
narratives run on `SimulatedLLMClient` (template-based). Both fall back
gracefully — the full loop works end to end either way, clearly labeled in
the UI and in every audit record's `execution.provider` /
`/api/narrative` `provider` field.

## The six stopping rules (guardrails)

| Rule | What it enforces |
|---|---|
| SR1 — max retries | no transaction auto-retried more than 3 times; a 4th attempt always escalates |
| SR2 — cooldown | recurring/insufficient-funds retries respect a cooldown window; inside it, outcome is `pending_retry`, never a forced attempt |
| SR3 — mandate expiry | `mandate_expired` always routes to re-authorization, never a blind retry, always escalates |
| SR4 — margin floor | any incentive offered is capped so it can never cut into the product's margin floor |
| SR5 — high-value escalation | amount above ₹5,000 combined with a prior failed attempt mandatorily loops in a human |
| SR6 — card-testing pattern | many distinct customers hitting card_declined at low amounts in a tight window is blocked and escalated outright — a narrow pattern guardrail, explicitly *not* a fraud model (see `app/fraud_detection.py`) |

Every threshold above (max retries, cooldown hours, the escalation amount,
the incentive target/margin buffer) is bundled into a `PolicyConfig` that
`decide()` accepts as an override — the dashboard's Guardrail Simulator
re-runs the real decision engine under hypothetical thresholds this way,
never touching the persisted run.

Every decision names the specific rule that fired — see `rule_fired` in the
audit log, the Guardrails view's live per-rule counts, and the expandable
row detail in the dashboard's audit table.

## Beyond the base loop

- **LLM reasoning layer** (`app/llm_client.py`) — every decision can be
  narrated by Claude: the actual customer-facing message, a plain-English
  explanation of the rule that fired, and — for escalated cases — a
  briefing a human agent can act on immediately. This is what turns the
  engine from a rules table into something that reasons in language.
- **Human escalation inbox** — escalated cases don't dead-end in a log. The
  Inbox view is a real action queue: read the AI briefing, then approve
  the agent's suggested path, override it, or mark it resolved, with every
  action appended to its own record (`escalation_actions.jsonl`).
- **Live webhook ingestion** (`app/webhook_handler.py`) — a real
  `payment.failed` handler wired to the exact same decision engine,
  executor, and audit log the batch uses. `scripts/simulate_webhooks.py`
  drives it locally, proving the event-by-event path works, not just the
  batch path.
- **Adaptive intervention selection** (`app/bandit.py`) — for three failure
  types, the engine runs a Thompson Sampling bandit across two candidate
  message variants instead of one fixed message forever. State persists
  across runs in `bandit_state.json`; the Learning view charts each arm's
  posterior converging as evidence accumulates.
- **Run history / learning curve** (`app/run_history.py`) — every real
  pipeline run appends a snapshot (`run_history.jsonl`); the Learning view's
  top chart plots recovery rate across runs, so the bandit's persistence is
  evidenced at the outcome level, not just asserted per-arm. Because
  learning is stochastic (exploration doesn't monotonically improve every
  single run), the chart shows whatever actually happened, including dips —
  no fabricated "always up" line.
- **Counterfactual baseline** — the report doesn't just show recovered ₹,
  it shows what a naive "retry everything the same way" strategy would
  have recovered, so the decision engine's uplift is a measured number,
  not an assertion.
- **Margin-adjusted view** — recovered gross revenue isn't recovered
  profit; the report also shows recovered ₹ weighted by each product's
  actual margin, plus total incentive cost paid out.
- **Live Agent Reasoning console** — a terminal-style drawer (toggle in the
  header) that traces the decision engine's reasoning line by line:
  `txn_id  failure_reason → rule_fired → intervention  [OUTCOME]`. "Replay
  batch" plays back the last run; with Live feed on, genuinely new
  webhook-ingested transactions print themselves as they arrive.
- **Transaction Galaxy** (`components/TransactionGalaxy.tsx`) — every
  transaction as an interactive node in a real 3D scene (react-three-fiber
  + OrbitControls), clustered by failure_reason, colored by outcome, sized
  by amount. Click a node to inspect it. Turns the dashboard's decorative
  3D background into an actual data visualization.
- **Ask the Agent** — a floating chat panel answering natural-language
  questions grounded in the current run's full audit log and report (never
  inventing numbers not present in the data). Falls back to a small set of
  keyword-matched canned answers (recovery rate, escalations, baseline
  uplift, margin, best/worst failure reason) without an API key.
- **One-pager export** — generates a clean, self-contained, printable HTML
  summary of the run (Claude-authored copy when a key is present, a
  template-rendered equivalent otherwise) with a "Print / Save as PDF"
  button — a tangible artifact beyond the live dashboard URL.
- **Guardrail Policy Simulator** (`app/simulate.py`) — sliders for every
  threshold (max retries, cooldowns, escalation amount, incentive target,
  margin buffer); dragging one re-runs the real `decide()` function over
  the current batch and shows the projected delta in recovery rate,
  escalation count, and margin, computed as expected value so the result is
  stable and attributable to that one change — a sandbox for tuning
  guardrails, never touching the actual persisted run.
- **Decision Tree Visualizer** — an interactive flowchart, reconstructed
  entirely from an audit record's own fields, showing the exact rule-by-rule
  path one transaction took (SR6 → SR3 → SR1 → handler [± SR2] → SR5 →
  final intervention), with the actually-taken branch highlighted and the
  alternative dimmed. Open it from any row in the Audit trail.
- **Customer 360** (`app/customers.py`) — every customer this run, grouped
  by `customer_id` (meaningful here since batch_generator.py cycles
  synthetic customers across transactions and the live webhook simulator
  deliberately reuses a small pool) — pick one to see their full
  cross-transaction history and risk profile.

## Honesty notes (stated, not glossed over)

- **Detection is both batch- and webhook-driven, but the webhook path is a
  local simulation.** `POST /webhooks/razorpay` is a real, working handler
  for a Razorpay-webhook-shaped payload — the same decide → execute → log
  pipeline the batch uses, running in real time. What's still simulated is
  the *source* of traffic: this dev environment has no publicly reachable
  URL for Razorpay to actually call, so `scripts/simulate_webhooks.py`
  plays that role locally. The ingestion path itself is not theoretical.
- **Conversion outcomes are probabilistic even in "real" mode.** Actually
  completing a recharge or re-authorization requires the customer to act
  (OTP, mandate approval) — no batch job or webhook handler can do that on
  their behalf. `RealRazorpayClient` creates real Razorpay test-mode
  resources (Payment Links / Orders), which proves the execution layer
  talks to Razorpay; but whether that resource ultimately "converts" is
  resolved with the same documented, bounded probability model as
  `SimulatedRazorpayClient`. Every audit record's `execution.provider`
  field says which path produced it.
- **LLM narratives are generated on demand, not for all 120+ transactions
  eagerly** — a narrative is only requested (and cached) when a row is
  actually opened in the UI, to keep the batch pipeline fast and keep API
  spend proportional to what a reviewer actually looks at.
- **Synthetic data**, not real merchant data, modeled on publicly discussed
  Indian payment-failure patterns. Seeded (`RANDOM_SEED = 42`) so batch
  results are reproducible and checkable, not a one-time lucky run.
