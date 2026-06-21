"""Trust- and risk-gated autonomy.

Autonomy is earned per skill from real outcomes (trust scores live in memory and
move on success/failure). A task's right to proceed without a human depends on
BOTH its risk and the trust accumulated in its skills:

  risk=low                  -> proceed (cheap, reversible, abundant)
  risk=medium, trust>=0.5   -> proceed
  risk=medium, trust<0.5    -> require approval (not yet earned)
  risk=high                 -> require approval (side-effecting / costly-to-undo)

Returns (require_approval: bool, reason: str). Deterministic — same inputs, same
decision — so it is testable and auditable.
"""
from __future__ import annotations

MEDIUM_TRUST_GATE = 0.5


def decide(risk: str, trust: float, kind: str) -> tuple[bool, str]:
    if risk == "high":
        return True, f"high-risk {kind}: requires human approval before side effects"
    if risk == "medium":
        if trust >= MEDIUM_TRUST_GATE:
            return False, f"medium-risk, trust {trust:.2f} ≥ {MEDIUM_TRUST_GATE} → autonomous"
        return True, f"medium-risk, trust {trust:.2f} < {MEDIUM_TRUST_GATE} → not yet earned"
    return False, "low-risk → autonomous"


def tier(trust: float) -> str:
    """Human-readable autonomy tier for a trust score (dashboard surface)."""
    if trust >= 0.75:
        return "trusted"
    if trust >= 0.55:
        return "autonomous"
    if trust >= 0.4:
        return "guided"
    return "supervised"
