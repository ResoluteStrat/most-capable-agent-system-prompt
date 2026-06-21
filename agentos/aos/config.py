"""Tunable config — a transparent, versioned surface the self-improvement loop is
allowed to touch (code stays off-limits until eval coverage is deeper).

Values live in state/config.json (project-overridable), merged over DEFAULTS.
Everything here is observable and revertable. `aos config` shows/sets it; the
improve loop tunes ONE key at a time behind the eval gate (improve.py).
"""
from __future__ import annotations

import json
from pathlib import Path

from .db import ROOT

CONFIG_PATH = ROOT / "state" / "config.json"

DEFAULTS = {
    "medium_trust_gate": 0.5,     # trust needed for a medium-risk task to auto-proceed
    "default_max_attempts": 2,    # auto-retry budget before escalate
    "high_risk_always_approve": True,
}

_cache: dict | None = None


def load() -> dict:
    global _cache
    if _cache is None:
        data = dict(DEFAULTS)
        if CONFIG_PATH.exists():
            try:
                data.update(json.loads(CONFIG_PATH.read_text()))
            except json.JSONDecodeError:
                pass
        _cache = data
    return _cache


def get(key, default=None):
    return load().get(key, DEFAULTS.get(key, default))


def set(key, value) -> None:
    data = load()
    data[key] = value
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    # persist only the non-default deltas so the file stays legible
    deltas = {k: v for k, v in data.items() if DEFAULTS.get(k) != v}
    CONFIG_PATH.write_text(json.dumps(deltas, indent=2))


def reset(key=None) -> None:
    """Reset one key (or all) to its default and invalidate the cache."""
    global _cache
    if key is None:
        if CONFIG_PATH.exists():
            CONFIG_PATH.unlink()
        _cache = None
        return
    data = load()
    data[key] = DEFAULTS.get(key)
    set(key, DEFAULTS.get(key))
    _cache = None


def invalidate() -> None:
    global _cache
    _cache = None
