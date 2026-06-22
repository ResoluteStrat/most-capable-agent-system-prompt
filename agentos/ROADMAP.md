# Roadmap

## M1 — Closed loop, verified  ✅ (this build)
goal → task graph → pull-claim → typed executor → **separate verifier** →
memory (episodic/semantic/procedural) → visibility (status/dash/files) →
learning. Proven by `aos selftest` + `aos eval`. File-first project packs +
SQLite control plane. Metrics, budgets, audit events, deny-first shell policy.

## M2 — Profiles, routing, trust, approvals  ✅ (shipped)
- Loadable **profiles** (planner / executor / verifier / reviewer) as JSON data,
  not prompts baked in code. `route_profile()` matches kind first, then skill tags.
- **Model-routing adapter** (`aos/adapters/model.py`) behind a stable `route()`
  interface — deterministic stub today, real gateway later, engine unchanged.
  Cheap by default; escalates to the strong tier for high-risk work. Cost flows
  into `runs.cost_ticks`.
- **Trust- and risk-gated autonomy** (`aos/autonomy.py`): low-risk auto; medium-
  risk needs earned trust (≥0.5); high-risk always pauses for approval. Trust
  moves on real outcomes; `tier()` maps it supervised→guided→autonomous→trusted.
- Approval queue CLI (`aos approvals --approve/--deny`) + `aos profiles` + dash
  shows per-skill autonomy tier. 4 new eval cases (10/10), 11/11 tests.

## M3 — Eval program depth + self-improvement engine  ◑ (core shipped)
- ✅ Eval categories now span capability, regression, behavioral/safety,
  **adversarial** (instructions-in-data stay inert), and **long-horizon**
  (8-step dependent chain). 12 cases. Each case is **timed** (time-to-pass) and
  **repeat-run stable** (`evals.stability()` → identical pass set across k runs).
- ✅ Config self-improvement: a safe, versioned `config` surface +
  `improve.tune_config` runs a one-change keep/revert loop **behind the eval
  gate** — strictly-better-or-revert; equal/worse → revert (default/simpler wins).
  Verified it correctly *rejects* a "be more autonomous" change that would break
  the trust gate. `aos config` / `aos improve --tune`.
- ✅ failure→eval converter wired into the failure loop (`improve.cycle`).
- ⏳ Still deferred: code-editing self-improvement (needs deeper eval coverage to
  protect it) and pass@k under stochastic executors (harness is deterministic).

## M4 — Specialized harness library (state machines)  ◑ (first harness shipped)
- ✅ Generic resumable state machine (`aos/harness/base.py`): ordered phases,
  entry guards, per-phase separate verify, status persisted to `harness_runs` +
  a checkpoint file. Resume skips `done` phases and restarts at the first
  non-done one (workspace is canonical — fix in place, then continue).
- ✅ First harness: **coding & delivery** (plan → change → test → review → gate),
  builder ≠ reviewer (review runs deny-first + forbidden-token scan on the
  change). `aos harness coding`. 3 eval cases + 2 tests (happy / resume / review-
  blocks-bad-change). Verified end-to-end: failing test stops at `test`, fix the
  workspace, resume runs test→review→gate to a passed ship gate.
- ✅ Second harness: **document/report** (intake → validate → render → review),
  reusing `base` unchanged — proves the state machine generalizes. Demonstrates a
  schema-validated phase boundary (refuses to render incomplete input) and
  programmatic templated output (the model never freestyles the format).
  `aos harness report`. 2 eval cases (happy / schema-gate-refusal).
- ⏳ Next: extract the workspace-fix/reapply policy into a documented harness
  contract; add a finance/reporting harness variant on the same base.

## M5 — Computer-use adapters  ◑ (browser seam shipped)
- ✅ Browser adapter (`aos/adapters/browser.py`): stable `BrowserBackend`
  interface + deterministic `SimBrowser` backend; `BrowserSession` enforces
  observe-before-act and writes before/after evidence per action.
- ✅ Skeptical QA evaluator (`aos/adapters/browser_qa.py`), separate from the
  actor, fails closed — certifies only on positive evidence.
- ✅ `browser_research` harness (open→act→extract→qa) on the shared base (3rd
  harness). `aos harness browser`. 2 eval cases (happy / QA-rejects-failed-flow).
- ⏳ Next: real backend (Playwright/CDP) behind `BrowserBackend`; session/auth
  reuse; selector healing; desktop adapter. Cross-process resume of a live
  browser flow is out of scope (browser state isn't durable — flows run in one
  invocation; deterministic re-run is the recovery model).

## M6 — Human interface surfaces  ◑ (universal ask shipped)
- ✅ Universal `aos ask "<intent>"` surface — a deterministic, transparent intent
  router (scored keyword signals, word-boundary matching, no LLM) that infers
  answer / execute / monitor / harness:{coding,report,browser}, shows the chosen
  mode + why, and routes (reversible modes run; side-effecting ones are
  recommended). Below a confidence margin it surfaces alternatives instead of
  guessing. 1 eval case (5/5 intents) + a test.
