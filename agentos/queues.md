# Momentum Queues

The system must never end a meaningful run with all five queues undefined.
These are the live human-facing momentum queues. The DB mirrors task state; this
file is the at-a-glance operator view. Updated by `aos queues --sync`.

## now
- M1–M7 done and verified (`aos selftest`; `aos eval` 23/23 timed + repeat-run
  stable; 19/19 tests). Self-driving `aos recurring` momentum loop + `aos intel`
  external-intelligence loop + `aos ask` router + `aos rollup` altitude control +
  3 harnesses on a shared resumable base + browser seam with skeptical QA.

## next
1. M6 cont. — thin web control plane reading the same DB + a live event stream
   (read-only HTTP over the existing state; stdlib http.server).
2. M5 cont. — real Playwright backend behind `BrowserBackend`; session/auth reuse.
3. M7 cont. — a swappable fetcher layer (RSS/changelog/release) feeding
   `intel.ingest`; hub-worker scale-out for multi-machine.

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
