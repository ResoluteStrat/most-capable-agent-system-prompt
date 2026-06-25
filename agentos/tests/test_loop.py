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


def test_two_workers_no_double_execution():
    import tempfile
    import threading
    from aos import worker
    from aos.db import connect, init_db
    db = str(Path(tempfile.mkdtemp()) / "agentos.db")
    init_db(db)
    c0 = connect(db)
    tasks = [{"title": f"t{i}", "kind": "noop", "spec": {},
              "verification": {"type": "always"}, "max_attempts": 1} for i in range(10)]
    gid = engine.create_goal(c0, "par", tasks=tasks); c0.close()

    def w(wid):
        c = connect(db); worker.run_until_idle(c, wid, gid); c.close()
    ts = [threading.Thread(target=w, args=(f"w{i}",)) for i in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]

    c = connect(db)
    done = c.execute("SELECT COUNT(*) c FROM tasks WHERE goal_id=? AND status='done'", (gid,)).fetchone()["c"]
    runs = c.execute("SELECT COUNT(*) c FROM runs r JOIN tasks t ON r.task_id=t.id WHERE t.goal_id=?",
                     (gid,)).fetchone()["c"]
    c.close()
    assert done == 10 and runs == 10        # exactly one run per task; no double execution


def test_skill_frontmatter_handles_block_scalar():
    from aos import skills
    name, desc, body = skills._parse_frontmatter(
        "---\nname: x\ndescription: |-\n  line one\n  line two\n---\n# Body\n")
    assert name == "x" and desc == "line one line two" and body.startswith("# Body")
    # plain scalar still works
    n2, d2, _ = skills._parse_frontmatter("---\nname: y\ndescription: hi there\n---\nbody")
    assert n2 == "y" and d2 == "hi there"


def test_skill_run_is_side_effecting_and_compensates():
    from aos import effects, skills, trace
    conn = _fresh()
    skills.register_all(conn, [str(Path(__file__).resolve().parents[1] / "examples" / "sample_skill")])
    sk = skills.resolve(conn, "hello-skill")
    g = engine.create_goal(conn, "se", tasks=[
        {"title": "run then fail", "kind": "skill",
         "spec": {"skill_path": sk["path"], "action": "run", "script": "greet.py", "args": ["x"],
                  "on_fail_compensate": {"kind": "noop"}},
         "verification": {"type": "file_contains", "path": "skill_sample_skill_output.txt",
                          "needle": "NOPE"}, "max_attempts": 1}])
    engine.run(conn, g)
    t = conn.execute("SELECT id FROM tasks WHERE goal_id=?", (g,)).fetchone()
    assert effects.status(conn, f"task:{t['id']}") == "compensated"
    assert trace.task_trace(conn, t["id"])["clean"] is True


def test_rollup_surfaces_dangerous_trajectory():
    from aos import rollup
    conn = _fresh()
    g = engine.create_goal(conn, "risky", tasks=[
        {"title": "commit then fail", "kind": "python", "spec": {"code": "open('x.txt','w').write('x')"},
         "verification": {"type": "file_contains", "path": "x.txt", "needle": "NEVER"}, "max_attempts": 1}])
    engine.run(conn, g)
    assert len(rollup.project_rollup(conn, g)["dangerous_paths"]) == 1
    assert rollup.portfolio_rollup(conn)["dangerous_paths"] == 1


def test_skill_scaffold_register_and_run():
    import tempfile
    from aos import skills
    conn = _fresh()
    sk = skills.scaffold("My New Skill", "does a thing", base_dir=tempfile.mkdtemp())
    skills.register(conn, sk)
    assert sk.name == "my-new-skill" and "my-new-skill.py" in sk.scripts
    assert skills.resolve(conn, "my-new-skill") is not None
    g = engine.create_goal(conn, "use", tasks=[
        {"title": "run", "kind": "skill",
         "spec": {"skill_path": sk.path, "action": "run", "script": "my-new-skill.py"},
         "verification": {"type": "file_contains", "path": "skill_my-new-skill_output.txt",
                          "needle": "my-new-skill ran"}, "max_attempts": 1}])
    engine.run(conn, g)
    assert conn.execute("SELECT status FROM goals WHERE id=?", (g,)).fetchone()["status"] == "done"


