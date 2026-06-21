# Momentum Queues

The system must never end a meaningful run with all five queues undefined.
These are the live human-facing momentum queues. The DB mirrors task state; this
file is the at-a-glance operator view. Updated by `aos queues --sync`.

## now
- M1 + M2 + M3-core done and verified (`aos selftest`; `aos eval` 12/12 timed +
  repeat-run stable; 13/13 tests). Eval depth (adversarial + long-horizon) and a
  safe config keep/revert self-improvement loop are live.

## next
1. M4 — First specialized harness: **coding & delivery** as an explicit phased
   state machine (plan → change → test → review → gate) with per-phase
   checkpoints + resumability after interruption.
2. M4 — Generalize the harness base (phases, entry/exit criteria, schema-validated
   boundaries, resume) so document/report harness reuses it.
3. M3 follow-up — wire `improve.tune_config` into the recurring sweep so tuning is
   attempted automatically when eval headroom appears.

## blocked
- (none) — single-machine, stdlib build has no external blockers right now.

## improve
- Add a failure→guardrail converter: any task that fails twice the same way
  auto-creates an eval case. (failure loop)
- Replace tick-count cost proxy with real token/cost accounting once an LLM
  executor adapter lands. (cost loop)
- Memory consolidation job: compress episodic events into semantic facts. (memory loop)

## recurring
- `aos recurring` sweep: scan projects for blocked tasks, stale handoffs, dirty
  repos, failing selftest → emit proactive goals. (proactive operations loop)
- External-intelligence digest (manual trigger for now; see ROADMAP M7).
