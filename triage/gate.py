"""Mock human-approval gate for proposed response actions.

Nothing is ever executed. The gate records exactly what was proposed,
binds the approval to those exact parameters, and returns 'pending'.
Any later change to the parameters would need a new approval.
"""
from __future__ import annotations

import hashlib
import json


def request_approval(action: dict) -> dict:
    canonical = json.dumps(action, sort_keys=True, separators=(",", ":"))
    return {
        "action": action,
        "binding_hash": hashlib.sha256(canonical.encode()).hexdigest(),
        "status": "pending_human_approval",
        "executed": False,  # always False: this project never runs real responses
    }
