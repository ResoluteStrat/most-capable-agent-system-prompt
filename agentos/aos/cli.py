"""AgentOS CLI — the human control plane.

    python -m aos <command> [args]

Commands:
  ask "<intent>"                              universal entry: infer mode + route
  goal "<title>" [--desc ...] [--mode ...]   intake a goal (creates a project pack)
  run [--goal ID] [--max N]                   drive eligible tasks to completion
  status [--goal ID]                          human-readable state
  rollup [--goal ID | --task ID]              altitude control: portfolio→project→task
  dash                                        live dashboard (queues, recent events)
  queues [--sync]                             show / sync momentum queues
  metrics                                     proof-of-progress metrics
  eval                                        run the eval harness
  improve [--tune]                            one bounded self-improvement cycle
                                              (--tune = config keep/revert behind evals)
  config [--set k=v | --reset k|all]          show / tune the safe config surface
  approvals [--approve ID|--deny ID]          approval queue
  recurring                                   proactive sweep → propose goals
  profiles                                     list behavior profiles + model routing
  harness coding [--spec f.json] [--goal ID]   run the coding & delivery state machine
                 [--no-resume]                 (plan→change→test→review→gate; resumable)
  selftest                                    prove the full closed loop end-to-end
"""
from __future__ import annotations

import argparse
import json
import sys

from . import engine, evals, improve, projectpack
from .db import emit, init_db, jloads, now


def _conn():
    return init_db()


def cmd_goal(args):
    conn = _conn()
    gid = engine.create_goal(conn, args.title, args.desc or "", args.mode)
    goal = conn.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone()
    print(f"created goal {gid}: {args.title}")
    print(f"project pack: {goal['project_dir']}")
    n = conn.execute("SELECT COUNT(*) c FROM tasks WHERE goal_id=?", (gid,)).fetchone()["c"]
    print(f"decomposed into {n} tasks. run: python -m aos run --goal {gid}")


def cmd_run(args):
    conn = _conn()
    outcomes = engine.run(conn, args.goal, max_ticks=args.max)
    if not outcomes:
        print("no eligible tasks.")
        return
    for o in outcomes:
        mark = {"done": "✓", "failed": "✗", "retry": "↻",
                "awaiting_approval": "⏸"}.get(o.get("result"), "•")
        print(f"  {mark} {o.get('title', o.get('task_id'))} -> {o.get('result')}")
    print(f"\n{len(outcomes)} ticks. " + json.dumps(engine.metrics(conn)))


def cmd_status(args):
    conn = _conn()
    q = "SELECT * FROM goals" + (" WHERE id=?" if args.goal else "") + " ORDER BY created_at DESC"
    goals = conn.execute(q, (args.goal,) if args.goal else ()).fetchall()
    if not goals:
        print("no goals yet. create one: python -m aos goal \"...\"")
        return
    for g in goals:
        tasks = conn.execute("SELECT * FROM tasks WHERE goal_id=? ORDER BY priority", (g["id"],)).fetchall()
        done = sum(t["status"] == "done" for t in tasks)
        print(f"\n[{g['status'].upper()}] {g['id']} — {g['title']}  ({done}/{len(tasks)} done)")
        for t in tasks:
            print(f"    {t['status']:8} {t['kind']:11} {t['title']}")


def cmd_dash(args):
    conn = _conn()
    m = engine.metrics(conn)
    print("══ AgentOS dashboard ══", now())
    print("\nMETRICS")
    for k, v in m.items():
        print(f"  {k:20} {v}")
    print("\nGOALS")
    for g in conn.execute("SELECT * FROM goals ORDER BY created_at DESC LIMIT 8"):
        print(f"  [{g['status']:6}] {g['id']}  {g['title']}")
    print("\nTRUST (per-skill → autonomy tier)")
    from . import autonomy
    for r in conn.execute("SELECT mkey,value FROM memory WHERE mtype='preference' AND mkey LIKE 'trust:%'"):
        val = float(r["value"])
        print(f"  {r['mkey'][6:]:12} {val:.3f}  [{autonomy.tier(val)}]")
    print("\nRECENT EVENTS")
    for e in conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT 12"):
        print(f"  {e['ts']}  {e['kind']:22} {e['task_id'] or e['goal_id'] or ''}")
    pend = conn.execute("SELECT COUNT(*) c FROM approvals WHERE status='pending'").fetchone()["c"]
    if pend:
        print(f"\n⏸  {pend} approval(s) pending → python -m aos approvals")


