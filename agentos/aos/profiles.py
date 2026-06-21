"""Loadable behavior profiles — data, not prompts baked into code.

A profile is a behavior pack (planner / executor / verifier / reviewer) loaded
from aos/profiles/*.json. Routing picks a profile for a task by matching the
task's executor `kind` first, then its `skill_tags`. Profiles are the seam where
model tier, allowed executors, verification standard, and escalation policy are
chosen per task instead of being hard-coded into one giant prompt.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parent / "profiles"
DEFAULT = "executor"


@lru_cache(maxsize=1)
def load_all() -> dict[str, dict]:
    profiles = {}
    for f in sorted(PROFILE_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        profiles[data["name"]] = data
    return profiles


def route_profile(kind: str, skill_tags=None) -> dict:
    """Pick the profile for a task. kind match wins; else best tag overlap."""
    profiles = load_all()
    tags = set(skill_tags or [])
    # 1) exact executor-kind ownership
    for p in profiles.values():
        if kind in p.get("handles_kinds", []):
            return p
    # 2) best skill-tag overlap
    best, best_score = None, 0
    for p in profiles.values():
        score = len(tags & set(p.get("handles_tags", [])))
        if score > best_score:
            best, best_score = p, score
    return best or profiles.get(DEFAULT, {"name": DEFAULT, "model_tier": "cheap"})


def names() -> list[str]:
    return list(load_all().keys())
