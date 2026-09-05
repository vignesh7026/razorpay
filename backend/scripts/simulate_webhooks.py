"""Drives real-time, event-by-event traffic into POST /webhooks/razorpay --
proof that the live ingestion path (app/webhook_handler.py) actually works,
not just the batch path. Run this while the FastAPI server is up and watch
the dashboard's Live Feed update as each event lands.

Usage:
    python scripts/simulate_webhooks.py [--count 30] [--interval 2.0] [--url http://127.0.0.1:8000]
"""
import argparse
import json
import random
import time
import urllib.error
import urllib.request

# A small pool of recurring "live customers" -- weighted so a few repeat
# often enough to accumulate retry history and demonstrably trip SR1 (max
# retries) and SR5 (high-value escalation) in real time, not just in the
# seeded batch.
LIVE_CUSTOMERS = [
    {"customer_id": "cust_live_01", "customer_name": "Kavya Nair", "sku": "SKU-1002",
     "product_name": "Smart Fitness Band", "amount_paise": 149900, "margin": 0.18,
     "is_recurring": False, "failure_reason": "card_declined", "weight": 3},
    {"customer_id": "cust_live_02", "customer_name": "Rohan Mehta", "sku": "SKU-1007",
     "product_name": "Cloud Storage 1TB - Annual", "amount_paise": 899900, "margin": 0.62,
     "is_recurring": False, "failure_reason": "insufficient_funds", "weight": 2},
    {"customer_id": "cust_live_03", "customer_name": "Ishaan Verma", "sku": "SKU-1011",
     "product_name": "Language Learning Pro - Yearly", "amount_paise": 699900, "margin": 0.58,
     "is_recurring": True, "failure_reason": "mandate_insufficient_funds", "weight": 2},
    {"customer_id": "cust_live_04", "customer_name": "Ananya Rao", "sku": "SKU-1004",
     "product_name": "Premium OTT Plan", "amount_paise": 29900, "margin": 0.55,
     "is_recurring": True, "failure_reason": "mandate_expired", "weight": 1},
    {"customer_id": "cust_live_05", "customer_name": "Farhan Sheikh", "sku": "SKU-1019",
     "product_name": "Smart Watch Series X", "amount_paise": 1299900, "margin": 0.21,
     "is_recurring": False, "failure_reason": "card_declined", "weight": 2},
    {"customer_id": "cust_live_06", "customer_name": "Meera Iyer", "sku": "SKU-1013",
     "product_name": "Organic Grocery Box - Weekly", "amount_paise": 89900, "margin": 0.10,
     "is_recurring": False, "failure_reason": "gateway_timeout", "weight": 3},
]


def build_event(customer: dict) -> dict:
    return {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_{random.randint(10**9, 10**10 - 1)}",
                    "amount": customer["amount_paise"],
                    "currency": "INR",
                    "error_reason": customer["failure_reason"],
                    "notes": {
                        "customer_id": customer["customer_id"],
                        "customer_name": customer["customer_name"],
                        "sku": customer["sku"],
                        "product_name": customer["product_name"],
                        "product_margin_pct": str(customer["margin"]),
                        "is_recurring": str(customer["is_recurring"]).lower(),
                        "failure_reason": customer["failure_reason"],
                    },
                }
            }
        },
    }


def post_event(url: str, event: dict) -> dict:
    data = json.dumps(event).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Simulate live Razorpay webhook traffic.")
    parser.add_argument("--count", type=int, default=30, help="number of events to send")
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between events")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="backend base URL")
    args = parser.parse_args()

    endpoint = f"{args.url.rstrip('/')}/webhooks/razorpay"
    weights = [c["weight"] for c in LIVE_CUSTOMERS]

    print(f"Streaming {args.count} live webhook events to {endpoint} every {args.interval}s...\n")
    for i in range(args.count):
        customer = random.choices(LIVE_CUSTOMERS, weights=weights, k=1)[0]
        event = build_event(customer)
        try:
            result = post_event(endpoint, event)
        except urllib.error.URLError as exc:
            print(f"[{i + 1}/{args.count}] FAILED to reach {endpoint}: {exc}")
            break

        if result is None:
            print(f"[{i + 1}/{args.count}] {customer['customer_name']} -- event ignored")
        else:
            print(
                f"[{i + 1}/{args.count}] {result['transaction_id']} "
                f"{customer['customer_name']} ({customer['failure_reason']}) -> "
                f"{result['intervention_chosen']} | rule={result['rule_fired']} | "
                f"outcome={result['outcome']}"
            )
        time.sleep(args.interval)

    print("\nDone. Check the dashboard's Live Feed / Audit trail for these transactions.")


if __name__ == "__main__":
    main()