def cmd_metrics(args):
    print(json.dumps(engine.metrics(_conn()), indent=2))


def cmd_eval(args):
    conn = _conn()
    results = evals.run_suite(conn)
    npass = sum(1 for _, p, _ in results if p)
    for name, passed, detail in results:
        print(f"  {'PASS' if passed else 'FAIL'}  {name:24} {detail}")
    print(f"\n{npass}/{len(results)} eval cases passing")
    sys.exit(0 if npass == len(results) else 1)


def cmd_improve(args):
    conn = _conn()
    out = improve.tune_config(conn) if args.tune else improve.cycle(conn)
    print(json.dumps(out, indent=2))


def cmd_config(args):
    from . import config
    if args.set:
        key, _, raw = args.set.partition("=")
        try:
            val = json.loads(raw)
        except json.JSONDecodeError:
            val = raw
        config.set(key.strip(), val)
        print(f"set {key.strip()} = {val!r}")
        return
    if args.reset:
        config.reset(None if args.reset == "all" else args.reset)
        print(f"reset {args.reset}")
        return
    cfg = config.load()
    for k, v in cfg.items():
        flag = "" if config.DEFAULTS.get(k) == v else "  (overridden)"
        print(f"  {k:26} {v}{flag}")


def cmd_approvals(args):
    conn = _conn()
    if args.approve or args.deny:
        aid = args.approve or args.deny
        status = "approved" if args.approve else "denied"
        conn.execute("UPDATE approvals SET status=?, decided_at=? WHERE id=?", (status, now(), aid))
        # un-block the task so the worker can re-pick it
        row = conn.execute("SELECT task_id FROM approvals WHERE id=?", (aid,)).fetchone()
        if row:
            new = "pending" if args.approve else "failed"
            conn.execute("UPDATE tasks SET status=? WHERE id=?", (new, row["task_id"]))
            emit(conn, f"approval.{status}", task_id=row["task_id"])
        conn.commit()
        print(f"approval {aid} -> {status}")
        return
    rows = conn.execute("SELECT * FROM approvals WHERE status='pending'").fetchall()
    if not rows:
        print("no pending approvals.")
        return
    for r in rows:
        print(f"  #{r['id']}  task={r['task_id']}  {r['reason']}")
    print("\napprove: python -m aos approvals --approve <id>   deny: --deny <id>")


def cmd_recurring(args):
    """Self-driving sweep: portfolio scan → proactive proposals + failure→eval
    (+ optional config tuning behind the eval gate). The momentum loop."""
    from . import sweep
    d = sweep.run(_conn(), tune=getattr(args, "tune", False))
    if d["proposals"]:
        print("proactive proposals:")
        for p in d["proposals"]:
            print(f"  - {p}")
    else:
        print("sweep clean: no stalled or failed work detected.")
    print(f"\nimprove: {d['improve']}   tune: {d['tune']}   "
          f"pending approvals: {d['pending_approvals']}")


def cmd_profiles(args):
    from . import profiles
    from .adapters import model
    for p in profiles.load_all().values():
        r = model.route(p)
        print(f"  {p['name']:9} tier={p.get('model_tier'):6} ({r['model']}, cost={r['cost']})  "
              f"kinds={p.get('handles_kinds')} tags={p.get('handles_tags')}")


def cmd_harness(args):
    from pathlib import Path

    from . import engine
    from .harness import browser_research, coding_delivery, document_report
    conn = _conn()
    _site = {"https://demo/login": {"text": "Login", "links": {},
                                    "fields": {"user": "", "pass": ""},
                                    "submit": {"to": "https://demo/home", "requires": {"user": "ada"}}},
             "https://demo/home": {"text": "Welcome ada", "links": {}, "fields": {}}}
    defaults = {
        "coding": {"plan": "demo change", "files": {"hello.py": "print('hi')\n"}, "test_cmd": "true"},
        "report": {"data": {"title": "Weekly Report", "period": "2026-W25",
                            "metrics": {"tasks_done": 15, "eval_pass_rate": 1.0},
                            "findings": ["loop stable", "no regressions"]}},
        "browser": {"site": _site, "start": "https://demo/login",
                    "steps": [{"action": "type", "field": "user", "value": "ada"},
                              {"action": "click", "target": "submit"}],
                    "extract": {"contains": "Welcome"},
                    "goal": {"final_url": "https://demo/home", "must_contain": ["Welcome"]}},
    }
    spec = json.loads(Path(args.spec).read_text()) if args.spec else defaults[args.name]
    goal_id = args.goal
    if not goal_id:
        goal_id = engine.create_goal(conn, f"Harness: {args.name}", tasks=[])
    goal = conn.execute("SELECT project_dir FROM goals WHERE id=?", (goal_id,)).fetchone()
    workspace = args.workspace or str(Path(goal["project_dir"]) / "artifacts" / "workspace")
    harnesses = {"coding": coding_delivery.build, "report": document_report.build,
                 "browser": browser_research.build}
    h = harnesses[args.name]()
    out = h.run(conn, goal_id, {"workspace": workspace, "spec": spec}, resume=not args.no_resume)
    print(f"harness {out['harness']} → {out['status'].upper()} (last phase: {out['phase']})")
    for ph, st in out["phases"].items():
        print(f"  {st:8} {ph}")
    if out["status"] != "done":
        print(f"\nresumable: fix the issue and re-run "
              f"`aos harness {args.name} --goal {goal_id}` to continue from here.")


