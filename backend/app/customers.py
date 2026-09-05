"""Customer 360: groups the audit log by customer_id. Purely an aggregation
over the existing audit log (FR9's single source of truth) -- no new
decision-engine logic, just a different lens on data that already exists.
Meaningful because customer_id repeats across records in this project's
data: batch_generator.py cycles synthetic customers across at-risk
transactions, and the live webhook simulator deliberately reuses a small
pool of customers to build real retry history over wall-clock time.
"""
from collections import defaultdict


def build_customer_summaries(records: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        grouped[r.get("customer_id") or r["customer_name"]].append(r)

    summaries = []
    for customer_id, txns in grouped.items():
        total_at_risk = sum(t["amount_inr"] for t in txns)
        total_recovered = sum(t.get("recovered_inr", 0) for t in txns)
        escalated_count = sum(1 for t in txns if t["outcome"] == "escalated")
        summaries.append(
            {
                "customer_id": customer_id,
                "customer_name": txns[0]["customer_name"],
                "transaction_count": len(txns),
                "total_at_risk_inr": round(total_at_risk, 2),
                "total_recovered_inr": round(total_recovered, 2),
                "escalated_count": escalated_count,
                "is_repeat": len(txns) > 1,
                "has_live_activity": any(t.get("source") == "webhook" for t in txns),
            }
        )

    summaries.sort(key=lambda s: (s["escalated_count"], s["total_at_risk_inr"]), reverse=True)
    return summaries


def build_customer_detail(records: list[dict], customer_id: str) -> dict | None:
    txns = [r for r in records if (r.get("customer_id") or r["customer_name"]) == customer_id]
    if not txns:
        return None
    txns_sorted = sorted(txns, key=lambda t: t["timestamp"])
    summary = build_customer_summaries(txns)[0]
    return {**summary, "transactions": txns_sorted}
