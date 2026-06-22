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


def test_coding_harness_runs_all_phases():
    from aos.harness import coding_delivery
    conn = _fresh()
    import tempfile
    ws = Path(tempfile.mkdtemp()) / "ws"
    gid = engine.create_goal(conn, "h", tasks=[])
    out = coding_delivery.build().run(conn, gid, {
        "workspace": str(ws),
        "spec": {"plan": "p", "files": {"a.py": "x=1\n"}, "test_cmd": "true"}})
    assert out["status"] == "done"
    assert (ws / "DELIVERABLE.md").exists()


def test_coding_harness_resumes_from_failed_phase():
    from aos.harness import coding_delivery
    import tempfile
    conn = _fresh()
    ws = Path(tempfile.mkdtemp()) / "ws"
    gid = engine.create_goal(conn, "h", tasks=[])
    h = coding_delivery.build()
    spec = {"plan": "p", "files": {"a.py": "x=1\n"}, "test_cmd": "false"}
    r1 = h.run(conn, gid, {"workspace": str(ws), "spec": spec})
    assert r1["status"] == "failed" and r1["phase"] == "test"
    spec["test_cmd"] = "true"        # the fix
    r2 = h.run(conn, gid, {"workspace": str(ws), "spec": spec})
    assert r2["status"] == "done"
    assert r2["phases"]["plan"] == "done" and r2["phases"]["change"] == "done"


def test_web_snapshot_and_event_stream():
    from aos import web
    conn = _fresh()
    g = engine.create_goal(conn, "w"); engine.run(conn, g)
    snap = web.snapshot(conn)
    assert snap["portfolio"]["goals"] == 1 and snap["metrics"]["tasks_completed"] == 3
    evs = web.events_since(conn, 0)
    assert len(evs) > 0 and all(evs[i]["id"] < evs[i + 1]["id"] for i in range(len(evs) - 1))
    assert web.events_since(conn, evs[-1]["id"]) == []   # since-filter excludes seen


def test_intel_ranks_and_promotes():
    from aos import intel
    conn = _fresh()
    items = [
        {"source": "Temporal", "url": "u1", "category": "durable-execution",
         "claim": "durable execution with checkpoint, retries, typed contracts, workflow versioning"},
        {"source": "ShinyBot", "url": "u2", "category": "product",
         "claim": "thin wrapper around a provider API, chatbot ui-only demo riding the trend"},
    ]
    summary = intel.ingest(conn, items)
    assert intel.score(items[0]) > intel.score(items[1])
    assert intel.score(items[1]) == 0           # noise penalized to zero
    assert summary["promoted_experiments"] == 1
    d = intel.digest(conn)
    assert d["ranked"][0]["source"] == "Temporal" and d["counts"]["ignore"] == 1


def test_recurring_sweep_proposes_and_improves():
    from aos import sweep
    conn = _fresh()
    engine.run(conn, engine.create_goal(conn, "good"))
    engine.run(conn, engine.create_goal(conn, "bad", tasks=[
        {"title": "f", "kind": "noop", "spec": {},
         "verification": {"type": "file_exists", "path": "no.md"}, "max_attempts": 1}]))
    d = sweep.run(conn)
    assert any("bad" in p for p in d["proposals"])
    assert d["improve"] in ("noop", "materialize_regression_eval")


def test_rollup_aggregates_altitudes():
    from aos import rollup
    conn = _fresh()
    g = engine.create_goal(conn, "x"); engine.run(conn, g)
    port = rollup.portfolio_rollup(conn)
    proj = rollup.project_rollup(conn, g)
    assert port["goals"] == 1 and port["done"] == 1
    assert proj["tasks_done"] == 3 and proj["status"] == "done"
    tid = conn.execute("SELECT id FROM tasks WHERE goal_id=? LIMIT 1", (g,)).fetchone()["id"]
    assert rollup.task_rollup(conn, tid)["status"] == "done"


def test_ask_router_infers_modes():
    from aos import ask
    assert ask.classify("What is blocked?")["mode"] == "answer"
    assert ask.classify("Fix the failing login bug")["mode"] == "execute"
    assert ask.classify("Write a weekly KPI report")["mode"] == "harness:report"
    assert ask.classify("Log in to the website and navigate to billing")["mode"] == "harness:browser"
    # word-boundary: 'list' inside 'checklist' must not trigger the answer mode
    assert ask.classify("create an onboarding checklist")["mode"] == "execute"


def test_eval_suite_is_repeat_run_stable():
    stable, counts = evals.stability(3)
    assert stable, f"non-deterministic eval suite across runs: {counts}"


def test_tune_loop_reverts_a_regression():
    from aos import config
    conn = _fresh()
    config.reset(None)                       # start from defaults
    out = improve.tune_config(conn)
    # candidate gate=0.0 breaks the trust-gate eval → strictly worse → revert
    assert out["kept"] is False
    assert out["after"] < out["baseline"]
    assert config.get("medium_trust_gate") == 0.5    # restored
    config.reset(None)


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
