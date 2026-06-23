"""Claude Code skill adapter — let AgentOS ingest and use SKILL.md packages.

A Claude Code skill is a folder with a `SKILL.md` (YAML frontmatter: name +
description, then a markdown body of instructions) and optionally a `scripts/`
directory of bundled tools. This adapter lets AgentOS DISCOVER such packages,
REGISTER them as capabilities, and USE them through the normal task loop via the
`skill` executor:
  - action "guidance" (default): surface the skill's instructions as an artifact a
    worker (or an LLM) follows — deterministic and always safe.
  - action "run": execute a bundled `scripts/<name>` deterministically.

Frontmatter is parsed with the stdlib (no YAML dependency) — just the two fields
Claude Code requires.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .db import jdumps, jloads, now


@dataclass
class Skill:
    name: str
    description: str
    path: str
    body: str = ""
    scripts: list[str] = field(default_factory=list)


_BLOCK_SCALARS = {"|", "|-", "|+", ">", ">-", ">+"}


def _parse_frontmatter(text: str) -> tuple[str, str, str]:
    """Return (name, description, body). Tolerates a missing frontmatter block and
    YAML block scalars (`description: |-` followed by indented lines), which it
    folds into a single line."""
    body = text
    if not text.lstrip().startswith("---"):
        return "", "", body
    t = text.lstrip()
    end = t.find("\n---", 3)
    if end == -1:
        return "", "", body
    fm, body = t[3:end], t[end + 4:].lstrip("\n")

    lines = fm.split("\n")
    data: dict[str, str] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith((" ", "\t")):
            key, _, val = line.partition(":")
            key, val = key.strip().lower(), val.strip()
            if val in _BLOCK_SCALARS:                # YAML block scalar → gather indented lines
                block, i = [], i + 1
                while i < len(lines) and (lines[i].strip() == "" or lines[i][:1] in (" ", "\t")):
                    block.append(lines[i].strip())
                    i += 1
                data[key] = " ".join(b for b in block if b)
                continue
            data[key] = val.strip("\"'")
        i += 1
    return data.get("name", ""), data.get("description", ""), body


def load(skill_md: Path) -> Skill:
    skill_md = Path(skill_md).resolve()
    name, description, body = _parse_frontmatter(skill_md.read_text(errors="replace"))
    pkg = skill_md.parent
    name = name or pkg.name
    sdir = pkg / "scripts"
    scripts = sorted(p.name for p in sdir.glob("*") if p.is_file()) if sdir.is_dir() else []
    return Skill(name=name, description=description, path=str(pkg), body=body, scripts=scripts)


def discover(paths) -> list[Skill]:
    """Find SKILL.md packages under each path (a SKILL.md file, or a dir to walk)."""
    found, seen = [], set()
    for p in paths:
        p = Path(p)
        candidates = [p] if p.name == "SKILL.md" else sorted(p.rglob("SKILL.md"))
        for md in candidates:
            if md.is_file() and str(md) not in seen:
                seen.add(str(md))
                found.append(load(md))
    return found


def register(conn, skill: Skill) -> None:
    conn.execute(
        "INSERT INTO skills (name, description, path, scripts, ts) VALUES (?,?,?,?,?) "
        "ON CONFLICT(name) DO UPDATE SET description=excluded.description, path=excluded.path, "
        "scripts=excluded.scripts, ts=excluded.ts",
        (skill.name, skill.description, skill.path, jdumps(skill.scripts), now()))
    conn.commit()


def register_all(conn, paths) -> list[Skill]:
    skills = discover(paths)
    for s in skills:
        register(conn, s)
    return skills


def listing(conn) -> list[dict]:
    return [{"name": r["name"], "description": r["description"], "path": r["path"],
             "scripts": jloads(r["scripts"], [])}
            for r in conn.execute("SELECT * FROM skills ORDER BY name").fetchall()]


def resolve(conn, name) -> dict | None:
    r = conn.execute("SELECT * FROM skills WHERE name=?", (name,)).fetchone()
    return ({"name": r["name"], "description": r["description"], "path": r["path"],
             "scripts": jloads(r["scripts"], [])} if r else None)