def test_skill_routing_and_match():
    from aos import profiles, skills
    conn = _fresh()
    assert profiles.route_profile("skill", [])["name"] == "skill-runner"
    skills.register_all(conn, [str(Path(__file__).resolve().parents[1] / "examples" / "sample_skill")])
    assert skills.match(conn, "use the hello skill")["name"] == "hello-skill"
    assert skills.match(conn, "reconcile the general ledger") is None


def test_claude_code_skill_discovered_and_run():
    from aos import skills
    conn = _fresh()
    pkg = Path(__file__).resolve().parents[1] / "examples" / "sample_skill"
    found = skills.register_all(conn, [str(pkg)])
    assert len(found) == 1 and skills.resolve(conn, "hello-skill")["scripts"] == ["greet.py"]
    sk = skills.resolve(conn, "hello-skill")
    g = engine.create_goal(conn, "use", tasks=[
        {"title": "run", "kind": "skill",
         "spec": {"skill_path": sk["path"], "action": "run", "script": "greet.py", "args": ["x"]},
         "verification": {"type": "file_contains", "path": "skill_sample_skill_output.txt",
                          "needle": "hello, x"}, "max_attempts": 1}])
    engine.run(conn, g)
    assert conn.execute("SELECT status FROM goals WHERE id=?", (g,)).fetchone()["status"] == "done"


def test_failed_task_auto_compensates_declared_side_effect():
    from aos import effects, trace
    conn = _fresh()
    g = engine.create_goal(conn, "comp", tasks=[
        {"title": "commit then fail", "kind": "python",
         "spec": {"code": "open('did.txt','w').write('x')",
                  "on_fail_compensate": {"kind": "python", "code": "import os; os.remove('did.txt')"}},
         "verification": {"type": "file_contains", "path": "did.txt", "needle": "NEVER"},
         "max_attempts": 1}])
    engine.run(conn, g)
    t = conn.execute("SELECT * FROM tasks WHERE goal_id=?", (g,)).fetchone()
    assert effects.status(conn, f"task:{t['id']}") == "compensated"
    assert trace.task_trace(conn, t["id"])["clean"] is True


def test_trace_judge_flags_dangerous_path():
    from aos import trace
    conn = _fresh()
    g1 = engine.create_goal(conn, "clean"); engine.run(conn, g1)
    t1 = conn.execute("SELECT id FROM tasks WHERE goal_id=? LIMIT 1", (g1,)).fetchone()["id"]
    assert trace.task_trace(conn, t1)["clean"] is True
    g2 = engine.create_goal(conn, "orphan", tasks=[
        {"title": "commit then fail", "kind": "python", "spec": {"code": "open('d.txt','a').write('x')"},
         "verification": {"type": "file_contains", "path": "d.txt", "needle": "NEVER"}, "max_attempts": 1}])
    engine.run(conn, g2)
    t2 = conn.execute("SELECT id FROM tasks WHERE goal_id=? LIMIT 1", (g2,)).fetchone()["id"]
    tr = trace.task_trace(conn, t2)
    assert tr["clean"] is False and any("orphaned side effect" in f for f in tr["findings"])


def test_quarantine_captures_and_replay_recovers():
    from aos import quarantine
    conn = _fresh()
    g = engine.create_goal(conn, "q", tasks=[
        {"title": "needs file", "kind": "noop", "spec": {},
         "verification": {"type": "file_exists", "path": "fix.md"}, "max_attempts": 1}])
    engine.run(conn, g)
    t = conn.execute("SELECT * FROM tasks WHERE goal_id=?", (g,)).fetchone()
    assert t["status"] == "failed" and len(quarantine.listq(conn)) == 1
    pdir = conn.execute("SELECT project_dir FROM goals WHERE id=?", (g,)).fetchone()["project_dir"]
    (Path(pdir) / "fix.md").write_text("ok")
    assert quarantine.replay(conn, t["id"])["ok"]
    engine.run(conn, g)
    assert conn.execute("SELECT status FROM tasks WHERE id=?", (t["id"],)).fetchone()["status"] == "done"
    assert quarantine.listq(conn) == []          # cleared after recovery


def test_timer_waitpoint_blocks_then_resumes():
    conn = _fresh()
    g = engine.create_goal(conn, "t", tasks=[
        {"title": "w", "kind": "wait", "spec": {"wait": "timer", "until": "2999-01-01T00:00:00Z"},
         "verification": {"type": "always"}}])
    engine.run(conn, g)
    assert conn.execute("SELECT status FROM tasks WHERE goal_id=?", (g,)).fetchone()["status"] == "blocked"


