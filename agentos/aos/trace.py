"""Trajectory tracing + a path judge (rule 22).

Outcomes aren't enough: a system that reaches the right answer through a dangerous
path is not yet reliable. Every action already emits an event; this module
assembles a task's events into an ordered trajectory and JUDGES the path — flagging
dangerous trajectories (an orphaned side effect, a success that rode over a denied
action, excessive retries, poison) even when the final status is 'done'.

`judge` is the payoff: it can fail a trajectory the outcome alone would pass.
"""
from __future__ import annotations

from .db import jloads

# event kind → human phase label
PHASE = {
    "task.created": "created", "task.routed": "route", "task.running": "run",
    "effect.committed": "side-effect", "effect.replayed": "side-effect(replay)",
    "effect.failed": "side-effect(failed)", "task.retry": "retry",
    "task.awaiting_approval": "approval-wait", "approval.approved": "approved",
    "approval.denied": "denied", "task.waiting": "wait", "task.resumed": "resume",
    "task.done": "done", "task.failed": "failed", "task.quarantined": "quarantine",
    "task.replayed": "replay",
}


def task_trace(conn, task_id) -> dict:
    rows = conn.execute(
        "SELECT id, ts, kind, data FROM events WHERE task_id=? ORDER BY id", (task_id,)).fetchall()
    spans = [{"seq": i, "ts": r["ts"], "kind": r["kind"],
              "phase": PHASE.get(r["kind"], r["kind"]), "data": jloads(r["data"], {})}
             for i, r in enumerate(rows)]
    # splice in the task's ledgered side effect (key-scoped, so not in task events)
    eff = conn.execute("SELECT kind, status, ts FROM effects WHERE idempotency_key=?",
                       (f"task:{task_id}",)).fetchone()
    if eff:
        spans.append({"seq": len(spans), "ts": eff["ts"], "kind": f"effect.{eff['status']}",
                      "phase": f"side-effect({eff['status']})", "data": {"effect_kind": eff["kind"]}})
        spans.sort(key=lambda s: s["ts"])
    clean, findings = judge(conn, task_id)
    return {"task_id": task_id, "spans": spans, "clean": clean, "findings": findings}


def goal_trace(conn, goal_id) -> list[dict]:
    tids = [r["id"] for r in conn.execute(
        "SELECT id FROM tasks WHERE goal_id=? ORDER BY priority, created_at", (goal_id,)).fetchall()]
    return [task_trace(conn, tid) for tid in tids]


def judge(conn, task_id) -> tuple[bool, list[str]]:
    """Evaluate the PATH, not just the outcome. Returns (clean, findings)."""
    kinds = [r["kind"] for r in conn.execute(
        "SELECT kind FROM events WHERE task_id=? ORDER BY id", (task_id,)).fetchall()]
    findings = []

    # orphaned side effect: an effect committed on a task that then failed. The
    # effect ledger (keyed by task:<id>) is the source of truth — effect events
    # are key-scoped, not task-scoped, so check the table directly.
    eff = conn.execute("SELECT status FROM effects WHERE idempotency_key=?",
                       (f"task:{task_id}",)).fetchone()
    if eff and eff["status"] == "committed" and "task.failed" in kinds:
        findings.append("orphaned side effect: an effect committed but the task failed "
                        "(needs compensation)")

    # dangerous success: task finished done, but a run was denied by policy along the way.
    if "task.done" in kinds:
        denied = conn.execute(
            "SELECT COUNT(*) c FROM runs WHERE task_id=? AND output LIKE '%denied by policy%'",
            (task_id,)).fetchone()["c"]
        if denied:
            findings.append("succeeded despite a policy-denied action on the path")

    retries = kinds.count("task.retry")
    if retries >= 2:
        findings.append(f"excessive retries on the path ({retries})")

    if kinds.count("task.replayed") >= 3:
        findings.append("poison: replayed 3+ times")

    return len(findings) == 0, findings
