# AgentOS — Design Map

How this implementation answers the prompt. ~3,100 lines of stdlib Python across
29 modules; 25 eval cases (timed + repeat-run stable); 21 tests; `aos selftest`
green. This file maps each subsystem to the prompt's architecture so coverage is
auditable at a glance.

## The closed loop (what M1 proved, everything else extends)
```
goal → task graph → pull-claim → execute → INDEPENDENT verify → memory → visibility → learning
 │         │            │          │            │                  │          │          │
create_  decompose/  engine._    executors  verify.py          memory.py  projectpack rollup/
goal     add_task    claim       .py        (separate)         + trust    + web + dash improve
```

## Prompt layers → modules
| Prompt layer | Implemented by | Notes |
|---|---|---|
| A. Control plane | `db.py` + `schema.sql`, `cli.py`, `web.py` | SQLite WAL; CLI + read-only HTTP. |
| B. Execution fabric | `worker.py`, `engine.tick/_claim` | Pull-based, atomic claim, multi-worker, daemon `loop`. |
| C. Task graph engine | `engine.py` | goals→tasks, deps, fan-in, retry/escalate, DoD+verification per task. |
| D. Skill/profile system | `profiles.py` + `profiles/*.json` | Loadable behavior packs; kind→tag routing. |
| E. Memory system | `memory.py` | episodic/semantic/procedural/preference/external; trust; reuse metric. |
| F. Tool adapters | `executors.py`, `adapters/browser.py` | Typed actions; browser seam (observe-before-act, evidence). |
| G. Model routing & economics | `adapters/model.py` | Stable `route()`; cheap→strong on risk; cost→`runs.cost_ticks`. |
| H. Governance/policy/trust | `policy.py`, `autonomy.py`, approvals | Deny-first shell; trust+risk gate; approval queue. |
| I. Evaluation & learning | `evals/`, `improve.py` | capability/behavioral/regression/safety/adversarial/long-horizon; keep-revert. |
| J. Self-improvement | `improve.py`, `sweep.py`, `intel.py` | failure→eval; config tune behind gate; news→experiment. |
| K. Observability & incidents | `events` table, `dash`, `web` live stream | every action emits; incidents via failed-task escalation. |
| L. Context management | `projectpack.py` (file-first packs) | plan/tasks/status/handoff/knowledge/decisions + artifacts; resumable. |

## Non-negotiable design bets → how honored
- **One strong agent + task graph + separate verifier + durable memory + control
  plane** — exactly the shape; no agent swarm. (`engine` + `verify` + `memory` + `cli`/`web`.)
- **Verification is a separate concern** — `verify.py` runs independently; the
  `verifier_independent` eval proves it rejects an executor that lies about success.
- **Files canonical, DB derived** — `projects/<id>/*.md` is source of truth; DB
  rebuildable. Container is ephemeral → git is the durability layer.
- **Deterministic harness, no LLM inside it** — every module is stdlib + testable;
  open-ended reasoning enters by authoring task specs (`create_goal(tasks=...)`).
- **Bounded autonomy** — atomic claim, 1 auto-retry then escalate, attempt cap,
  deny-first destructive shell, trust-gated approvals, full audit log.
- **One-change eval loop; equal score → simpler** — `improve.tune_config`
  strictly-better-or-revert (verified it rejects a gate-weakening change).

## Specialized harness library (state machines on one base)
`harness/base.py` (resumable phase machine) + three harnesses:
`coding_delivery` (plan→change→test→review→gate, builder≠reviewer),
`document_report` (schema-gated boundary + programmatic output),
`browser_research` (open→act→extract→qa, actor≠evaluator). All resumable from a
checkpoint; review/QA always separate from the builder.

## Capability surfaces (CAPABILITY_MATRIX.md)
Shell/FS/git/SQLite: native. Browser: working **seam** (`SimBrowser` + evidence +
skeptical QA; real Playwright drops in behind `BrowserBackend`). Desktop/vision:
deferred. Scheduling: file-driven recurring sweep. Multi-machine: pull-workers on
a shared DB (atomic claim proven across processes).

## Momentum (never finish empty-handed)
`queues.md` (now/next/blocked/improve/recurring) + `aos recurring` self-driving
sweep (portfolio scan → proactive proposals + failure→eval + optional tune +
queued intel experiments). Every milestone left a reusable ratchet (skill/profile/
harness/eval/dashboard/policy/memory).

## Command reference
`ask · goal · run · status · rollup · dash · metrics · eval · improve [--tune] ·
config · approvals · recurring [--tune] · intel [--add] · profiles · harness
{coding,report,browser} · worker · web · queues · selftest`

## Where to look first
`OPERATING_SUMMARY.md` (the compact contract) → `aos selftest` (the loop, live) →
`evals/__init__.py` (what "working" means, executably) → `ROADMAP.md` (M1–M7 + next).
