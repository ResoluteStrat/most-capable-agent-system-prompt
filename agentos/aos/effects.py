"""Idempotent effect layer + sagas (reliability rules 16-17).

Retries are not enough when an action sends email, creates a ticket, triggers a
deploy, or mutates a business record. Every side-effecting action goes through the
ledger with an IDEMPOTENCY KEY so a retry replays the recorded result instead of
re-applying the effect, and every forward action records a COMPENSATION so a
multi-step workflow can roll back on partial failure (a saga). The ledger is
queryable from the control plane (`aos effects`), per the prompt's introspection
requirement.

The `do`/`undo` callables are supplied at runtime (not stored); the ledger
persists status + result + a human-readable compensation descriptor for audit.
"""
from __future__ import annotations

from .db import emit, jdumps, jloads, now


def _get(conn, key):
    return conn.execute("SELECT * FROM effects WHERE idempotency_key=?", (key,)).fetchone()


def commit(conn, key, kind, do, compensation="", saga=""):
    """Run `do()` exactly once per idempotency key. If already committed, return the
    recorded result WITHOUT re-running (idempotent replay)."""
    row = _get(conn, key)
    if row and row["status"] == "committed":
        emit(conn, "effect.replayed", key=key, effect_kind=kind)
        return jloads(row["result"], None)
    try:
        result = do()
    except Exception as e:
        _upsert(conn, key, kind, "failed", {"error": repr(e)}, compensation, saga)
        emit(conn, "effect.failed", key=key, effect_kind=kind, error=repr(e))
        raise
    _upsert(conn, key, kind, "committed", result, compensation, saga)
    emit(conn, "effect.committed", key=key, effect_kind=kind)
    return result


def compensate(conn, key, undo=None):
    """Run the recorded compensating action and mark the effect compensated.
    Idempotent: compensating an already-compensated effect is a no-op."""
    row = _get(conn, key)
    if not row or row["status"] != "committed":
        return False
    if undo:
        undo()
    conn.execute("UPDATE effects SET status='compensated', updated_at=? WHERE idempotency_key=?",
                 (now(), key))
    conn.commit()
    emit(conn, "effect.compensated", key=key, effect_kind=row["kind"])
    return True


def saga(conn, name, steps) -> dict:
    """Run forward steps; on any failure, compensate all prior committed steps in
    reverse order (rollback). steps: [{key, kind, do, undo?, compensation?}, ...]."""
    done = []
    for s in steps:
        try:
            commit(conn, s["key"], s["kind"], s["do"],
                   compensation=s.get("compensation", ""), saga=name)
            done.append(s)
        except Exception:
            for c in reversed(done):
                compensate(conn, c["key"], c.get("undo"))
            emit(conn, "saga.rolled_back", saga=name, completed=len(done), failed_step=s["key"])
            return {"saga": name, "status": "rolled_back",
                    "completed": [d["key"] for d in done], "failed_step": s["key"]}
    emit(conn, "saga.committed", saga=name, steps=len(done))
    return {"saga": name, "status": "committed", "completed": [d["key"] for d in done]}


def _upsert(conn, key, kind, status, result, compensation, saga):
    row = _get(conn, key)
    if row:
        conn.execute("UPDATE effects SET status=?, result=?, updated_at=? WHERE idempotency_key=?",
                     (status, jdumps(result), now(), key))
    else:
        conn.execute("INSERT INTO effects (ts,idempotency_key,kind,status,result,compensation,saga,"
                     "updated_at) VALUES (?,?,?,?,?,?,?,?)",
                     (now(), key, kind, status, jdumps(result), compensation, saga, now()))
    conn.commit()


def guarded(conn, key, kind, runner):
    """Run an executor-style `runner()` (returns a dict with an 'ok' flag) at most
    once per key while it SUCCEEDS. A committed (ok) result is replayed on retry
    without re-running the side effect; a failed result is left re-runnable so
    transient failures can still retry. This is the engine's double-apply guard."""
    row = _get(conn, key)
    if row and row["status"] == "committed":
        emit(conn, "effect.replayed", key=key, effect_kind=kind)
        return jloads(row["result"], {"ok": True, "output": "replayed", "artifacts": []})
    res = runner()
    status = "committed" if res.get("ok") else "failed"
    _upsert(conn, key, kind, status, res, "", "")
    emit(conn, f"effect.{status}", key=key, effect_kind=kind)
    return res


def status(conn, key):
    row = _get(conn, key)
    return row["status"] if row else None


def ledger(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM effects ORDER BY id").fetchall()]
