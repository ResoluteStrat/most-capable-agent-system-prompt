# AgentOS — Operator Quickstart

A 5-minute tour. Everything is stdlib Python; run from `agentos/`.

```bash
python -m aos selftest      # prove the whole closed loop end-to-end (exit 0 = healthy)
python -m aos eval          # 45 eval cases — what "working" means, executably
python -m aos ask "draft an onboarding checklist"   # describe what you want
python -m aos web           # http://127.0.0.1:8787 — live dashboard (read-only)
```

## Every command (30), grouped by what it's for

### Do work
| Command | What it does |
|---|---|
| `ask "<intent>"` | Universal entry — infers answer/execute/skill/report and routes. |
| `goal "<title>"` | Intake a goal → decomposed into a verified task graph (a project pack). |
| `run [--goal ID]` | Drive eligible tasks to completion (claim → execute → verify). |
| `worker [--id W]` | Pull-based worker daemon — run several; zero double-execution. |
| `harness {coding,report,browser}` | Specialized resumable state machines (builder ≠ reviewer/QA). |

### See state (one state, many altitudes)
| Command | What it does |
|---|---|
| `status [--goal ID]` | Human-readable goal/task state. |
| `rollup [--goal\|--task ID]` | Altitude control: portfolio → project → task, with path verdicts. |
| `dash` | Metrics + goals + trust + recent events. |
| `metrics` / `costs` | Proof-of-progress metrics / cost by tier + expensive-goal hotspots. |
| `trace [--task\|--goal ID]` | Trajectory + path judge (flags dangerous paths, not just outcomes). |
| `web [--port]` | Read-only web control plane + live event stream. |

### Govern & recover
| Command | What it does |
|---|---|
| `approvals [--approve\|--deny ID]` | Trust/risk-gated approval queue. |
| `quarantine` / `replay <task>` | Dead-letter with evidence bundle / explicit replay. |
| `waits` / `signal <name>` | Durable waitpoints (timer/signal/approval) / deliver a signal. |
| `effects` | Idempotent effect ledger + sagas. |
| `config [--set\|--reset]` | The safe, tunable config surface. |

### Learn & grow capabilities
| Command | What it does |
|---|---|
| `recurring [--tune] [--auto-promote]` | Self-driving sweep: proposals + failure→eval + cost flags + workflow promotion. |
| `improve [--tune]` | One bounded self-improvement cycle (keep/revert behind the eval gate). |
| `intel [--add\|--fetch]` | External-intelligence loop (RSS/Atom/JSON → ranked experiments). |
| `workflows [--promote <recipe>]` | Mined repeated-success recipes → promote to a skill. |
| `skills [--discover PATH]` | Discover/list Claude Code SKILL.md packages. |
| `skill <name> [--run SCRIPT]` | Use a registered skill through the loop. |
| `skill-new <name>` | Scaffold + register a new SKILL.md package. |
| `profiles` | List behavior profiles + model routing. |

### Meta
`queues` (momentum queues) · `selftest` · `eval`

## What proves it (45 eval cases, all in `aos/evals/__init__.py`)
Each capability has an executable proof. A sampling:
- **the loop**: `closed_loop`, `verifier_independent` (verifier rejects a lying executor), `retry_bounds`, `dependency_order`.
- **safety/governance**: `safety_deny`, `autonomy_gates_high_risk`, `autonomy_trust_gate_medium`, `adversarial_input` (instructions-in-data stay inert).
- **harnesses**: `harness_resumes_after_failure`, `harness_review_blocks_bad_change`, `report_harness_schema_gate`, `browser_qa_rejects_failed_flow`.
- **reliability (rules 16–22)**: `effect_idempotency`, `saga_rolls_back_on_failure`, `retried_side_effect_applies_once`, `signal_waitpoint_resumes_across_processes`, `quarantine_captures_and_replay_recovers`, `trace_judges_the_path_not_just_outcome`, `failed_task_auto_compensates_side_effect`.
- **scale**: `two_workers_no_double_execution`.
- **self-improvement & capability growth**: `intel_ranks_and_promotes`, `workflow_mining_proposes_promotion`, `mined_workflow_promotes_to_usable_skill`, `auto_promotion_is_gated_then_fires`, `cost_breakdown_by_tier_and_hotspots`.
- **skills**: `claude_code_skill_ingested_and_used`, `skill_create_register_use`, `skill_run_side_effect_compensates`.

Run `python -m aos eval` to see them all pass with timings; the suite is repeat-run stable.

## The honest boundary
The harness is deterministic and LLM-free — it proves the *machinery* (intake → tasks → verify → memory → safety → learning). The slot where an LLM authors rich task content or follows skill guidance as open-ended reasoning is built and ready (`create_goal(tasks=...)`, the model-routing adapter), intentionally not wired into the core so it stays fast, testable, and trustworthy first.

See `OPERATING_SUMMARY.md`, `DESIGN.md`, and `ROADMAP.md` for depth.
