# Roadmap

## M1 — Closed loop, verified  ✅ (this build)
goal → task graph → pull-claim → typed executor → **separate verifier** →
memory (episodic/semantic/procedural) → visibility (status/dash/files) →
learning. Proven by `aos selftest` + `aos eval`. File-first project packs +
SQLite control plane. Metrics, budgets, audit events, deny-first shell policy.

## M2 — Profiles, routing, trust, approvals
- Loadable **profiles** (planner / executor / verifier / reviewer) as data, not
  prompts baked in code. Skill-tag → profile routing table.
- **Model-routing adapter** slot (cheap-vs-strong) behind a stable interface; no
  vendor lock-in. Budget accounting by model/task/goal.
- **Per-skill trust scores** promoted from real outcomes; autonomy tiers
  (supervised → guided → autonomous) gated by trust.
- Approval queue CLI (`aos approvals`) + richer deny-first policy + tests.

## M3 — Eval program depth + self-improvement engine
- Eval categories: capability, regression, behavioral/safety, adversarial,
  long-horizon. pass@1 + repeat-run stability + cost/time-to-pass.
- Background self-improvement loop: one bounded change → eval slice → keep/revert,
  fully logged. Equal-score → simpler wins.
- failure→eval converter wired into the failure loop.

## M4 — Specialized harness library (state machines)
First specialized harness: **coding & delivery** (plan → change → test → review →
gate) as an explicit phased state machine with checkpoints + resumability. Then a
**document/report** harness with schema-validated phase boundaries and templated
programmatic output.

## M5 — Computer-use adapters
Browser adapter (named actions, observe-before-act, evidence capture, session
reuse) + a skeptical QA evaluator separate from the builder. Desktop later.

## M6 — Human interface surfaces
Universal ask surface + altitude control (task → project → portfolio). CLI first,
then a thin web control plane reading the same state. Live event stream.

## M7 — External-intelligence loop + multi-machine
Scheduled digest of open-source agent architecture → ranked experiments → evals.
Hub-worker scale-out: multiple workers, then multiple machines on one task graph
(git worktrees per owned lane).
