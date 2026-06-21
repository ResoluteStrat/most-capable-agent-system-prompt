"""Specialized harness library — state machines for repeated, high-value,
reliability-sensitive workflows.

A harness is the opposite of open-ended improvisation: explicit phases, entry/exit
criteria, an artifact written every stage, and resumability mid-run after a
failure or interruption. The generic engine (engine.py) handles ambiguous work;
harnesses handle workflows that must run the same way every time.

base.Harness is the reusable state machine; coding_delivery is the first concrete
harness (plan → change → test → review → gate).
"""
from .base import Harness, Phase  # noqa: F401
