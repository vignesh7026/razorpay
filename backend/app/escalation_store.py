"""Human escalation inbox: an append-only action log layered on top of the
audit log, so escalated cases become an actionable queue instead of a
dead-end row -- proving "compliant escalation... without being blindsided
by an agent doing something risky unsupervised" with a real workflow,
not just a flag in a table.

The audit log itself stays immutable (FR8/FR9's single source of truth for
*what the agent decided*); this is a separate, append-only log of *what a
human did about it* -- resolving to the latest action per transaction.
"""
import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

from app.config import ESCALATION_ACTIONS_FILE, REPORTS_DIR

ActionType = Literal["approve", "override", "resolve"]


class EscalationAction(BaseModel):
    transaction_id: str
    action: ActionType
    note: str = ""
    timestamp: str = ""


def record_action(transaction_id: str, action: ActionType, note: str = "") -> dict:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "transaction_id": transaction_id,
        "action": action,
        "note": note,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    with open(ESCALATION_ACTIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read_all_actions() -> list[dict]:
    if not ESCALATION_ACTIONS_FILE.exists():
        return []
    actions = []
    with open(ESCALATION_ACTIONS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                actions.append(json.loads(line))
    return actions


def latest_action_by_transaction() -> dict[str, dict]:
    """Reduces the append-only action log to the most recent action per
    transaction_id -- later entries in the file win.
    """
    latest: dict[str, dict] = {}
    for action in read_all_actions():
        latest[action["transaction_id"]] = action
    return latest


def reset_actions() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ESCALATION_ACTIONS_FILE.write_text("", encoding="utf-8")
