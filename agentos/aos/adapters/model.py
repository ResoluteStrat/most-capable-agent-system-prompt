"""Model-routing adapter (stable interface).

The engine asks this adapter which model to use for a task; it does NOT know or
care which provider answers. v1 is a deterministic stub router (no network, no
LLM call) so cost/economics flow through a real seam from day one. A future
adapter implementation can call LiteLLM / a real gateway behind the same
`route()` signature without touching the engine.

Economics rule: use the cheap tier by default; escalate to strong only when the
profile demands it or the task is high-risk (judgement-heavy / costly-to-get-wrong).
"""
from __future__ import annotations

# tier -> (model name, relative cost per tick)
TIERS = {
    "cheap": ("router/cheap", 1),
    "strong": ("router/strong", 3),
}


def route(profile: dict, risk: str = "low") -> dict:
    tier = profile.get("model_tier", "cheap")
    if risk == "high" and tier == "cheap":
        tier = "strong"            # don't be cheap on costly-to-get-wrong work
    name, cost = TIERS.get(tier, TIERS["cheap"])
    return {"tier": tier, "model": name, "cost": cost, "profile": profile.get("name", "executor")}
