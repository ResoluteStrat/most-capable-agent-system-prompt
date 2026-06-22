"""External-intelligence loop — turn outside signal into improvement work.

Don't just collect news; convert it. This module ingests structured intelligence
items (from `aos intel --add file.json`, or any upstream fetcher) and:
  - scores each by ARCHITECTURAL relevance using the prompt's selection rule —
    reward durable execution / checkpointing / typed contracts / memory / model
    routing / sandboxing / eval loops / approvals / traceability; penalize thin
    wrappers, chat shells, UI-only, and trend-demo noise,
  - stores it in the dedicated `external` memory layer (deduped by URL),
  - promotes high-signal items into experiment / eval candidates (the
    news-to-improvement pipeline), so the recurring sweep can act on them.

Deterministic + stdlib: no network here. A fetcher is a separate, swappable layer
that just hands this module a list of items.
"""
from __future__ import annotations

import re

from .db import emit, jdumps, jloads, now

# Architecture signals worth stealing (the include-rule). Substrings, lowercased.
ARCH_SIGNALS = [
    "durable execution", "checkpoint", "resumab", "state machine", "workflow",
    "typed", "schema", "contract", "memory", "retrieval", "model routing",
    "gateway", "sandbox", "eval", "validation", "approval", "trace",
    "observability", "provenance", "protocol", "human-in-the-loop",
]
# Noise (the exclude-rule): thin wrappers / chat shells / UI-only / hype.
NOISE = ["thin wrapper", "wrapper around", "chat shell", "chatbot", "ui-only",
         "no-code", "just a demo", "trend", "hype", "marketing"]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "item"


def score(item: dict) -> int:
    text = f"{item.get('claim','')} {item.get('category','')} {item.get('source','')}".lower()
    hits = sum(1 for s in ARCH_SIGNALS if s in text)
    noise = sum(1 for n in NOISE if n in text)
    return max(0, hits - 2 * noise)


def verdict(relevance: int) -> str:
    if relevance >= 3:
        return "test"      # worth a bounded experiment / eval candidate
    if relevance >= 1:
        return "watch"
    return "ignore"


def ingest(conn, items: list[dict]) -> dict:
    """Store items in the external memory layer (dedup by URL). Promote 'test'
    items into experiment candidates. Returns a summary."""
    added, updated, promoted = 0, 0, 0
    for item in items:
        url = item.get("url") or item.get("source", "") + ":" + _slug(item.get("claim", ""))
        rel = score(item)
        v = verdict(rel)
        record = {**item, "relevance": rel, "verdict": v, "status": "new"}
        existing = conn.execute(
            "SELECT id FROM memory WHERE mtype='external' AND mkey=?", (url,)).fetchone()
        if existing:
            conn.execute("UPDATE memory SET value=?, ts=? WHERE id=?",
                         (jdumps(record), now(), existing["id"]))
            updated += 1
        else:
            conn.execute(
                "INSERT INTO memory (ts,mtype,mkey,value,tags,provenance,confidence)"
                " VALUES (?,?,?,?,?,?,?)",
                (now(), "external", url, jdumps(record),
                 jdumps([item.get("category", "misc"), v]),
                 item.get("source", ""), min(1.0, rel / 6.0)))
            added += 1
        if v == "test":
            # news → improvement: register an experiment candidate (semantic memory)
            ekey = f"intel.experiment:{_slug(item.get('claim',''))}"
            if not conn.execute("SELECT id FROM memory WHERE mkey=?", (ekey,)).fetchone():
                conn.execute(
                    "INSERT INTO memory (ts,mtype,mkey,value,tags,provenance,confidence)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (now(), "semantic", ekey,
                     item.get("suggested_experiment",
                              f"Test locally: {item.get('claim','')[:120]} (relevance {rel})."),
                     jdumps(["experiment", "intel"]), url, 0.6))
                promoted += 1
    conn.commit()
    emit(conn, "intel.ingest", added=added, updated=updated, promoted=promoted)
    return {"added": added, "updated": updated, "promoted_experiments": promoted,
            "total": len(items)}


def digest(conn, top=10) -> dict:
    rows = conn.execute("SELECT value FROM memory WHERE mtype='external'").fetchall()
    items = [jloads(r["value"], {}) for r in rows]
    items.sort(key=lambda i: i.get("relevance", 0), reverse=True)
    by_verdict = {"test": [], "watch": [], "ignore": []}
    for i in items:
        by_verdict.setdefault(i.get("verdict", "ignore"), []).append(i)
    experiments = [jloads(r["value"], r["value"]) if False else r["mkey"]
                   for r in conn.execute(
                       "SELECT mkey FROM memory WHERE mtype='semantic' AND mkey LIKE 'intel.experiment:%'")]
    return {"total": len(items), "ranked": items[:top],
            "counts": {k: len(v) for k, v in by_verdict.items()},
            "experiments": experiments}
