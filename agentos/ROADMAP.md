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
- ⏳ Next: altitude control (task → project → portfolio rollups over the same
  state) and a thin web control plane reading the same DB + a live event stream.

## M7 — External-intelligence loop + multi-machine
Scheduled digest of open-source agent architecture → ranked experiments → evals.
Hub-worker scale-out: multiple workers, then multiple machines on one task graph
(git worktrees per owned lane).
