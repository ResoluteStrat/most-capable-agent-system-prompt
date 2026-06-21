# AgentOS — a reference implementation of the "most capable agent" system

A small, **working, observable** agentic operating system that runs the full
closed loop the prompt in this repo describes:

```
goal → task graph → execution → verification → memory update → visibility → learning
```

It is built in **harness-wrapper mode** (the LLM runtime is a replaceable
execution engine) and is **file-first**: canonical project state lives in
markdown on disk; a SQLite control plane indexes and coordinates it. **Stdlib
Python only** — no third-party dependencies.

This is M1 of the [ROADMAP](ROADMAP.md): the loop proven end-to-end, not a broad
demo. A narrow-but-closed loop beats a wide-but-broken one.

## Quick start

```bash
cd agentos
python -m aos selftest      # prove the whole loop end-to-end (exit 0 = healthy)
python -m aos eval          # run the 6-case eval harness
python tests/test_loop.py   # same checks via the stdlib test runner
```

Then drive a real goal:

```bash
python -m aos goal "Draft an onboarding checklist" --mode ops
python -m aos run                    # execute + verify all eligible tasks
python -m aos status                 # human-readable state
python -m aos dash                   # metrics, goals, trust, recent events
python -m aos metrics                # proof-of-progress metrics (JSON)
cat projects/*onboarding*/status.md  # the file-first project pack
```

## What each piece does

| File | Role |
|---|---|
| `aos/engine.py` | The loop: goal intake, template decomposition, **atomic pull-claim**, execute, verify, memory, learning, metrics, goal rollup. |
| `aos/executors.py` | Typed deterministic actions: `noop/checkpoint`, `write_file`, `shell`, `python`, `gather`. Executors **act**; they never self-certify. |
| `aos/verify.py` | **Independent** verifier. Plans: `always`, `exec_ok`, `file_exists`, `file_contains`, `json_schema`, `command`. |
| `aos/memory.py` | Layered memory (episodic / semantic / **procedural** / preference). Procedural recipes are the compounding asset; trust scores per skill. |
| `aos/projectpack.py` | File-first project packs: `project/plan/tasks/status/knowledge/decisions/handoff.md` + `artifacts/`. Any agent can continue from the folder. |
| `aos/profiles/` + `aos/profiles.py` | Loadable behavior profiles (planner/executor/verifier/reviewer) as JSON; `route_profile()` picks one per task by kind then tags. |
| `aos/adapters/model.py` | Model-routing seam behind a stable `route()` — cheap by default, escalates to strong for high-risk. Vendor-neutral; cost flows into `runs`. |
| `aos/autonomy.py` | Trust- and risk-gated autonomy: low-risk auto, medium needs earned trust, high pauses for approval. |
| `aos/policy.py` | Deny-first shell guardrails. |
| `aos/config.py` | Transparent, versioned, tunable surface (`state/config.json` over defaults) the self-improvement loop is allowed to touch. |
| `aos/improve.py` | Bounded, safe, logged self-improvement: recurring failures → regression evals; **`tune_config`** runs a one-change keep/revert loop behind the eval gate (strictly-better-or-revert). |
| `aos/evals/` | 12 cases (capability / behavioral / regression / safety / structure / **adversarial** / **long-horizon**), each timed; `stability()` checks repeat-run determinism. |
| `aos/harness/` | Specialized **state-machine** harnesses. `base.py` is a generic resumable phase machine; `coding_delivery.py` is plan→change→test→review→gate (builder ≠ reviewer), resumable from any phase via a checkpoint. |
| `aos/db.py`, `aos/schema.sql` | SQLite (WAL) control plane: goals, tasks, events, runs, memory, evals, approvals, harness_runs. |
| `aos/cli.py` | The human control plane (`goal/run/status/dash/metrics/eval/improve/approvals/recurring/queues/selftest`). |

## Design bets (why it's shaped this way)

- **One strong agent + explicit task graph + separate verifier + durable memory +
  control plane.** No agent swarm. Parallelism/multi-agent is a later lever.
- **Verification is a separate concern.** The eval `verifier_independent` proves
  the verifier rejects an executor that *says* it succeeded but produced the
  wrong artifact. Nothing is `done` without an independent pass.
- **Files are canonical, the DB is derived.** Projects survive runtime swaps.
- **Deterministic harness, no LLM calls inside it.** The rails are testable and
  repeatable; open-ended reasoning is supplied by the host agent authoring task
  specs (pass explicit `tasks=` to `create_goal`).
- **Bounded autonomy:** atomic claim, 1 auto-retry then escalate, attempt cap,
  deny-first destructive shell, approval queue for high-risk work, full audit log.

## Extending it

- **New executor:** add a function to `aos/executors.py` and register it in
  `REGISTRY`. Add a verification type in `aos/verify.py` if needed.
- **Host agent as the planner:** instead of the template decomposer, call
  `engine.create_goal(conn, title, tasks=[{...typed task specs...}])` — this is
  the seam where an LLM (or a model-routing adapter, ROADMAP M2) plugs in.
- **New eval:** add a case to `aos/evals/__init__.py`. Failures auto-suggest eval
  candidates via the failure loop; `aos improve` materializes them.

See [OPERATING_SUMMARY.md](OPERATING_SUMMARY.md),
[IMPLEMENTATION_CONTRACT.md](IMPLEMENTATION_CONTRACT.md),
[CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md), and [ROADMAP.md](ROADMAP.md).
