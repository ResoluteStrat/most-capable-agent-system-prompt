"""Cost loop — find the expensive steps so they can be made cheaper.

Each run books `cost_ticks` from the model-routing adapter (cheap=1, strong=3).
This module rolls that up by tier and by goal so an operator (or the sweep) can see
where spend concentrates and target it — the prompt's cost loop: replace expensive
steps with cheaper models, narrower subagents, cached artifacts, or deterministic
code.
"""
from __future__ import annotations

TIER_BY_COST = {1: "cheap", 3: "strong"}


def by_tier(conn) -> dict:
    out: dict[str, int] = {}
    for r in conn.execute("SELECT cost_ticks, SUM(cost_ticks) s FROM runs GROUP BY cost_ticks"):
        tier = TIER_BY_COST.get(r["cost_ticks"], "other")
        out[tier] = out.get(tier, 0) + (r["s"] or 0)
    return out


def hotspots(conn, top=5) -> list[dict]:
    rows = conn.execute(
        "SELECT g.id, g.title, COALESCE(SUM(r.cost_ticks),0) cost, COUNT(r.id) runs "
        "FROM goals g JOIN tasks t ON t.goal_id=g.id JOIN runs r ON r.task_id=t.id "
        "GROUP BY g.id ORDER BY cost DESC LIMIT ?", (top,)).fetchall()
    return [{"id": r["id"], "title": r["title"], "cost": r["cost"], "runs": r["runs"]} for r in rows]
