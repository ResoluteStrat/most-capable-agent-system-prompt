"""Deny-first safety policy for risky executors (shell).

The harness is deterministic rails. Risky actions are gated here, not left to the
model's judgement. Default posture: deny destructive patterns; require approval
for high-risk tasks before any side effect.
"""
from __future__ import annotations

import re

# Patterns that are refused outright (deny-first). Conservative, not exhaustive —
# this is a guardrail, not a sandbox. Real isolation belongs in an exec sandbox.
DENY_PATTERNS = [
    r"\brm\s+-rf?\s+/(?:\s|$)",       # rm -rf /
    r"\brm\s+-rf?\s+~(?:/\s|\s|$)",   # rm -rf ~
    r":\(\)\s*\{.*\};:",               # fork bomb
    r"\bmkfs\b",
    r"\bdd\s+if=.*of=/dev/",
    r">\s*/dev/sd",
    r"\bchmod\s+-R\s+777\s+/",
    r"\bgit\s+push\b.*--force\b.*\bmain\b",
    r"\bshutdown\b|\breboot\b",
    r"curl[^|]*\|\s*(?:ba)?sh",        # curl | sh
    r"wget[^|]*\|\s*(?:ba)?sh",
]

_DENY_RE = [re.compile(p) for p in DENY_PATTERNS]


def check_shell(cmd: str) -> tuple[bool, str]:
    """Return (allowed, reason). allowed=False means refuse the command."""
    for rx in _DENY_RE:
        if rx.search(cmd):
            return False, f"denied by policy: matches /{rx.pattern}/"
    return True, "ok"


def requires_approval(task_risk: str, kind: str) -> bool:
    """High-risk side-effecting tasks pause for human approval before execution."""
    return task_risk == "high" and kind in {"shell", "python"}
