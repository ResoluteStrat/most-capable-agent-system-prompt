"""Durable waitpoints (reliability rules 18-19).

A run can pause and resume from its exact state because the waitpoint lives on
disk (SQLite), not in process memory. Three kinds:
  timer   — resume once now >= wake_at (scheduled work, rate-limit backoff).
  signal  — resume once a named signal is delivered (webhook/human/event).
  approval— resume once the approval row is approved (reuses the approvals table).

The engine pauses a `wait` task by creating a waitpoint and blocking the task;
`ready` flips it back to runnable when the condition is met — so a fresh process
that opens the same DB resumes correctly.
"""
from __future__ import annotations

from .db import emit, now


def create(conn, task_id, goal_id, kind, *, wake_at="", signal="", reason=""):
    cur = conn.execute(
        "INSERT INTO waitpoints (ts,task_id,goal_id,kind,status,wake_at,signal,reason,updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (now(), task_id, goal_id, kind, "pending", wake_at, signal, reason, now()))
    conn.commit()
    emit(conn, "waitpoint.created", goal_id=goal_id, task_id=task_id,
         wp_kind=kind, wake_at=wake_at, signal=signal)
    return cur.lastrowid


def for_task(conn, task_id):
    return conn.execute(
        "SELECT * FROM waitpoints WHERE task_id=? AND status='pending' ORDER BY id DESC LIMIT 1",
        (task_id,)).fetchone()


def ready(conn, wp) -> bool:
    if wp["kind"] == "timer":
        return bool(wp["wake_at"]) and wp["wake_at"] <= now()
    if wp["kind"] == "signal":
        return wp["delivered"] == 1
    if wp["kind"] == "approval":
        row = conn.execute(
            "SELECT status FROM approvals WHERE task_id=? ORDER BY id DESC LIMIT 1",
            (wp["task_id"],)).fetchone()
        return bool(row) and row["status"] == "approved"
    return False


def resolve(conn, wp_id):
    conn.execute("UPDATE waitpoints SET status='resolved', updated_at=? WHERE id=?", (now(), wp_id))
    conn.commit()


def deliver_signal(conn, name) -> int:
    cur = conn.execute(
        "UPDATE waitpoints SET delivered=1, updated_at=? WHERE kind='signal' AND signal=? "
        "AND status='pending'", (now(), name))
    conn.commit()
    emit(conn, "signal.delivered", signal=name, matched=cur.rowcount)
    return cur.rowcount


def pending(conn):
    return conn.execute("SELECT * FROM waitpoints WHERE status='pending' ORDER BY id").fetchall()
