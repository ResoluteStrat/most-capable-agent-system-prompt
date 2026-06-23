---
name: hello-skill
description: A minimal sample Claude Code skill. Use when you want to verify AgentOS can discover, register, and run a SKILL.md package end to end.
---

# Hello Skill

This is a tiny example of a Claude Code skill that AgentOS can ingest.

## What it does
- Surfaces this guidance to the agent (the "guidance" action).
- Ships a bundled script under `scripts/` that AgentOS can run deterministically
  (the "run" action).

## Steps
1. Read this guidance.
2. Optionally run `scripts/greet.py "<name>"` to produce a greeting artifact.
3. Report the result.
