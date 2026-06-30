# AgentOS — Design Map

How this implementation answers the prompt. ~4,200 lines of stdlib Python across
35 modules; 36 eval cases (timed + repeat-run stable); 33 tests; 12 control-plane
tables; `aos selftest` green. This file maps each subsystem to the prompt's
architecture so coverage is auditable at a glance.

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
| D. Skill/profile system | `profiles.py` + `profiles/*.json` (5), `skills.py` | Behavior packs (planner/executor/verifier/reviewer/skill-runner); kind→tag routing; **Claude Code SKILL.md adapter** (discover/register/use). |
| E. Memory system | `memory.py` | episodic/semantic/procedural/preference/external; trust; reuse metric. |
| F. Tool adapters | `executors.py`, `adapters/browser.py` | Typed actions (incl. `skill`); browser seam (observe-before-act, evidence). |
| G. Model routing & economics | `adapters/model.py`, `config.py` | Stable `route()`; cheap→strong on risk; cost→`runs.cost_ticks`; tunable config surface. |
| H. Governance/policy/trust | `policy.py`, `autonomy.py`, approvals | Deny-first shell; trust+risk gate; approval queue. |
| I. Evaluation & learning | `evals/`, `improve.py` | capability/behavioral/regression/safety/adversarial/long-horizon/concurrency/skill; keep-revert. |
| J. Self-improvement | `improve.py`, `sweep.py`, `intel.py`, `fetchers.py` | failure→eval; config tune behind gate; news→experiment; RSS/Atom fetcher. |
| K. Observability & incidents | `events` table, `dash`, `web` stream, `trace.py`, `quarantine.py` | every action emits; trajectory tracing + path judge; dead-letter with replay. |
| L. Context management | `projectpack.py` (file-first packs), `waitpoints.py` | plan/tasks/status/handoff/… + artifacts; durable pause/resume across processes. |

## Reliability stack (prompt rules 16–22) → modules
| Rule | Concern | Implemented by |
|---|---|---|
| 16-17 | idempotent side effects + compensating sagas | `effects.py` (`guarded` keyed by task; `saga` rollback) |
| 18-19 | durable waits + checkpoint/resume | `waitpoints.py` (timer/signal/approval), `harness/base.py` (phase checkpoints) |
| 20 | queryable run state | `rollup.py`, `aos trace/waits/effects/quarantine` |
| 21 | quarantine poison work, explicit replay | `quarantine.py` (evidence bundle, `aos replay`, poison flag) |
| 22 | trace trajectories, judge the path | `trace.py` (`judge` flags orphaned effects / denied-path success), auto-compensation in `engine._maybe_compensate` |

## Execution fabric & scale
`worker.py` runs pull-based workers; the atomic claim makes many workers (threads
or separate processes on one DB) collaborate with zero double-execution. `aos web`
serves the same state read-only with a polled live event stream.

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
Shell/FS/git/SQLite: native. **Claude Code skills**: discovered, registered, and
run through the loop (`skills.py` + `skill` executor). Browser: working **seam**
(`SimBrowser` + evidence + skeptical QA; real Playwright drops in behind
`BrowserBackend`). Desktop/vision: deferred. Scheduling: file-driven recurring
sweep + durable timer waitpoints. Multi-machine: pull-workers on a shared DB
(atomic claim proven across processes).

## Momentum (never finish empty-handed)
`queues.md` (now/next/blocked/improve/recurring) + `aos recurring` self-driving
sweep (portfolio scan → proactive proposals + failure→eval + optional tune +
queued intel experiments). Every milestone left a reusable ratchet (skill/profile/
harness/eval/dashboard/policy/memory).

## Command reference (30 commands, all checked against the parser)
`ask · goal · run · status · rollup · dash · metrics · eval · improve [--tune] ·
config · approvals · recurring [--tune] · intel [--add|--fetch] · web · effects ·
trace · skills [--discover] · skill <name> [--run] · quarantine · replay · signal ·
waits · worker · profiles · harness {coding,report,browser} · queues · selftest`

## Where to look first
`OPERATING_SUMMARY.md` (the compact contract) → `aos selftest` (the loop, live) →
`evals/__init__.py` (what "working" means, executably) → `ROADMAP.md` (M1–M7 + next).
