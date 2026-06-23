"""Altitude control — one state, many zoom levels.

The same control-plane state powers a single task, a project (goal), and the whole
portfolio. These pure functions return structured rollups so the CLI (and a future
web UI) can render any altitude and drill between them without switching tools.
"""
from __future__ import annotations

from . import trace
from .db import jloads


def task_rollup(conn, task_id) -> dict | None:
    t = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not t:
        return None
    runs = conn.execute("SELECT started, ok, verified, cost_ticks FROM runs WHERE task_id=? ORDER BY id",
                        (task_id,)).fetchall()
    return {"level": "task", "id": task_id, "title": t["title"], "kind": t["kind"],
            "status": t["status"], "risk": t["risk"], "attempts": t["attempts"],
            "skill_tags": jloads(t["skill_tags"], []),
            "artifacts": jloads(t["artifacts"], []),
            "runs": [{"started": r["started"], "ok": r["ok"], "verified": r["verified"],
                      "cost": r["cost_ticks"]} for r in runs],
            "escalation": t["escalation"]}


def project_rollup(conn, goal_id) -> dict | None:
    g = conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
    if not g:
        return None
    tasks = conn.execute("SELECT status, COUNT(*) c FROM tasks WHERE goal_id=? GROUP BY status",
                         (goal_id,)).fetchall()
    by_status = {r["status"]: r["c"] for r in tasks}
    harnesses = conn.execute("SELECT harness, status, phase FROM harness_runs WHERE goal_id=?",
                            (goal_id,)).fetchall()
    cost = conn.execute("SELECT COALESCE(SUM(r.cost_ticks),0) c FROM runs r "
                        "JOIN tasks t ON r.task_id=t.id WHERE t.goal_id=?", (goal_id,)).fetchone()["c"]
    total = sum(by_status.values())
    # trajectory judge per task — surfaces dangerous PATHS even on done tasks (rule 22)
    dangerous = []
    for r in conn.execute("SELECT id FROM tasks WHERE goal_id=?", (goal_id,)).fetchall():
        clean, findings = trace.judge(conn, r["id"])
        if not clean:
            dangerous.append({"task_id": r["id"], "findings": findings})
    return {"level": "project", "id": goal_id, "title": g["title"], "status": g["status"],
            "project_dir": g["project_dir"], "tasks_total": total,
            "tasks_done": by_status.get("done", 0), "by_status": by_status,
            "blocked": by_status.get("blocked", 0), "failed": by_status.get("failed", 0),
            "cost_ticks": cost, "dangerous_paths": dangerous,
            "harnesses": [{"harness": h["harness"], "status": h["status"], "phase": h["phase"]}
                          for h in harnesses]}


def portfolio_rollup(conn) -> dict:
    goals = conn.execute("SELECT * FROM goals ORDER BY created_at DESC").fetchall()
    projects = [project_rollup(conn, g["id"]) for g in goals]
    agg = {"goals": len(goals),
           "active": sum(p["status"] == "active" for p in projects),
           "done": sum(p["status"] == "done" for p in projects),
           "failed": sum(p["status"] == "failed" for p in projects),
           "blocked_tasks": sum(p["blocked"] for p in projects),
           "failed_tasks": sum(p["failed"] for p in projects),
           "dangerous_paths": sum(len(p["dangerous_paths"]) for p in projects),
           "cost_ticks": sum(p["cost_ticks"] for p in projects)}
    approvals = conn.execute("SELECT COUNT(*) c FROM approvals WHERE status='pending'").fetchone()["c"]
    # attention = where a human is needed or work is stuck (the inbox signal)
    attention = []
    for p in projects:
        if p["failed"]:
            attention.append(f"{p['id']} ({p['title']}): {p['failed']} failed task(s)")
        if p["blocked"]:
            attention.append(f"{p['id']} ({p['title']}): {p['blocked']} blocked task(s)")
        if p["dangerous_paths"]:
            attention.append(f"{p['id']} ({p['title']}): {len(p['dangerous_paths'])} "
                             f"dangerous trajectory(ies) — check `aos trace`")
    return {"level": "portfolio", **agg, "pending_approvals": approvals,
            "attention": attention,
            "projects": [{"id": p["id"], "title": p["title"], "status": p["status"],
                          "done": p["tasks_done"], "total": p["tasks_total"]} for p in projects]}
