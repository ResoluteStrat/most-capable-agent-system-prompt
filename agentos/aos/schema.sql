-- AgentOS control-plane schema (SQLite, WAL).
-- The DB is the coordination/index layer. Canonical per-project state lives in
-- markdown files under projects/<id>/. The DB is rebuildable from those files.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS goals (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    mode        TEXT NOT NULL DEFAULT 'general',   -- software/research/ops/...
    status      TEXT NOT NULL DEFAULT 'open',      -- open/active/done/failed
    project_dir TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id            TEXT PRIMARY KEY,
    goal_id       TEXT NOT NULL REFERENCES goals(id),
    title         TEXT NOT NULL,
    kind          TEXT NOT NULL,                   -- executor kind
    spec          TEXT NOT NULL DEFAULT '{}',      -- JSON: executor inputs
    skill_tags    TEXT NOT NULL DEFAULT '[]',      -- JSON list
    status        TEXT NOT NULL DEFAULT 'pending', -- pending/claimed/running/blocked/done/failed
    depends_on    TEXT NOT NULL DEFAULT '[]',      -- JSON list of task ids
    priority      INTEGER NOT NULL DEFAULT 5,
    risk          TEXT NOT NULL DEFAULT 'low',     -- low/medium/high
    budget_ticks  INTEGER NOT NULL DEFAULT 1,
    attempts      INTEGER NOT NULL DEFAULT 0,
    max_attempts  INTEGER NOT NULL DEFAULT 2,
    verification  TEXT NOT NULL DEFAULT '{}',      -- JSON: verification plan
    evidence      TEXT NOT NULL DEFAULT '{}',      -- JSON: verifier evidence
    artifacts     TEXT NOT NULL DEFAULT '[]',      -- JSON list of paths
    escalation    TEXT NOT NULL DEFAULT '',
    worker        TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_goal   ON tasks(goal_id);

CREATE TABLE IF NOT EXISTS events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    kind     TEXT NOT NULL,                        -- goal.created/task.claimed/...
    goal_id  TEXT,
    task_id  TEXT,
    data     TEXT NOT NULL DEFAULT '{}'            -- JSON
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

CREATE TABLE IF NOT EXISTS runs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id   TEXT NOT NULL,
    started   TEXT NOT NULL,
    finished  TEXT,
    ok        INTEGER,                             -- 1/0
    verified  INTEGER,                             -- 1/0
    output    TEXT NOT NULL DEFAULT '',
    cost_ticks INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS memory (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    mtype       TEXT NOT NULL,                     -- episodic/semantic/procedural/external/preference
    mkey        TEXT NOT NULL,
    value       TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '[]',        -- JSON list
    provenance  TEXT NOT NULL DEFAULT '',
    confidence  REAL NOT NULL DEFAULT 0.5,
    uses        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(mtype);
CREATE INDEX IF NOT EXISTS idx_memory_key  ON memory(mkey);

CREATE TABLE IF NOT EXISTS evals (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      TEXT NOT NULL,
    name    TEXT NOT NULL,
    suite   TEXT NOT NULL DEFAULT 'default',
    passed  INTEGER NOT NULL,                      -- 1/0
    detail  TEXT NOT NULL DEFAULT '',
    cost_ticks INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS approvals (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    task_id   TEXT NOT NULL,
    reason    TEXT NOT NULL,
    status    TEXT NOT NULL DEFAULT 'pending',     -- pending/approved/denied
    decided_at TEXT
);