def cmd_queues(args):
    from .db import ROOT
    qf = ROOT / "queues.md"
    if args.sync:
        conn = _conn()
        blocked = conn.execute("SELECT COUNT(*) c FROM tasks WHERE status='blocked'").fetchone()["c"]
        print(f"(sync) blocked tasks in DB: {blocked}")
    print(qf.read_text() if qf.exists() else "queues.md not found")


def cmd_rollup(args):
    """Altitude control: --task ID < --goal ID < (default) portfolio."""
    from . import rollup
    conn = _conn()
    if args.task:
        r = rollup.task_rollup(conn, args.task)
        if not r:
            print("no such task"); return
        print(f"TASK {r['id']} — {r['title']}  [{r['status']}]")
        print(f"  kind={r['kind']} risk={r['risk']} attempts={r['attempts']} tags={r['skill_tags']}")
        print(f"  artifacts={r['artifacts']}")
        for i, run in enumerate(r["runs"]):
            print(f"  run {i}: ok={run['ok']} verified={run['verified']} cost={run['cost']}")
        if r["escalation"]:
            print(f"  escalation: {r['escalation']}")
        return
    if args.goal:
        r = rollup.project_rollup(conn, args.goal)
        if not r:
            print("no such goal"); return
        print(f"PROJECT {r['id']} — {r['title']}  [{r['status']}]")
        print(f"  tasks {r['tasks_done']}/{r['tasks_total']} done  by_status={r['by_status']}")
        print(f"  blocked={r['blocked']} failed={r['failed']} cost_ticks={r['cost_ticks']}")
        print(f"  pack: {r['project_dir']}")
        for h in r["harnesses"]:
            print(f"  harness {h['harness']}: {h['status']} @ {h['phase']}")
        return
    r = rollup.portfolio_rollup(conn)
    print("PORTFOLIO")
    print(f"  goals: {r['goals']}  (active {r['active']} / done {r['done']} / failed {r['failed']})")
    print(f"  tasks: blocked {r['blocked_tasks']} · failed {r['failed_tasks']}  "
          f"cost_ticks {r['cost_ticks']}  pending_approvals {r['pending_approvals']}")
    print("  NEEDS ATTENTION:" if r["attention"] else "  needs attention: none")
    for a in r["attention"]:
        print(f"    - {a}")
    print("  projects:")
    for p in r["projects"]:
        print(f"    [{p['status']:6}] {p['id']}  {p['done']}/{p['total']}  {p['title']}")


def cmd_ask(args):
    """Universal entry: infer the mode, show why, route. Reversible modes run;
    side-effecting ones are recommended (the user stays in control)."""
    from . import ask, engine
    text = args.text
    c = ask.classify(text)
    conf = "confident" if c["confident"] else f"low-confidence (alts: {c['alternatives']})"
    print(f"intent: {c['mode']}  [{conf}; signals={c['signals']}]")
    if not c["confident"]:
        print("  (ambiguous — routing to the best guess; override with the explicit command)")

    mode = c["mode"]
    conn = _conn()
    if mode == "answer":
        print()
        cmd_dash(args)
    elif mode == "monitor":
        print("\nrouting to the proactive sweep (schedule via your runner for recurrence):\n")
        cmd_recurring(args)
    elif mode == "harness:report":
        print("\nrunning the report harness with defaults:\n")
        args.name, args.spec, args.goal, args.workspace, args.no_resume = "report", None, None, None, True
        cmd_harness(args)
    elif mode == "harness:coding":
        print("\nrecommended: aos harness coding --spec <change.json>")
    elif mode == "harness:browser":
        print("\nrecommended: aos harness browser --spec <flow.json>")
    else:  # execute
        gid = engine.create_goal(conn, text)
        print(f"\ncreated goal {gid}; driving it:\n")
        for o in engine.run(conn, gid):
            print(f"  {o.get('result'):8} {o.get('title','')}")
        print("\n" + json.dumps(engine.metrics(conn)))


