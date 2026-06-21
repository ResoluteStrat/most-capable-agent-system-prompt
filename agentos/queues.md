# Momentum Queues

The system must never end a meaningful run with all five queues undefined.
These are the live human-facing momentum queues. The DB mirrors task state; this
file is the at-a-glance operator view. Updated by `aos queues --sync`.

## now
- M1 closed loop + M2 (profiles, model-routing adapter, trust-gated autonomy,
  approvals UX) implemented and verified (`aos selftest`; `aos eval` 10/10;
  11/11 tests).

## next
1. M3 — Eval depth: adversarial-input case + long-horizon (many-task) case +
   repeat-run stability + cost/time-to-pass tracked per case.
2. M3 — Background self-improvement that can edit a *config* surface (e.g. the
   medium-risk trust gate, profile model tiers) behind the eval gate; keep/revert.
3. M4 — First specialized harness (coding & delivery) as an explicit phased
   state machine with checkpoints + resumability.

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
