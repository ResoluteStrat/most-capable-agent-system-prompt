"""Workflow-mining loop — turn repeated successful trajectories into proposals.

Every repeated success should become a reusable asset. Procedural memory already
records a recipe (executor kind + verification type) for each verified task and
counts its `uses`. This loop scans for recipes used >= a threshold that haven't
been promoted yet, and proposes promoting them to a skill/workflow — recording the
proposal in semantic memory and emitting an event so the recurring sweep surfaces
it. Idempotent: a recipe is proposed once.
"""
from __future__ import annotations

from . import memory, skills
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


def candidates(conn) -> list[dict]:
    """Mined promotion candidates, each tagged with whether it's been promoted."""
    out = []
    for r in conn.execute(
            "SELECT mkey, value FROM memory WHERE mtype='semantic' AND mkey LIKE 'workflow_promotion:%'"):
        recipe_key = r["mkey"].split("workflow_promotion:", 1)[1]
        promoted = conn.execute("SELECT id FROM memory WHERE mkey=?",
                                (f"workflow_promoted:{recipe_key}",)).fetchone() is not None
        out.append({"recipe": recipe_key, "note": r["value"], "promoted": promoted})
    return out


def auto_promote(conn, min_sweeps=2, conf_gate=0.75, base_dir=None) -> list[str]:
    """Autonomy ramp: promote a candidate ONLY after it has survived `min_sweeps`
    sweeps AND its procedural recipe is confident enough (>= conf_gate, which rises
    with proven reuse). Opt-in — the sweep calls this only when asked. A repeated,
    proven workflow becomes a skill with no human in the loop."""
    promoted = []
    for c in candidates(conn):
        if c["promoted"]:
            continue
        key = c["recipe"]
        conn.execute("UPDATE memory SET uses=uses+1 WHERE mkey=?", (f"workflow_promotion:{key}",))
        conn.commit()
        wp = conn.execute("SELECT uses FROM memory WHERE mkey=?",
                          (f"workflow_promotion:{key}",)).fetchone()
        rec = conn.execute("SELECT confidence FROM memory WHERE mtype='procedural' AND mkey=?",
                           (key,)).fetchone()
        if wp["uses"] >= min_sweeps and rec and rec["confidence"] >= conf_gate:
            sk = promote(conn, key, base_dir)
            if sk:
                emit(conn, "workflow.auto_promoted", recipe=key, skill=sk.name,
                     sweeps=wp["uses"], confidence=rec["confidence"])
                promoted.append(sk.name)
    return promoted


def promote(conn, recipe_key, base_dir=None):
    """Turn a mined recipe into a scaffolded, registered skill (mine → asset).
    Idempotent: a recipe already promoted returns its existing skill."""
    rec = conn.execute("SELECT value FROM memory WHERE mtype='procedural' AND mkey=?",
                       (recipe_key,)).fetchone()
    if not rec:
        return None
    recipe = jloads(rec["value"], {})
    parts = recipe_key.split(":")
    name = "workflow " + " ".join(parts[1:])      # e.g. "workflow write_file file_contains"
    sk = skills.scaffold(
        name,
        f"Promoted from a repeated successful trajectory ({recipe_key}): "
        f"kind={recipe.get('kind')}, verification={recipe.get('verification', {}).get('type')}.",
        base_dir=base_dir)
    skills.register(conn, sk)
    promoted_key = f"workflow_promoted:{recipe_key}"
    if not conn.execute("SELECT id FROM memory WHERE mkey=?", (promoted_key,)).fetchone():
        memory.record(conn, "semantic", promoted_key, f"promoted to skill '{sk.name}'",
                      tags=["workflow", "promoted"], provenance=recipe_key, confidence=0.8)
        emit(conn, "workflow.promoted", recipe=recipe_key, skill=sk.name)
    return sk
