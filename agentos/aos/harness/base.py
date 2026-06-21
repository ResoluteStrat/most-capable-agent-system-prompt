"""Generic resumable phased state machine.

A Harness runs an ordered list of Phases. Each phase:
  - has an entry guard (default: previous phase done),
  - runs a deterministic step that writes an artifact,
  - is certified by a SEPARATE verify function (same discipline as the engine),
  - records its status to the harness_runs row + a checkpoint file.

Resumability: re-running a harness with resume=True skips phases already `done`
and restarts at the first non-done phase — so a run interrupted (or stopped at a
failing phase) continues from the last good checkpoint instead of from zero.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..db import emit, jdumps, jloads, now


@dataclass
class Phase:
    name: str
    run: Callable[[dict], dict]                 # ctx -> {ok, output, artifacts}
    verify: Callable[[dict, dict], tuple]       # (ctx, result) -> (passed, evidence)
    entry: Callable[[dict], bool] | None = None # ctx -> bool (default: always ok)


class Harness:
    def __init__(self, name: str, phases: list[Phase]):
        self.name = name
        self.phases = phases

    # ---- persistence -------------------------------------------------------
    def _load(self, conn, goal_id):
        row = conn.execute(
            "SELECT * FROM harness_runs WHERE harness=? AND goal_id=? ORDER BY created_at DESC LIMIT 1",
            (self.name, goal_id)).fetchone()
        return row

    def _checkpoint_path(self, ctx) -> Path:
        return Path(ctx["workspace"]).parent / f"harness_{self.name}.json"

    def _save(self, conn, hid, goal_id, phases, status, phase, ckpt):
        existing = conn.execute("SELECT id FROM harness_runs WHERE id=?", (hid,)).fetchone()
        if existing:
            conn.execute("UPDATE harness_runs SET status=?, phase=?, phases=?, updated_at=? WHERE id=?",
                         (status, phase, jdumps(phases), now(), hid))
        else:
            conn.execute("INSERT INTO harness_runs (id,harness,goal_id,status,phase,phases,checkpoint,"
                         "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                         (hid, self.name, goal_id, status, phase, jdumps(phases), str(ckpt), now(), now()))
        conn.commit()
        Path(ckpt).write_text(json.dumps(
            {"harness": self.name, "goal_id": goal_id, "status": status,
             "phase": phase, "phases": phases, "updated_at": now()}, indent=2))

    # ---- run ---------------------------------------------------------------
    def run(self, conn, goal_id, ctx, resume=True) -> dict:
        Path(ctx["workspace"]).mkdir(parents=True, exist_ok=True)
        ckpt = self._checkpoint_path(ctx)
        prior = self._load(conn, goal_id) if resume else None
        phases = jloads(prior["phases"], {}) if prior else {}
        hid = prior["id"] if prior else f"h_{uuid.uuid4().hex[:8]}"
        for p in self.phases:
            phases.setdefault(p.name, "pending")

        for p in self.phases:
            if resume and phases.get(p.name) == "done":
                continue
            if p.entry and not p.entry(ctx):
                phases[p.name] = "blocked"
                self._save(conn, hid, goal_id, phases, "blocked", p.name, ckpt)
                emit(conn, "harness.phase_blocked", goal_id=goal_id, harness=self.name, phase=p.name)
                return self._result(hid, "blocked", p.name, phases)

            emit(conn, "harness.phase_start", goal_id=goal_id, harness=self.name, phase=p.name)
            try:
                result = p.run(ctx)
                passed, evidence = p.verify(ctx, result)
            except Exception as e:  # a throwing phase fails the run, never crashes it
                phases[p.name] = "failed"
                self._save(conn, hid, goal_id, phases, "failed", p.name, ckpt)
                emit(conn, "harness.phase_failed", goal_id=goal_id, harness=self.name,
                     phase=p.name, error=repr(e))
                return self._result(hid, "failed", p.name, phases, error=repr(e))

            if passed:
                phases[p.name] = "done"
                ctx.setdefault("artifacts", []).extend(result.get("artifacts", []))
                self._save(conn, hid, goal_id, phases, "running", p.name, ckpt)
                emit(conn, "harness.phase_done", goal_id=goal_id, harness=self.name,
                     phase=p.name, evidence=evidence)
            else:
                phases[p.name] = "failed"
                self._save(conn, hid, goal_id, phases, "failed", p.name, ckpt)
                emit(conn, "harness.phase_failed", goal_id=goal_id, harness=self.name,
                     phase=p.name, evidence=evidence)
                return self._result(hid, "failed", p.name, phases, evidence=evidence)

        self._save(conn, hid, goal_id, phases, "done", self.phases[-1].name, ckpt)
        emit(conn, "harness.done", goal_id=goal_id, harness=self.name)
        return self._result(hid, "done", self.phases[-1].name, phases)

    def _result(self, hid, status, phase, phases, **extra):
        return {"harness": self.name, "id": hid, "status": status,
                "phase": phase, "phases": dict(phases), **extra}
