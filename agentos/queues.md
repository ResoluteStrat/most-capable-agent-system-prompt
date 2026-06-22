# Momentum Queues

The system must never end a meaningful run with all five queues undefined.
These are the live human-facing momentum queues. The DB mirrors task state; this
file is the at-a-glance operator view. Updated by `aos queues --sync`.

## now
- M1–M7 done and verified (`aos selftest`; `aos eval` 25/25 timed + repeat-run
  stable; 21/21 tests). Full surface: closed loop · profiles/routing/trust/
  approvals · eval depth + safe self-improvement · 3 resumable harnesses ·
  browser seam + skeptical QA · `aos ask` router · `aos rollup` altitude ·
  self-driving `aos recurring` · `aos intel` external-intelligence (+ swappable
  RSS/Atom/JSON fetcher) · `aos web` read-only control plane · `aos worker`
  multi-worker scale-out (zero double-execution, proven across threads AND
  processes) · `aos effects` idempotent effect ledger + sagas · durable waitpoints
  (timer/signal/approval, cross-process resume) · quarantine/dead-letter with
  explicit replay (rules 16-21).

## next
1. Observability cont. — trajectory tracing (rule 22): record per-task spans
   (plan/tool/verify/retry/wait/effect) so a whole execution path can be replayed
   and judged, not just the final outcome.
2. M7 cont. — cross-machine git-worktree lanes per worker for parallel coding.
3. M5 cont. — real Playwright backend behind `BrowserBackend` (deferred: needs a
   real browser + dep, unverifiable here; the seam is ready for when it isn't).

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