def cmd_selftest(args):
    """M1 proof: full closed loop + eval suite, deterministic, repeatable."""
    print("AgentOS selftest — proving the closed loop\n")
    conn = _conn()
    gid = engine.create_goal(conn, "Selftest: prove the closed loop",
                             "Goal→tasks→exec→verify→memory→visibility→learning.")
    print(f"1. goal intake: {gid}")
    outcomes = engine.run(conn, gid)
    for o in outcomes:
        print(f"   {o.get('result'):8} {o.get('title','')}")
    goal = conn.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone()
    proc = conn.execute("SELECT COUNT(*) c FROM memory WHERE mtype='procedural'").fetchone()["c"]
    print(f"2. goal status: {goal['status']}")
    print(f"3. procedural memory recipes learned: {proc}")
    from pathlib import Path
    pack = Path(goal["project_dir"])
    files = [f.name for f in pack.glob("*.md")] + [f"artifacts/{f.name}" for f in (pack/'artifacts').glob('*')]
    print(f"4. project pack files: {sorted(files)}")
    print("5. metrics:", json.dumps(engine.metrics(conn)))
    print("\n6. eval harness:")
    results = evals.run_suite(conn)
    npass = sum(1 for _, p, _ in results if p)
    for name, passed, detail in results:
        print(f"   {'PASS' if passed else 'FAIL'}  {name:24} {detail}")

    loop_ok = goal["status"] == "done" and proc >= 2 and (pack / "status.md").exists()
    ok = loop_ok and npass == len(results)
    print(f"\n{'✅ SELFTEST PASS' if ok else '❌ SELFTEST FAIL'} — "
          f"loop={'ok' if loop_ok else 'broken'}, evals={npass}/{len(results)}")
    sys.exit(0 if ok else 1)


def build_parser():
    p = argparse.ArgumentParser(prog="aos", description="AgentOS control plane")
    sub = p.add_subparsers(dest="cmd", required=True)

    ak = sub.add_parser("ask"); ak.add_argument("text"); ak.set_defaults(fn=cmd_ask)
    g = sub.add_parser("goal"); g.add_argument("title"); g.add_argument("--desc")
    g.add_argument("--mode", default="general"); g.set_defaults(fn=cmd_goal)
    r = sub.add_parser("run"); r.add_argument("--goal"); r.add_argument("--max", type=int, default=100)
    r.set_defaults(fn=cmd_run)
    s = sub.add_parser("status"); s.add_argument("--goal"); s.set_defaults(fn=cmd_status)
    rl = sub.add_parser("rollup"); rl.add_argument("--goal"); rl.add_argument("--task")
    rl.set_defaults(fn=cmd_rollup)
    sub.add_parser("dash").set_defaults(fn=cmd_dash)
    sub.add_parser("metrics").set_defaults(fn=cmd_metrics)
    sub.add_parser("eval").set_defaults(fn=cmd_eval)
    im = sub.add_parser("improve"); im.add_argument("--tune", action="store_true")
    im.set_defaults(fn=cmd_improve)
    cf = sub.add_parser("config"); cf.add_argument("--set"); cf.add_argument("--reset")
    cf.set_defaults(fn=cmd_config)
    a = sub.add_parser("approvals"); a.add_argument("--approve"); a.add_argument("--deny")
    a.set_defaults(fn=cmd_approvals)
    rc = sub.add_parser("recurring"); rc.add_argument("--tune", action="store_true")
    rc.set_defaults(fn=cmd_recurring)
    sub.add_parser("profiles").set_defaults(fn=cmd_profiles)
    hp = sub.add_parser("harness"); hp.add_argument("name", choices=["coding", "report", "browser"])
    hp.add_argument("--spec"); hp.add_argument("--goal"); hp.add_argument("--workspace")
    hp.add_argument("--no-resume", action="store_true"); hp.set_defaults(fn=cmd_harness)
    q = sub.add_parser("queues"); q.add_argument("--sync", action="store_true"); q.set_defaults(fn=cmd_queues)
    sub.add_parser("selftest").set_defaults(fn=cmd_selftest)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
