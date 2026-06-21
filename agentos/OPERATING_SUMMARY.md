# AgentOS — Operating Summary (read this first on every long run)

> Compact self-summary per the READER CONTRACT. If a long run drifts into
> chat-only behavior or premature multi-agent complexity, re-read this file
> and return to: files → tasks → execution → verification → memory → learning.

## What this is
A durable, observable, file-first **agentic operating system** that runs the
closed loop:

```
goal → task graph → execution → verification → memory update → visibility → learning
```

It is built in **harness-wrapper mode**: the LLM runtime (Claude Code, Codex,
any agent) is a *replaceable execution engine*. The source of truth is on disk:
markdown project packs + a SQLite control-plane index. Projects survive runtime
swaps and can be continued by any compatible agent from the folder alone.

## Default architecture (the non-negotiable bet)
- **One strong generalist engine** + an **explicit task graph** + a **separate
  verifier** + **durable file-first memory** + a **CLI control plane**.
- No swarm of chatty agents. Add parallelism/multi-agent only where it clearly
  beats simpler control flow, and only after the single-agent loop is reliable.
- Deterministic Python (stdlib only) for the harness. No LLM calls inside the
  harness machinery — the harness is the rails; the LLM is the open-ended worker
  that runs *on* the rails.

## State model (transparent, not hidden)
- **Canonical per-project state = markdown files** in `projects/<id>/`:
  `project.md, plan.md, tasks.md, status.md, knowledge.md, decisions.md,
  handoff.md, artifacts/`.
- **Coordination/index state = SQLite** (`state/agentos.db`, WAL): goals, tasks,
  events, runs, memory, evals. The DB *mirrors and indexes* the files; it does
  not replace them.

## First milestone (DONE = the loop runs end-to-end and is verified)
Accept a goal → decompose into a task graph → a worker claims an eligible task →
executes it with a typed deterministic executor → a **separate verifier** proves
it → record memory + evidence → make it visible (`status`, `dash`) → extract one
learning. Proven by `aos selftest` and the eval harness (`aos eval`).

## Key guardrails
- Nothing is "done" until the verifier runs and passes. Executor never
  self-certifies.
- Atomic task claiming (one worker, one task). Bounded retries (1 auto-retry,
  then escalate). Hard per-task attempt cap.
- Every task carries a Definition of Done + verification plan + evidence.
- Every phase writes a file/artifact (resumable, inspectable, debuggable).
- Side effects are typed; risky kinds (`shell`) are policy-gated and logged.
- Equal eval score → prefer the simpler system.

## Runtime constraints (current)
- Runtime: Claude Code (strong agent host). Shell/FS/git: yes. Browser/desktop:
  not wired yet (deferred, see ROADMAP). Network: policy-governed.
- Language: Python 3.11 stdlib only. No third-party deps.
- Ephemeral container: commit + push to persist.

## How to drive it
```
cd agentos
python -m aos selftest          # prove the closed loop end-to-end
python -m aos goal "..."        # intake a goal (creates a project pack)
python -m aos run               # drive all eligible tasks to completion
python -m aos status            # human-readable state
python -m aos dash              # live dashboard (queues, events, costs)
python -m aos eval              # run the eval harness
python -m aos improve           # one bounded self-improvement cycle
python -m aos queues            # now / next / blocked / improve / recurring
```

## Never finish empty-handed
Every substantial run leaves: updated state, visible evidence, ≥1 reusable
artifact, an explicit next step, and ≥1 queued improvement. See `queues.md`.
