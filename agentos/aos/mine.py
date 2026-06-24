"""Workflow-mining loop — turn repeated successful trajectories into proposals.

Every repeated success should become a reusable asset. Procedural memory already
records a recipe (executor kind + verification type) for each verified task and
counts its `uses`. This loop scans for recipes used >= a threshold that haven't
been promoted yet, and proposes promoting them to a skill/workflow — recording the
proposal in semantic memory and emitting an event so the recurring sweep surfaces
it. Idempotent: a recipe is proposed once.
"""
from __future__ import annotations

from . import memory
from .db import emit, jloads


def mine(conn, threshold=3) -> list[dict]:
    candidates = []
    rows = conn.execute(
        "SELECT mkey, uses, value FROM memory WHERE mtype='procedural' AND uses>=? ORDER BY uses DESC",
        (threshold,)).fetchall()
    for r in rows:
        promo_key = f"workflow_promotion:{r['mkey']}"
        if conn.execute("SELECT id FROM memory WHERE mkey=?", (promo_key,)).fetchone():
            continue                              # already proposed
        recipe = jloads(r["value"], {})
        memory.record(conn, "semantic", promo_key,
                      f"Recipe {r['mkey']} used {r['uses']}x — promote to a reusable "
                      f"skill/workflow (kind={recipe.get('kind')}, "
                      f"verification={recipe.get('verification', {}).get('type')}).",
                      tags=["workflow", "promotion"], provenance=r["mkey"], confidence=0.7)
        emit(conn, "workflow.candidate", recipe=r["mkey"], uses=r["uses"])
        candidates.append({"recipe": r["mkey"], "uses": r["uses"]})
    return candidates


def pending(conn) -> int:
    return conn.execute(
        "SELECT COUNT(*) c FROM memory WHERE mtype='semantic' AND mkey LIKE 'workflow_promotion:%'"
    ).fetchone()["c"]
