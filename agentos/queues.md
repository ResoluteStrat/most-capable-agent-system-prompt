# Momentum Queues

The system must never end a meaningful run with all five queues undefined.
These are the live human-facing momentum queues. The DB mirrors task state; this
file is the at-a-glance operator view. Updated by `aos queues --sync`.

## now
- M1–M6 done and verified (`aos selftest`; `aos eval` 21/21 timed + repeat-run
  stable; 17/17 tests). Universal `aos ask` router + `aos rollup` altitude control
  + 3 harnesses on a shared resumable base + browser adapter seam with skeptical QA.

## next
1. M7 — wire `improve.tune_config` + a portfolio-attention scan into the recurring
   sweep so the system proposes its own next work and tunes itself when idle.
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
