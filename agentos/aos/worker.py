"""Execution fabric — pull-based workers on one shared task graph.

A worker repeatedly claims one eligible task (atomically, via engine._claim) and
drives it to done/failed, then polls again. Many workers — threads on one machine
or processes across machines pointed at the same DB — collaborate safely because
the claim is a single atomic UPDATE…WHERE status='pending': exactly one worker
wins each task, the rest get `claim-lost` and move on. No central dispatcher.

`run_until_idle` drains the queue (used by the CLI and the concurrency test).
`loop` is the long-running daemon form with polling + an idle backoff.
"""
from __future__ import annotations

import time

from . import engine
from .db import connect, emit


def run_until_idle(conn, worker_id, goal_id=None, max_ticks=1000) -> dict:
    done = failed = claim_lost = 0
    for _ in range(max_ticks):
        out = engine.tick(conn, goal_id, worker_id)
        if out is None:
            break
        r = out.get("result")
        done += r == "done"
        failed += r == "failed"
        claim_lost += r == "claim-lost"
        if r == "awaiting_approval":
            break
    return {"worker": worker_id, "done": done, "failed": failed, "claim_lost": claim_lost}


def loop(worker_id, db_path=None, poll=1.0, max_idle=5, goal_id=None) -> dict:
    """Daemon form: keep claiming; after `max_idle` empty polls, exit. Each worker
    uses its own connection (sqlite connections are per-thread/process)."""
    conn = connect(db_path)
    emit(conn, "worker.start", worker=worker_id)
    totals = {"done": 0, "failed": 0, "claim_lost": 0}
    idle = 0
    while idle < max_idle:
        out = engine.tick(conn, goal_id, worker_id)
        if out is None:
            idle += 1
            time.sleep(poll)
            continue
        idle = 0
        r = out.get("result")
        if r in totals:
            totals[r] += 1
    emit(conn, "worker.stop", worker=worker_id, **totals)
    conn.close()
    return {"worker": worker_id, **totals}
