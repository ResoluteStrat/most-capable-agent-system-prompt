"""File-first project pack writer.

Canonical per-project state is on disk. Any compatible agent can enter the
folder, read these files, understand state, and continue. The DB mirrors/indexes
this; the files are the source of truth and are rebuildable-from / writable-to.

Pack: project.md, plan.md, tasks.md, status.md, knowledge.md, decisions.md,
handoff.md, artifacts/.
"""
from __future__ import annotations

import re
from pathlib import Path

from .db import ROOT, jloads

PROJECTS_DIR = ROOT / "projects"

STATUS_GLYPH = {
    "pending": "[ ]", "claimed": "[~]", "running": "[~]",
    "blocked": "[!]", "done": "[x]", "failed": "[F]",
}


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:48] or "goal"


def project_dir(goal_id: str, title: str) -> Path:
    d = PROJECTS_DIR / f"{goal_id}-{slug(title)}"
    (d / "artifacts").mkdir(parents=True, exist_ok=True)
    return d


def ensure_base_files(d: Path, goal):
    """Create the canonical files once if absent (append-only files preserved)."""
    if not (d / "project.md").exists():
        (d / "project.md").write_text(
            f"# {goal['title']}\n\n{goal['description']}\n\n"
            f"- id: {goal['id']}\n- mode: {goal['mode']}\n"
            f"- created: {goal['created_at']}\n")
    for name, header in [("knowledge.md", "# Knowledge"),
                         ("decisions.md", "# Decisions"),
                         ("plan.md", "# Plan")]:
        if not (d / name).exists():
            (d / name).write_text(header + "\n")


def render(conn, goal_id: str):
    """Re-render the live mirror files (tasks.md, status.md, handoff.md) from DB."""
    goal = conn.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
    if not goal:
        return None
    d = Path(goal["project_dir"])
    d.mkdir(parents=True, exist_ok=True)
    ensure_base_files(d, goal)
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE goal_id=? ORDER BY priority, created_at",
        (goal_id,)).fetchall()

    # tasks.md
    lines = [f"# Tasks — {goal['title']}", ""]
    for t in tasks:
        deps = jloads(t["depends_on"], [])
        dep_s = f" (deps: {', '.join(deps)})" if deps else ""
        lines.append(f"- {STATUS_GLYPH.get(t['status'],'[ ]')} `{t['id']}` "
                     f"{t['title']} — kind={t['kind']} status={t['status']}"
                     f" attempts={t['attempts']}/{t['max_attempts']}{dep_s}")
    (d / "tasks.md").write_text("\n".join(lines) + "\n")

    # status.md
    counts = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    done = counts.get("done", 0)
    total = len(tasks)
    s = [f"# Status — {goal['title']}", "",
         f"- goal status: **{goal['status']}**",
         f"- progress: {done}/{total} tasks done",
         f"- breakdown: {counts}", ""]
    (d / "status.md").write_text("\n".join(s) + "\n")

    # handoff.md — explicit next actions + blockers
    nexts = [t for t in tasks if t["status"] in ("pending", "blocked")]
    h = [f"# Handoff — {goal['title']}", "",
         "## Next actions"]
    if nexts:
        for t in nexts[:8]:
            h.append(f"- `{t['id']}` {t['title']} ({t['status']})")
    else:
        h.append("- (none — all tasks resolved)")
    failed = [t for t in tasks if t["status"] == "failed"]
    h += ["", "## Blockers / failures"]
    h += [f"- `{t['id']}` {t['title']}: {t['escalation'] or 'failed'}" for t in failed] or ["- (none)"]
    (d / "handoff.md").write_text("\n".join(h) + "\n")
    return d


def record_decision(d: Path, text: str, ts: str):
    with (d / "decisions.md").open("a") as fh:
        fh.write(f"\n- {ts}: {text}\n")
