"""Pytest suite for the AgentOS closed loop. Stdlib + pytest only.

Run: cd agentos && python -m pytest tests/ -q
(Also runnable without pytest via `python -m aos eval`.)
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aos import engine, evals, improve, projectpack  # noqa: E402
from aos.db import init_db  # noqa: E402


def _fresh():
    tmp = Path(tempfile.mkdtemp(prefix="aos_test_"))
    projectpack.PROJECTS_DIR = tmp / "projects"
    projectpack.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return init_db(tmp / "agentos.db")


def test_eval_suite_all_pass():
    results = evals.run_suite()
    failed = [(n, d) for n, p, d in results if not p]
    assert not failed, f"failing eval cases: {failed}"


def test_closed_loop_completes_and_verifies():
    conn = _fresh()
    gid = engine.create_goal(conn, "loop")
    engine.run(conn, gid)
    goal = conn.execute("SELECT status FROM goals WHERE id=?", (gid,)).fetchone()
    assert goal["status"] == "done"
    runs = conn.execute("SELECT COUNT(*) c FROM runs WHERE verified=1").fetchone()["c"]
    assert runs == 3


def test_verifier_is_independent_of_executor():
    conn = _fresh()
    gid = engine.create_goal(conn, "indep", tasks=[
        {"title": "exec ok but wrong content", "kind": "write_file",
         "spec": {"path": "o.md", "content": "x"},
         "verification": {"type": "file_contains", "path": "o.md", "needle": "Z"},
         "max_attempts": 1}])
    engine.run(conn, gid)
    t = conn.execute("SELECT * FROM tasks WHERE goal_id=?", (gid,)).fetchone()
    run = conn.execute("SELECT ok, verified FROM runs WHERE task_id=?", (t["id"],)).fetchone()
    assert run["ok"] == 1 and run["verified"] == 0    # executor ok, verifier rejected
    assert t["status"] == "failed"


def test_retry_then_fail_is_bounded():
    conn = _fresh()
    gid = engine.create_goal(conn, "retry", tasks=[
        {"title": "always fails", "kind": "noop", "spec": {},
         "verification": {"type": "file_exists", "path": "missing.md"},
         "max_attempts": 2}])
    engine.run(conn, gid)
    t = conn.execute("SELECT * FROM tasks WHERE goal_id=?", (gid,)).fetchone()
    assert t["status"] == "failed" and t["attempts"] == 2


def test_safety_policy_denies_destructive_shell():
    conn = _fresh()
    gid = engine.create_goal(conn, "danger", tasks=[
        {"title": "rm rf", "kind": "shell", "spec": {"cmd": "rm -rf /"},
         "max_attempts": 1}])
    engine.run(conn, gid)
    t = conn.execute("SELECT * FROM tasks WHERE goal_id=?", (gid,)).fetchone()
    out = conn.execute("SELECT output FROM runs WHERE task_id=?", (t["id"],)).fetchone()["output"]
    assert "denied by policy" in out and t["status"] == "failed"


def test_dependencies_block_until_ready():
    conn = _fresh()
    gid = engine.create_goal(conn, "deps")
    outcomes = engine.run(conn, gid)
    done = [o["title"] for o in outcomes if o.get("result") == "done"]
    assert done[-1] == "Fan-in verification checkpoint"   # fan-in runs last


def test_procedural_memory_records_recipes():
    conn = _fresh()
    gid = engine.create_goal(conn, "mem")
    engine.run(conn, gid)
    n = conn.execute("SELECT COUNT(*) c FROM memory WHERE mtype='procedural'").fetchone()["c"]
    assert n >= 2


def test_profiles_route_by_kind_then_tag():
    from aos import profiles
    assert profiles.route_profile("write_file", [])["name"] == "executor"
    assert profiles.route_profile("checkpoint", [])["name"] == "verifier"
    assert profiles.route_profile("analysis", ["review"])["name"] == "reviewer"


def test_model_adapter_escalates_on_high_risk():
    from aos import profiles
    from aos.adapters import model
    ex = profiles.route_profile("write_file", [])
    assert model.route(ex, "low")["tier"] == "cheap"
    assert model.route(ex, "high")["tier"] == "strong"


def test_high_risk_task_requires_approval_then_completes():
    conn = _fresh()
    gid = engine.create_goal(conn, "risky", tasks=[
        {"title": "risky", "kind": "write_file", "risk": "high",
         "spec": {"path": "r.md", "content": "rollback"},
         "verification": {"type": "file_contains", "path": "r.md", "needle": "rollback"},
         "max_attempts": 1}])
    out = engine.run(conn, gid)
    assert out[-1]["result"] == "awaiting_approval"
    t = conn.execute("SELECT id FROM tasks WHERE goal_id=?", (gid,)).fetchone()
    conn.execute("UPDATE approvals SET status='approved' WHERE task_id=?", (t["id"],))
    conn.execute("UPDATE tasks SET status='pending' WHERE id=?", (t["id"],))
    conn.commit()
    engine.run(conn, gid)
    assert conn.execute("SELECT status FROM tasks WHERE id=?", (t["id"],)).fetchone()["status"] == "done"


def test_improve_cycle_is_safe_noop_when_stable():
    conn = _fresh()
    out = improve.cycle(conn)
    assert out["action"] in ("noop", "materialize_regression_eval")


if __name__ == "__main__":
    # Stdlib fallback runner so the suite works without pytest installed.
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failures}/{len(fns)} tests passing")
    sys.exit(1 if failures else 0)