def test_signal_waitpoint_resumes_on_fresh_connection():
    import tempfile
    from aos.db import connect, init_db
    db = str(Path(tempfile.mkdtemp()) / "agentos.db")
    c = init_db(db)
    g = engine.create_goal(c, "s", tasks=[
        {"title": "w", "kind": "wait", "spec": {"wait": "signal", "signal": "go"},
         "verification": {"type": "always"}}])
    engine.run(c, g)
    assert c.execute("SELECT status FROM tasks WHERE goal_id=?", (g,)).fetchone()["status"] == "blocked"
    from aos import waitpoints
    waitpoints.deliver_signal(c, "go"); c.close()
    c2 = connect(db)                              # fresh process
    engine.run(c2, g)
    assert c2.execute("SELECT status FROM tasks WHERE goal_id=?", (g,)).fetchone()["status"] == "done"


def test_engine_retry_does_not_double_apply_side_effect():
    conn = _fresh()
    gid = engine.create_goal(conn, "once", tasks=[
        {"title": "append", "kind": "python", "spec": {"code": "open('c.txt','a').write('x\\n')"},
         "verification": {"type": "file_contains", "path": "c.txt", "needle": "NEVER"},
         "max_attempts": 2}])
    engine.run(conn, gid)
    t = conn.execute("SELECT attempts FROM tasks WHERE goal_id=?", (gid,)).fetchone()
    cf = Path(conn.execute("SELECT project_dir FROM goals WHERE id=?", (gid,)).fetchone()["project_dir"]) / "c.txt"
    assert t["attempts"] == 2 and len(cf.read_text().splitlines()) == 1   # 2 tries, 1 application


def test_effect_idempotency_runs_action_once():
    from aos import effects
    conn = _fresh()
    calls = {"n": 0}
    do = lambda: (calls.__setitem__("n", calls["n"] + 1) or {"id": "T1"})
    r1 = effects.commit(conn, "k", "email", do)
    r2 = effects.commit(conn, "k", "email", do)
    assert calls["n"] == 1 and r1 == r2 == {"id": "T1"}


def test_saga_compensates_on_partial_failure():
    from aos import effects
    conn = _fresh()
    st = {"crm": False}
    out = effects.saga(conn, "s", [
        {"key": "a", "kind": "crm", "do": lambda: st.__setitem__("crm", True) or {"ok": 1},
         "undo": lambda: st.__setitem__("crm", False)},
        {"key": "b", "kind": "deploy", "do": lambda: (_ for _ in ()).throw(RuntimeError("x"))},
    ])
    assert out["status"] == "rolled_back" and st["crm"] is False
    statuses = {r["idempotency_key"]: r["status"] for r in effects.ledger(conn)}
    assert statuses["a"] == "compensated" and statuses["b"] == "failed"


def test_web_goal_drilldown_returns_tasks():
    from aos import rollup
    conn = _fresh()
    g = engine.create_goal(conn, "drill"); engine.run(conn, g)
    proj = rollup.project_rollup(conn, g)
    assert len(proj["tasks"]) == 3
    assert all({"id", "title", "kind", "status"} <= set(t) for t in proj["tasks"])


def test_web_snapshot_and_event_stream():
    from aos import web
    conn = _fresh()
    g = engine.create_goal(conn, "w"); engine.run(conn, g)
    snap = web.snapshot(conn)
    assert snap["portfolio"]["goals"] == 1 and snap["metrics"]["tasks_completed"] == 3
    evs = web.events_since(conn, 0)
    assert len(evs) > 0 and all(evs[i]["id"] < evs[i + 1]["id"] for i in range(len(evs) - 1))
    assert web.events_since(conn, evs[-1]["id"]) == []   # since-filter excludes seen


def test_fetcher_parses_feed_and_degrades_gracefully():
    from aos import fetchers
    rss = ("<rss version='2.0'><channel>"
           "<item><title>durable checkpoint workflow</title>"
           "<link>https://x/a</link><description>typed contracts and eval loops</description></item>"
           "</channel></rss>")
    items = fetchers.parse_feed(rss)
    assert len(items) == 1 and items[0]["url"] == "https://x/a" and "durable" in items[0]["claim"]
    # JSON feeds also parse
    assert len(fetchers.parse_any('[{"claim":"x","url":"u"}]')) == 1
    # malformed input degrades to [] instead of crashing
    assert fetchers.parse_feed("not xml at all") == []
    # an unreachable URL returns [] (network-optional), no exception
    assert fetchers.HttpFetcher("http://127.0.0.1:9/none", timeout=1).fetch() == []


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


