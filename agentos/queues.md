# Momentum Queues

The system must never end a meaningful run with all five queues undefined.
These are the live human-facing momentum queues. The DB mirrors task state; this
file is the at-a-glance operator view. Updated by `aos queues --sync`.

## now
- M1 + M2 + M3-core + M4-first-harness done and verified (`aos selftest`;
  `aos eval` 15/15 timed + repeat-run stable; 15/15 tests). Coding & delivery
  harness (plan→change→test→review→gate) is resumable from any phase.

## next
1. M4 cont. — a **document/report** harness on the same base, with schema-
   validated phase boundaries + programmatic templated output (not free-form).
2. M5 — browser adapter slot (named actions, observe-before-act, evidence
   capture) + a skeptical QA evaluator separate from the builder.
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
