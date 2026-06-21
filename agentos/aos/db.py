"""SQLite control-plane access. Stdlib only.

The DB is the coordination/index layer. Canonical project state is on disk in
markdown (see projectpack.py). Keep this module free of business logic — it is
connection management + tiny helpers (event log, JSON columns).
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # the agentos/ dir
STATE_DIR = ROOT / "state"
DB_PATH = STATE_DIR / "agentos.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def now() -> str:
    """UTC ISO-8601 timestamp, second precision, sortable."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    conn = connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    return conn


def emit(conn: sqlite3.Connection, kind: str, *, goal_id=None, task_id=None, **data) -> None:
    """Append to the audit/event log. Every meaningful action calls this."""
    conn.execute(
        "INSERT INTO events (ts, kind, goal_id, task_id, data) VALUES (?,?,?,?,?)",
        (now(), kind, goal_id, task_id, json.dumps(data, default=str)),
    )
    conn.commit()


def jloads(value, default):
    try:
        return json.loads(value) if value else default
    except (json.JSONDecodeError, TypeError):
        return default


def jdumps(value) -> str:
    return json.dumps(value, default=str)
