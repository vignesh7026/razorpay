"""Builds report.json and report.md straight from the audit log (FR9-13).

Never computes a number the audit log doesn't already contain -- this
module only aggregates app.audit_logger.read_all_records().
"""
import json
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone

from app.config import (
    NAIVE_RETRY_IMPOSSIBLE_REASONS,
    NAIVE_RETRY_SUCCESS_RATE,
    REPORT_JSON_FILE,
    REPORT_MD_FILE,
)
from app.audit_logger import read_all_records

FAILURE_REASON_ORDER = [
    "card_declined",
    "checkout_abandoned",
    "insufficient_funds",
    "gateway_timeout",
    "otp_timeout",
    "mandate_insufficient_funds",
    "mandate_expired",
]


def _compute_baseline_comparison(records: list[dict]) -> dict:
    """Counterfactual: what a naive 'just retry everything the same generic
    way' strategy would have recovered, vs. the decision engine's actual
    result -- the PRD's own thesis (G2: never a generic retry) made
    measurable rather than asserted.
    """
    no_action = 0.0  # trivial floor: zero automated intervention recovers nothing

    naive_retry = 0.0
    for r in records:
        if r["failure_reason"] in NAIVE_RETRY_IMPOSSIBLE_REASONS:
            continue
        naive_retry += r["amount_inr"] * NAIVE_RETRY_SUCCESS_RATE

    agent_recovered = sum(r.get("recovered_inr", 0) for r in records)
    uplift_inr = agent_recovered - naive_retry

    return {
        "no_action_recovered_inr": round(no_action, 2),
        "naive_generic_retry_recovered_inr": round(naive_retry, 2),
        "agent_recovered_inr": round(agent_recovered, 2),
        "uplift_vs_naive_retry_inr": round(uplift_inr, 2),
        "uplift_vs_naive_retry_pct": round(uplift_inr / naive_retry, 4) if naive_retry else None,
        "naive_retry_success_rate_assumed": NAIVE_RETRY_SUCCESS_RATE,
        "structurally_unretryable_reasons": sorted(NAIVE_RETRY_IMPOSSIBLE_REASONS),
    }


def _compute_margin_analysis(records: list[dict]) -> dict:
    """Net, margin-adjusted view: gross recovered rupees vs. actual profit
    captured, since recovering a low-margin SKU is worth far less to the
    merchant than recovering a high-margin one at the same rupee amount.
    """
    at_risk_profit = sum(r["amount_inr"] * r.get("product_margin_pct", 0) for r in records)

    recovered_profit = 0.0
    incentive_cost = 0.0
    for r in records:
        if r["outcome"] != "recovered":
            continue
        recovered_profit += r.get("recovered_inr", 0) * r.get("product_margin_pct", 0)
        if r.get("incentive_pct", 0) > 0:
            incentive_cost += r["amount_inr"] - r.get("recovered_inr", 0)

    return {
        "at_risk_profit_inr": round(at_risk_profit, 2),
        "recovered_profit_inr": round(recovered_profit, 2),
        "margin_recovery_rate": round(recovered_profit / at_risk_profit, 4) if at_risk_profit else 0.0,
        "total_incentive_cost_inr": round(incentive_cost, 2),
    }


def build_report(records: list[dict] | None = None) -> dict:
    records = records if records is not None else read_all_records()

    total_at_risk = sum(r["amount_inr"] for r in records)
    total_recovered = sum(r.get("recovered_inr", 0) for r in records)

    by_reason: dict[str, dict] = defaultdict(
        lambda: {"at_risk_inr": 0.0, "recovered_inr": 0.0, "rate": 0.0, "count": 0}
    )
    for r in records:
        bucket = by_reason[r["failure_reason"]]
        bucket["at_risk_inr"] += r["amount_inr"]
        bucket["recovered_inr"] += r.get("recovered_inr", 0)
        bucket["count"] += 1

    for reason, bucket in by_reason.items():
        bucket["rate"] = round(bucket["recovered_inr"] / bucket["at_risk_inr"], 4) if bucket["at_risk_inr"] else 0.0
        bucket["at_risk_inr"] = round(bucket["at_risk_inr"], 2)
        bucket["recovered_inr"] = round(bucket["recovered_inr"], 2)

    ordered_by_reason = OrderedDict(
        (reason, by_reason[reason])
        for reason in FAILURE_REASON_ORDER
        if reason in by_reason
    )

    counts_by_outcome: dict[str, int] = defaultdict(int)
    for r in records:
        counts_by_outcome[r["outcome"]] += 1

    # Deterministic, non-cherry-picked: first escalated record encountered
    # in log order (log order == batch generation order, itself seeded).
    escalated_example = next((r for r in records if r["outcome"] == "escalated"), None)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "total_transactions": len(records),
        "total_at_risk_inr": round(total_at_risk, 2),
        "total_recovered_inr": round(total_recovered, 2),
        "recovery_rate_overall": round(total_recovered / total_at_risk, 4) if total_at_risk else 0.0,
        "by_failure_reason": ordered_by_reason,
        "escalated_example": escalated_example,
        "counts_by_outcome": dict(counts_by_outcome),
        "baseline_comparison": _compute_baseline_comparison(records),
        "margin_analysis": _compute_margin_analysis(records),
    }
    return report


