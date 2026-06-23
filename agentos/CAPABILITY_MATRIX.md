# Runtime Capability Matrix

Adapt by **capability shape**, not product name. Status as observed in this
runtime (Claude Code on an ephemeral Linux container), 2026-06-21.

| Capability | Status | Notes / decision |
|---|---|---|
| Repo read | yes | Full filesystem read. |
| Repo write | yes | Edit/Write tools + shell. |
| Shell execution | yes | Bash tool. Used by `shell` executor (policy-gated). |
| Filesystem search | yes | Glob/Grep. |
| File editing | yes | Native. |
| Git | yes | Commit/push to `claude/agentic-os-build-e8zl1y`. |
| Network | partial | Governed by env network policy. Don't assume egress. |
| Package install | partial | Avoid — harness is **stdlib-only** by design (portability). |
| Local database | yes | SQLite via stdlib `sqlite3` (WAL). Control plane. |
| Browser control | seam | **Adapter shipped** (`aos/adapters/browser.py`) with a deterministic `SimBrowser` backend + evidence capture + skeptical QA. Real Playwright/CDP backend drops in behind `BrowserBackend` (ROADMAP M5). |
| Screenshot / vision | text | Evidence = before/after text snapshots per action. Real screenshots arrive with a real backend. |
| Desktop input | no | Deferred. |
| Tool calling | yes | Native to the host agent. |
| Claude Code skills | yes | `skills.py` + `skill` executor: discover/register a SKILL.md package and run it (guidance or bundled script) through the loop. |
| Sub-agent support | yes | `Agent` tool — used only when work is parallel/reviewer-split. |
| Long-running background | partial | Background bash + session re-wake. Not relied on for v1. |
| Cron / scheduled | no (native) | Emulated via `recurring.md` + `aos recurring` sweeps. |
| Webhook / event triggers | partial | GitHub PR webhooks via host; generic bus deferred. |
| Persistent storage | partial | Container is ephemeral → **git is the durability layer.** |
| UI / dashboard | text | CLI dashboard (`aos dash`). Web UI deferred (ROADMAP M6). |
| Secret management | n/a (v1) | No secrets stored by the harness yet. Encrypt-at-rest when added. |
| Approval / interruption | yes | Policy gate + approval queue in DB; human via CLI. |
| Multi-machine | no (v1) | Single-machine. Hub-worker shape preserved for later scale-out. |

## Gaps → decisions
- **Browser/desktop/vision:** deferred. Milestone is coding/ops/file-work first;
  computer-use is a clean adapter slot (`aos/adapters/` planned), not core.
- **Scheduling:** emulated through file-driven recurring sweeps rather than OS cron.
- **Durability:** the container is ephemeral, so *commit + push* is the persistence
  contract. The DB is rebuildable from the file packs (files are canonical).
- **LLM in the harness:** intentionally absent. The harness is deterministic rails;
  the host agent supplies open-ended reasoning by calling into it.
