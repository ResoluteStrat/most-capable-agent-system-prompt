"""Quarantine / dead-letter queue (rule 21).

Repeatedly failing tasks must not thrash in silent retry storms — that destroys
reliability and operator trust. When a task fails terminally it is captured here
with an EVIDENCE BUNDLE (reason, attempt count, last run output, verifier
evidence). Getting it back into the system is EXPLICIT: an operator runs
`aos replay <task_id>`, which resets the task and records the replay. A task that
is re-quarantined after several replays is flagged `poison` so it is not
mindlessly retried again.
"""
from __future__ import annotations

from .db import emit, jdumps, jloads, now

POISON_REPLAYS = 3


def record(conn, task_row, reason, evidence) -> int:
    """Capture a terminally-failed task. If it was previously replayed and failed
    again, increment the replay counter on the existing entry (poison tracking)."""
    tid = task_row["id"]
    last_output = conn.execute(
        "SELECT output FROM runs WHERE task_id=? ORDER BY id DESC LIMIT 1", (tid,)).fetchone()
    bundle = {"reason": reason, "attempts": task_row["attempts"],
              "verifier_evidence": evidence or {},
              "last_output": (last_output["output"] if last_output else "")[:2000]}
    prior = conn.execute(
        "SELECT id, replays FROM quarantine WHERE task_id=? ORDER BY id DESC LIMIT 1", (tid,)).fetchone()
    if prior and prior["replays"] > 0:
        conn.execute("UPDATE quarantine SET status='quarantined', reason=?, evidence=?, "
                     "attempts=?, updated_at=? WHERE id=?",
                     (reason, jdumps(bundle), task_row["attempts"], now(), prior["id"]))
        conn.commit()
        qid = prior["id"]
    else:
        qid = conn.execute(
            "INSERT INTO quarantine (ts,task_id,goal_id,reason,attempts,evidence,updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (now(), tid, task_row["goal_id"], reason, task_row["attempts"], jdumps(bundle), now())
        ).lastrowid
        conn.commit()
    poison = is_poison(conn, tid)
    emit(conn, "task.quarantined", goal_id=task_row["goal_id"], task_id=tid,
         reason=reason, poison=poison)
    return qid


def is_poison(conn, task_id) -> bool:
    row = conn.execute(
        "SELECT replays FROM quarantine WHERE task_id=? ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
    return bool(row) and row["replays"] >= POISON_REPLAYS


def listq(conn, include_replayed=False):
    q = "SELECT * FROM quarantine"
    if not include_replayed:
        q += " WHERE status='quarantined'"
    return conn.execute(q + " ORDER BY id DESC").fetchall()


def replay(conn, task_id) -> dict:
    """Explicit operator replay: reset the task to pending and record it. Refuses
    a poison task (too many replays) unless forced."""
    entry = conn.execute(
        "SELECT * FROM quarantine WHERE task_id=? AND status='quarantined' ORDER BY id DESC LIMIT 1",
        (task_id,)).fetchone()
    if not entry:
        return {"ok": False, "reason": "no quarantined entry for that task"}
    if entry["replays"] >= POISON_REPLAYS:
        return {"ok": False, "reason": f"poison: already replayed {entry['replays']}x — fix the root cause"}
    conn.execute("UPDATE tasks SET status='pending', attempts=0, escalation='', updated_at=? WHERE id=?",
                 (now(), task_id))
    conn.execute("UPDATE quarantine SET status='replayed', replays=replays+1, updated_at=? WHERE id=?",
                 (now(), entry["id"]))
    conn.commit()
    emit(conn, "task.replayed", goal_id=entry["goal_id"], task_id=task_id,
         replays=entry["replays"] + 1)
    return {"ok": True, "task_id": task_id, "replays": entry["replays"] + 1}