def _fmt_inr(amount: float) -> str:
    return f"Rs {amount:,.0f}"


def render_markdown(report: dict) -> str:
    lines = []
    lines.append("# Revenue Recovery Report")
    lines.append("")
    lines.append(f"_Generated {report['generated_at']}_")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append(f"- **Total at-risk revenue:** {_fmt_inr(report['total_at_risk_inr'])}")
    lines.append(f"- **Total recovered revenue:** {_fmt_inr(report['total_recovered_inr'])}")
    lines.append(f"- **Overall recovery rate:** {report['recovery_rate_overall'] * 100:.1f}%")
    lines.append(f"- **Transactions processed:** {report['total_transactions']}")
    lines.append("")
    lines.append("## Recovery rate by failure reason")
    lines.append("")
    lines.append("| failure_reason | count | at-risk (Rs) | recovered (Rs) | rate |")
    lines.append("|---|---|---|---|---|")
    for reason, bucket in report["by_failure_reason"].items():
        lines.append(
            f"| {reason} | {bucket['count']} | {bucket['at_risk_inr']:,.0f} | "
            f"{bucket['recovered_inr']:,.0f} | {bucket['rate'] * 100:.1f}% |"
        )
    lines.append("")
    lines.append("## Baseline comparison (counterfactual)")
    lines.append("")
    bc = report["baseline_comparison"]
    lines.append(f"- **No action (0% recovery):** {_fmt_inr(bc['no_action_recovered_inr'])}")
    lines.append(
        f"- **Naive generic retry only** (flat {bc['naive_retry_success_rate_assumed'] * 100:.0f}% "
        f"success, skipping {', '.join(bc['structurally_unretryable_reasons'])} where a blind retry "
        f"cannot work at all): {_fmt_inr(bc['naive_generic_retry_recovered_inr'])}"
    )
    lines.append(f"- **This agent:** {_fmt_inr(bc['agent_recovered_inr'])}")
    uplift_pct = f"{bc['uplift_vs_naive_retry_pct'] * 100:.1f}%" if bc["uplift_vs_naive_retry_pct"] is not None else "n/a"
    lines.append(f"- **Uplift over naive retry:** {_fmt_inr(bc['uplift_vs_naive_retry_inr'])} ({uplift_pct})")
    lines.append("")
    lines.append("## Margin-adjusted view")
    lines.append("")
    ma = report["margin_analysis"]
    lines.append(f"- **At-risk gross profit:** {_fmt_inr(ma['at_risk_profit_inr'])}")
    lines.append(f"- **Recovered gross profit:** {_fmt_inr(ma['recovered_profit_inr'])}")
    lines.append(f"- **Margin recovery rate:** {ma['margin_recovery_rate'] * 100:.1f}%")
    lines.append(f"- **Total incentive cost paid out:** {_fmt_inr(ma['total_incentive_cost_inr'])}")
    lines.append("")
    lines.append("## Outcome breakdown")
    lines.append("")
    for outcome, count in report["counts_by_outcome"].items():
        lines.append(f"- **{outcome}:** {count}")
    lines.append("")
    lines.append("## Escalated case (surfaced in full, not cherry-picked)")
    lines.append("")
    ex = report["escalated_example"]
    if ex:
        lines.append(f"- Transaction: `{ex['transaction_id']}` ({ex['customer_name']}, {ex['product_name']})")
        lines.append(f"- Failure reason: `{ex['failure_reason']}`")
        lines.append(f"- Amount at risk: {_fmt_inr(ex['amount_inr'])}")
        lines.append(f"- Rule fired: `{ex['rule_fired']}`")
        lines.append(f"- Stopping rule hit: `{ex['stopping_rule_hit']}`")
        lines.append(f"- Notes: {ex['rule_notes']}")
    else:
        lines.append("_No escalated case in this run._")
    lines.append("")
    return "\n".join(lines)


def write_report(records: list[dict] | None = None) -> dict:
    report = build_report(records)
    REPORT_JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    with open(REPORT_MD_FILE, "w", encoding="utf-8") as f:
        f.write(render_markdown(report))
    return report


if __name__ == "__main__":
    report = write_report()
    print(json.dumps(report, indent=2)[:2000])
