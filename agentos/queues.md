# Momentum Queues

The system must never end a meaningful run with all five queues undefined.
These are the live human-facing momentum queues. The DB mirrors task state; this
file is the at-a-glance operator view. Updated by `aos queues --sync`.

## now
- M1–M7(sweep) done and verified (`aos selftest`; `aos eval` 22/22 timed +
  repeat-run stable; 18/18 tests). Self-driving `aos recurring` momentum loop +
  `aos ask` router + `aos rollup` altitude control + 3 harnesses + browser seam.

## next
1. M7 cont. — external-intelligence digest loop (capture source→claim→experiment
   →eval candidate) as a new memory layer + `aos intel` command.
2. M6 cont. — thin web control plane reading the same DB + a live event stream.
3. M5 cont. — real Playwright backend behind `BrowserBackend`; session/auth reuse.

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