def test_improve_reentrancy_guard_prevents_nested_suite_runs():
    import aos.improve as imp
    conn = _fresh()
    assert imp._in_scoring is False
    imp._in_scoring = True                       # simulate "inside eval scoring"
    try:
        assert imp.cycle(conn)["action"] == "noop"          # nested → no-op
        assert imp.tune_config(conn)["action"] == "noop"    # nested → no-op
    finally:
        imp._in_scoring = False
    imp._score(conn)                             # a real scoring run resets the flag
    assert imp._in_scoring is False


def test_cost_expensive_goals_flags_high_per_run():
    from aos import cost, engine
    conn = _fresh()
    engine.run(conn, engine.create_goal(conn, "cheap"))     # per-run 1
    g = engine.create_goal(conn, "exp", tasks=[
        {"title": "risky", "kind": "write_file", "risk": "high",
         "spec": {"path": "r.md", "content": "deploy"},
         "verification": {"type": "file_contains", "path": "r.md", "needle": "deploy"},
         "max_attempts": 1}])
    engine.run(conn, g)
    t = conn.execute("SELECT id FROM tasks WHERE goal_id=?", (g,)).fetchone()["id"]
    conn.execute("UPDATE approvals SET status='approved' WHERE task_id=?", (t,))
    conn.execute("UPDATE tasks SET status='pending' WHERE id=?", (t,)); conn.commit()
    engine.run(conn, g)
    exp = cost.expensive_goals(conn)
    assert len(exp) == 1 and exp[0]["id"] == g and exp[0]["per_run"] == 3.0


def test_cost_breakdown_by_tier():
    from aos import cost, engine
    conn = _fresh()
    engine.run(conn, engine.create_goal(conn, "cheap"))     # cheap runs
    g = engine.create_goal(conn, "exp", tasks=[
        {"title": "risky", "kind": "write_file", "risk": "high",
         "spec": {"path": "r.md", "content": "deploy"},
         "verification": {"type": "file_contains", "path": "r.md", "needle": "deploy"},
         "max_attempts": 1}])
    engine.run(conn, g)
    t = conn.execute("SELECT id FROM tasks WHERE goal_id=?", (g,)).fetchone()["id"]
    conn.execute("UPDATE approvals SET status='approved' WHERE task_id=?", (t,))
    conn.execute("UPDATE tasks SET status='pending' WHERE id=?", (t,)); conn.commit()
    engine.run(conn, g)
    tiers = cost.by_tier(conn)
    assert tiers.get("cheap", 0) >= 3 and tiers.get("strong", 0) == 3
    assert "cost_by_tier" in engine.metrics(conn)


def test_auto_promotion_is_gated_then_fires():
    import tempfile
    from aos import mine
    conn = _fresh()
    for _ in range(6):
        engine.run(conn, engine.create_goal(conn, "r"))
    mine.mine(conn, threshold=3)
    tmp = tempfile.mkdtemp()
    assert mine.auto_promote(conn, min_sweeps=99, conf_gate=0.75, base_dir=tmp) == []   # gated
    fired = mine.auto_promote(conn, min_sweeps=1, conf_gate=0.75, base_dir=tmp)
    assert any("workflow-write-file" in p for p in fired)


def test_mined_workflow_promotes_to_skill():
    import tempfile
    from aos import mine, skills
    conn = _fresh()
    for _ in range(3):
        engine.run(conn, engine.create_goal(conn, "r"))
    mine.mine(conn, threshold=3)
    sk = mine.promote(conn, "recipe:write_file:file_contains", base_dir=tempfile.mkdtemp())
    assert sk is not None and skills.resolve(conn, sk.name) is not None
    # idempotent: same recipe promotes to the same skill name
    assert mine.promote(conn, "recipe:write_file:file_contains", base_dir=tempfile.mkdtemp()).name == sk.name


def test_workflow_mining_is_idempotent():
    from aos import mine
    conn = _fresh()
    for _ in range(3):
        engine.run(conn, engine.create_goal(conn, "r"))
    first = mine.mine(conn, threshold=3)
    assert any("write_file" in c["recipe"] for c in first)
    assert mine.mine(conn, threshold=3) == []        # proposed once


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
