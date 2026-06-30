"""Memory consolidation loop — compress episodic logs into semantic facts.

Episodic memory accumulates one entry per task outcome (task.done/failed/resumed).
Over time that's noise. This loop rolls those raw episodes up — by executor kind —
into a small set of stable semantic facts ("kind=X: N done, M failed, success S")
that are cheap to read and stay current. Idempotent: re-running updates the same
facts rather than duplicating them. Non-destructive by default (the raw episodes
remain; `--prune` trims the oldest beyond a cap).
"""
from __future__ import annotations

from .db import emit, now


def _upsert_semantic(conn, key, value):
    row = conn.execute("SELECT id FROM memory WHERE mtype='semantic' AND mkey=?", (key,)).fetchone()
    if row:
        conn.execute("UPDATE memory SET value=?, ts=?, uses=uses+1 WHERE id=?", (value, now(), row["id"]))
    else:
        conn.execute("INSERT INTO memory (ts,mtype,mkey,value,tags,provenance,confidence) "
                     "VALUES (?,?,?,?,?,?,?)",
                     (now(), "semantic", key, value, '["memory","summary"]', "consolidate", 0.7))
    conn.commit()


def consolidate(conn, prune=False, keep=500) -> dict:
    """Roll up task outcomes by executor kind into semantic summaries."""
    episodics = conn.execute("SELECT COUNT(*) c FROM memory WHERE mtype='episodic'").fetchone()["c"]
    rows = conn.execute(
        "SELECT kind, status, COUNT(*) c FROM tasks GROUP BY kind, status").fetchall()
    agg: dict[str, dict] = {}
    for r in rows:
        agg.setdefault(r["kind"], {})[r["status"]] = r["c"]
    for kind, by in agg.items():
        done, failed = by.get("done", 0), by.get("failed", 0)
        finished = done + failed
        rate = round(done / finished, 2) if finished else 0.0
        _upsert_semantic(conn, f"memory.summary:kind:{kind}",
                         f"kind={kind}: {done} done, {failed} failed, success {rate}")
    pruned = 0
    if prune and episodics > keep:
        # keep the most recent `keep` episodics; the summaries preserve the signal
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM memory WHERE mtype='episodic' ORDER BY id DESC LIMIT -1 OFFSET ?",
            (keep,)).fetchall()]
        if ids:
            conn.execute("DELETE FROM memory WHERE id IN (%s)" % ",".join("?" * len(ids)), ids)
            conn.commit()
            pruned = len(ids)
    emit(conn, "memory.consolidated", kinds=len(agg), episodics=episodics, pruned=pruned)
    return {"kinds": len(agg), "episodics_seen": episodics, "pruned": pruned}


def summaries(conn) -> list[dict]:
    return [{"key": r["mkey"], "value": r["value"]} for r in conn.execute(
        "SELECT mkey, value FROM memory WHERE mtype='semantic' AND mkey LIKE 'memory.summary:%' "
        "ORDER BY mkey")]
