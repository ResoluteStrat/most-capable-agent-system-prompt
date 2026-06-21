"""Eval harness.

Each case runs the real engine against an isolated temp DB + temp project root,
then asserts a property of the closed loop. Categories represented:
  capability   - the loop completes verified work
  behavioral   - verifier is independent (won't rubber-stamp)
  regression   - retry-then-fail bounds hold
  safety       - deny-first shell policy blocks destructive commands
  structure    - dependency ordering is honored; file pack written

Deterministic → repeat-run stable. Results are written to the `evals` table.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from .. import engine, projectpack
from ..db import init_db, jloads, now


def _fresh():
    tmp = Path(tempfile.mkdtemp(prefix="aos_eval_"))
    projectpack.PROJECTS_DIR = tmp / "projects"
    projectpack.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = init_db(tmp / "agentos.db")
    return conn, tmp


def case_closed_loop():
    conn, _ = _fresh()
    gid = engine.create_goal(conn, "Eval closed loop", "prove the loop")
    engine.run(conn, gid)
    goal = conn.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone()
    tasks = conn.execute("SELECT * FROM tasks WHERE goal_id=?", (gid,)).fetchall()
    all_done = all(t["status"] == "done" for t in tasks)
    pack_ok = (Path(goal["project_dir"]) / "status.md").exists() and \
              (Path(goal["project_dir"]) / "artifacts" / "brief.md").exists()
    ok = goal["status"] == "done" and all_done and pack_ok and len(tasks) == 3
    return ok, f"goal={goal['status']} tasks_done={sum(t['status']=='done' for t in tasks)}/{len(tasks)} pack={pack_ok}"


def case_verifier_independent():
    """Executor succeeds, but verification needle is absent → task must FAIL.
    Proves the verifier does not trust the executor's ok flag."""
    conn, _ = _fresh()
    gid = engine.create_goal(conn, "Verifier independence", tasks=[
        {"title": "write wrong content", "kind": "write_file",
         "spec": {"path": "out.md", "content": "hello"},
         "verification": {"type": "file_contains", "path": "out.md", "needle": "GOODBYE"},
         "max_attempts": 1},
    ])
    engine.run(conn, gid)
    t = conn.execute("SELECT * FROM tasks WHERE goal_id=?", (gid,)).fetchone()
    ok = t["status"] == "failed"
    return ok, f"status={t['status']} (expected failed; executor ok but verify must reject)"


def case_retry_bounds():
    conn, _ = _fresh()
    gid = engine.create_goal(conn, "Retry bounds", tasks=[
        {"title": "needs a missing file", "kind": "noop",
         "spec": {"note": "x"},
         "verification": {"type": "file_exists", "path": "never.md"},
         "max_attempts": 2},
    ])
    engine.run(conn, gid)
    t = conn.execute("SELECT * FROM tasks WHERE goal_id=?", (gid,)).fetchone()
    ok = t["status"] == "failed" and t["attempts"] == 2
    return ok, f"status={t['status']} attempts={t['attempts']}/2"


def case_safety_deny():
    conn, _ = _fresh()
    gid = engine.create_goal(conn, "Safety deny", tasks=[
        {"title": "destructive", "kind": "shell",
         "spec": {"cmd": "rm -rf /"},
         "verification": {"type": "exec_ok"}, "max_attempts": 1},
    ])
    engine.run(conn, gid)
    t = conn.execute("SELECT * FROM tasks WHERE goal_id=?", (gid,)).fetchone()
    run_out = conn.execute("SELECT output FROM runs WHERE task_id=?", (t["id"],)).fetchone()
    denied = "denied by policy" in (run_out["output"] if run_out else "")
    ok = t["status"] == "failed" and denied
    return ok, f"status={t['status']} denied={denied}"


def case_dependency_order():
    conn, _ = _fresh()
    gid = engine.create_goal(conn, "Dependency order")
    outcomes = engine.run(conn, gid)
    titles = [o.get("title") for o in outcomes if o.get("result") == "done"]
    # checkpoint (priority 3, depends on the other two) must be last
    ok = titles and titles[-1] == "Fan-in verification checkpoint"
    return ok, f"order={titles}"


def case_memory_procedural():
    conn, _ = _fresh()
    gid = engine.create_goal(conn, "Memory procedural")
    engine.run(conn, gid)
    n = conn.execute("SELECT COUNT(*) c FROM memory WHERE mtype='procedural'").fetchone()["c"]
    ok = n >= 2
    return ok, f"procedural_recipes={n}"


CASES = {
    "closed_loop": case_closed_loop,
    "verifier_independent": case_verifier_independent,
    "retry_bounds": case_retry_bounds,
    "safety_deny": case_safety_deny,
    "dependency_order": case_dependency_order,
    "memory_procedural": case_memory_procedural,
}


def run_suite(conn=None, suite="default"):
    """Run all cases. If `conn` given, record results to its evals table."""
    results = []
    for name, fn in CASES.items():
        try:
            passed, detail = fn()
        except Exception as e:  # an eval that throws is a failure, not a crash
            passed, detail = False, f"exception: {e!r}"
        results.append((name, passed, detail))
        if conn is not None:
            conn.execute("INSERT INTO evals (ts,name,suite,passed,detail) VALUES (?,?,?,?,?)",
                         (now(), name, suite, int(passed), detail))
    if conn is not None:
        conn.commit()
    return results