- ✅ Altitude control (`aos rollup`): the same state aggregated at task →
  project → portfolio, with a portfolio "needs attention" inbox (failed/blocked
  work + pending approvals). Pure functions in `rollup.py` so a web UI can reuse
  them. 1 eval case + a test.
- ✅ Thin **web control plane** (`aos web`, `aos/web.py`): read-only stdlib
  http.server exposing `/api/snapshot` (portfolio + metrics), `/api/events?since=`
  (the live stream, polled), `/api/goal?id=`, and a single-page dashboard that
  polls them every 2s. Same state, another surface; no mutations (CLI stays the
  action surface). Data layer is pure functions; smoke-tested against a live
  socket. 1 eval + a test.

## M7 — Self-driving momentum loop + external intelligence + multi-machine  ◑
- ✅ Self-driving recurring sweep (`aos recurring [--tune]`, `aos/sweep.py`):
  portfolio scan → proactive proposals for failed/blocked/stalled work + the
  failure→eval converter (+ optional config tuning behind the eval gate). The
  system proposes its own next work instead of going idle. 1 eval case + a test.
  (Fixed a meta-recursion: improve now scores against a core suite that excludes
  the sweep case.)
- ✅ External-intelligence loop (`aos intel`, `aos/intel.py`): ingest structured
  items into the dedicated `external` memory layer (deduped by URL), score by
  ARCHITECTURAL relevance (reward durable execution / checkpoint / typed
  contracts / memory / routing / sandbox / eval / approvals / traceability;
  penalize thin-wrapper / chat-shell / UI-only / trend noise), and PROMOTE
  high-signal items into experiment candidates — the news→improvement pipeline.
  The recurring sweep reports queued intel experiments. 1 eval + a test.
  `examples/intel_sample.json` is a runnable starter set.
- ⏳ Next: a swappable fetcher layer feeding `intel.ingest`; hub-worker scale-out.

- ✅ Hub-worker scale-out (`aos worker`, `aos/worker.py`): pull-based workers on
  one shared task graph. The engine's atomic claim (UPDATE…WHERE status='pending')
  makes many workers — threads or separate processes/machines on the same DB —
  collaborate with **zero double-execution**. Proven by an eval + a test (two
  workers → exactly one run per task) and a live two-process CLI demo. `worker_id`
  threaded through tick/run; `loop` is the daemon form with idle backoff.
- ✅ Swappable fetcher layer (`aos/fetchers.py`, `aos intel --fetch`): RSS/Atom/
  JSON → normalized intel items via stdlib xml.etree. `FileFetcher` (offline,
  deterministic — used by the eval/test) and `HttpFetcher` (urllib, NETWORK-
  OPTIONAL — returns [] on any failure, never crashes the loop). 1 eval + a test.
- ⏳ Next: cross-machine git-worktree lanes per worker.

## Reliability hardening — idempotent effects + sagas + durable waits  ✅
- `aos/effects.py` + `effects` table (rules 16-17): every side-effecting action
  goes through the ledger with an **idempotency key** so a retry replays the
  recorded result instead of re-applying the effect; every forward action records
  a **compensation** so a multi-step workflow rolls back on partial failure
  (saga). Queryable via `aos effects`. 2 eval cases + 2 tests (action-runs-once;
  3-step saga compensates prior steps in reverse when the last fails).
- ✅ Engine integration: side-effecting executors (`shell`/`python`) now run
  through `effects.guarded` keyed by task id, so a retried task REPLAYS its
  committed result instead of re-applying the side effect. Proven through the real
  engine: a python task retried twice applies its effect exactly once (1 apply,
  1 replay). 1 eval + 1 test.
- ✅ Quarantine / dead-letter (`aos/quarantine.py` + `quarantine` table, rule 21):
  a terminally-failed task is captured with an evidence bundle (reason, attempts,
  last output, verifier evidence) instead of thrashing. Replay is EXPLICIT
  (`aos replay <task_id>`); a task re-quarantined ≥3 times is flagged POISON and
  refused. `aos quarantine` lists the queue. Proven: capture → operator fixes root
  cause → explicit replay → recovers to done. 1 eval + 1 test.
- ✅ Durable waitpoints (`aos/waitpoints.py` + `waitpoints` table, rules 18-19):
  a `wait` task pauses on a **timer** (resume when now ≥ wake_at), a **signal**
  (resume when delivered, e.g. a webhook), or **approval** — with exact state on
  disk, so a FRESH process resumes from the waitpoint, not from zero. The engine
  flips ready waits back to runnable at tick start. `aos signal <name>` / `aos
  waits`. Proven across separate processes (signal delivered, fresh-connection run
  resumes to done). 2 evals + 2 tests.

## M7 details — External-intelligence loop + multi-machine
Scheduled digest of open-source agent architecture → ranked experiments → evals.
Hub-worker scale-out: multiple workers, then multiple machines on one task graph
(git worktrees per owned lane).
