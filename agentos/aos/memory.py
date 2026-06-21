"""Layered, inspectable memory.

Memory is a product surface, not a hidden trick. Types:
  episodic   - what happened in a specific run
  semantic   - distilled stable facts / decisions
  procedural - reusable trajectories (executor+verification recipes that worked)
  preference - user/team/env preferences
  external   - outside-world intelligence

Procedural memory is the compounding asset: every verified task records its
(kind, verification) recipe so future similar tasks can be matched and reused.
`reuse` increments uses count → feeds the memory-reuse metric.
"""
from __future__ import annotations

import sqlite3

from .db import jdumps, jloads, now


def record(conn, mtype, mkey, value, *, tags=None, provenance="", confidence=0.5):
    conn.execute(
        "INSERT INTO memory (ts, mtype, mkey, value, tags, provenance, confidence)"
        " VALUES (?,?,?,?,?,?,?)",
        (now(), mtype, mkey, value, jdumps(tags or []), provenance, confidence),
    )
    conn.commit()


def record_procedural(conn, task_row, exec_result):
    """Promote a verified task into a reusable procedural recipe."""
    kind = task_row["kind"]
    plan = jloads(task_row["verification"], {})
    key = f"recipe:{kind}:{plan.get('type','exec_ok')}"
    existing = conn.execute(
        "SELECT id, uses FROM memory WHERE mtype='procedural' AND mkey=?", (key,)
    ).fetchone()
    if existing:
        conn.execute("UPDATE memory SET uses=uses+1, confidence=MIN(0.99, confidence+0.05)"
                     " WHERE id=?", (existing["id"],))
    else:
        record(conn, "procedural", key,
               jdumps({"kind": kind, "verification": plan,
                       "example_title": task_row["title"]}),
               tags=jloads(task_row["skill_tags"], []),
               provenance=f"task:{task_row['id']}", confidence=0.6)
    conn.commit()


def find_recipe(conn, kind, vtype):
    key = f"recipe:{kind}:{vtype}"
    row = conn.execute("SELECT * FROM memory WHERE mtype='procedural' AND mkey=?",
                       (key,)).fetchone()
    if row:
        conn.execute("UPDATE memory SET uses=uses+1 WHERE id=?", (row["id"],))
        conn.commit()
    return row


def reuse_rate(conn) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(uses),0) AS reuses, COUNT(*) AS n"
        " FROM memory WHERE mtype='procedural'").fetchone()
    n = row["n"] or 0
    return (row["reuses"] / n) if n else 0.0
