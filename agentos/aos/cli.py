"""AgentOS CLI — the human control plane.

    python -m aos <command> [args]

Commands:
  goal "<title>" [--desc ...] [--mode ...]   intake a goal (creates a project pack)
  run [--goal ID] [--max N]                   drive eligible tasks to completion
  status [--goal ID]                          human-readable state
  dash                                        live dashboard (queues, recent events)
  queues [--sync]                             show / sync momentum queues
  metrics                                     proof-of-progress metrics
  eval                                        run the eval harness
  improve                                     one bounded self-improvement cycle
  approvals [--approve ID|--deny ID]          approval queue
  recurring                                   proactive sweep → propose goals
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
    print("\nTRUST (per-skill)")
    for r in conn.execute("SELECT mkey,value FROM memory WHERE mtype='preference' AND mkey LIKE 'trust:%'"):
        print(f"  {r['mkey'][6:]:12} {r['value']}")
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
    out = improve.cycle(_conn())
    print(json.dumps(out, indent=2))


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
    """Proactive operations loop: scan goals for stalled/failed work → propose goals."""
    conn = _conn()
    proposals = []
    for g in conn.execute("SELECT * FROM goals WHERE status IN ('active','failed')"):
        failed = conn.execute("SELECT COUNT(*) c FROM tasks WHERE goal_id=? AND status='failed'",
                              (g["id"],)).fetchone()["c"]
        if failed:
            proposals.append(f"investigate {failed} failed task(s) in goal {g['id']} ({g['title']})")
    if not proposals:
        print("sweep clean: no stalled or failed work detected.")
        return
    print("proactive proposals:")
    for p in proposals:
        print(f"  - {p}")
        emit(conn, "proactive.proposal", detail=p)


def cmd_queues(args):
    from .db import ROOT
    qf = ROOT / "queues.md"
    if args.sync:
        conn = _conn()
        blocked = conn.execute("SELECT COUNT(*) c FROM tasks WHERE status='blocked'").fetchone()["c"]
        print(f"(sync) blocked tasks in DB: {blocked}")
    print(qf.read_text() if qf.exists() else "queues.md not found")


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

    g = sub.add_parser("goal"); g.add_argument("title"); g.add_argument("--desc")
    g.add_argument("--mode", default="general"); g.set_defaults(fn=cmd_goal)
    r = sub.add_parser("run"); r.add_argument("--goal"); r.add_argument("--max", type=int, default=100)
    r.set_defaults(fn=cmd_run)
    s = sub.add_parser("status"); s.add_argument("--goal"); s.set_defaults(fn=cmd_status)
    sub.add_parser("dash").set_defaults(fn=cmd_dash)
    sub.add_parser("metrics").set_defaults(fn=cmd_metrics)
    sub.add_parser("eval").set_defaults(fn=cmd_eval)
    sub.add_parser("improve").set_defaults(fn=cmd_improve)
    a = sub.add_parser("approvals"); a.add_argument("--approve"); a.add_argument("--deny")
    a.set_defaults(fn=cmd_approvals)
    sub.add_parser("recurring").set_defaults(fn=cmd_recurring)
    q = sub.add_parser("queues"); q.add_argument("--sync", action="store_true"); q.set_defaults(fn=cmd_queues)
    sub.add_parser("selftest").set_defaults(fn=cmd_selftest)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
