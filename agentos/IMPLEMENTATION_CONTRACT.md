# Implementation Contract — AgentOS v1

## Mission
Build a durable, observable, self-improving agentic operating system that runs
the full loop (goal → tasks → execution → verification → memory → visibility →
learning) and can expand toward general computer work over time.

## Runtime profile
Harness-wrapper mode over a strong agent host (Claude Code). File-first state +
SQLite control-plane index. Python 3.11 stdlib only. Single machine, local-first;
hub-worker shape preserved for later scale-out.

## First milestone (M1) — Closed loop, verified
The system can, end-to-end and provably:
1. accept a goal,
2. decompose it into an explicit dependency-aware task graph,
3. atomically claim one eligible task (pull-based),
4. execute it with a typed deterministic executor,
5. verify it with a **separate** verifier (executor never self-certifies),
6. record episodic + semantic + procedural memory with evidence,
7. surface it to a human (`status`, `dash`, project pack files),
8. extract at least one learning (procedural trajectory / failure→guardrail).

DONE = `python -m aos selftest` passes and `python -m aos eval` is green, with
the project pack on disk reflecting reality and the DB mirroring it.

## Non-goals for v1 (explicitly deferred)
- Browser/desktop/vision automation (adapter slots reserved).
- Web dashboard (CLI dashboard only).
- Multi-machine orchestration (single machine).
- LLM-driven decomposition inside the harness (templates + explicit specs for v1;
  the host agent can author tasks directly via the API).
- Distributed queue / message bus (in-process pull queue backed by SQLite).

## Constraints
- Stdlib only. No network assumptions. Ephemeral container → git is durability.
- No LLM calls inside harness scripts (portability + determinism + speed).

## Safety posture
- Deterministic rails; risky executors (`shell`) gated by an allow/deny policy and
  always logged as events.
- Bounded autonomy: per-task attempt cap, 1 auto-retry then escalate, hard
  task-level timeout, budget counters.
- Deny-first for destructive shell patterns; approval queue for gated actions.
- Full audit trail in the `events` table + per-project `decisions.md`.

## Proof-of-progress metrics (tracked from day one)
tasks_completed, tasks_verified, retry_rate, intervention_rate, eval_pass_rate,
repeat-run stability (selftest is deterministic), memory_reuse, time/cost proxies
(tick count, wall time), % proactive vs reactive. Surfaced by `aos metrics`.

## Verification strategy
Each task declares a verification plan (`exit_code`, `file_exists`,
`file_contains`, `json_schema`, `command`). The verifier runs it independently of
the executor and records pass/fail + evidence. No task is `done` without a pass.

## Tradeoffs recorded
- **SQLite over Postgres:** simpler ops, strong enough for single-server; revisit
  at real concurrency. (Recommended default.)
- **In-process pull queue over a broker:** fewer moving parts; the claim is atomic
  via a single UPDATE…WHERE status='pending'. Broker is a later scale lever.
- **Templates over LLM decomposition (v1):** keeps the harness deterministic and
  testable; the loop mechanics are what M1 must prove, not planning IQ.
- **Files canonical, DB derived:** projects outlive the runtime; DB is rebuildable.
