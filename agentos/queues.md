# Momentum Queues

The system must never end a meaningful run with all five queues undefined.
These are the live human-facing momentum queues. The DB mirrors task state; this
file is the at-a-glance operator view. Updated by `aos queues --sync`.

## now
- M1–M6(ask) done and verified (`aos selftest`; `aos eval` 20/20 timed +
  repeat-run stable; 16/16 tests). Universal `aos ask` router + 3 harnesses on a
  shared resumable base + browser adapter seam with skeptical QA.

## next
1. M6 cont. — altitude control: `aos rollup` (task → project → portfolio) over the
   same state, so the user can zoom without switching tools.
2. M5 cont. — real Playwright backend behind `BrowserBackend`; session/auth reuse.
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
