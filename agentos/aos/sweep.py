"""Recurring self-driving sweep — the momentum / proactive-operations loop.

Run on a schedule (or `aos recurring`), the sweep keeps the system compounding
even when no new user request arrives:
  1. portfolio scan  → emit proactive proposals for failed/blocked/idle work,
  2. failure loop     → improve.cycle materializes regression evals from recurring
                        failures (additive, never regresses the suite),
  3. (opt) tune loop  → improve.tune_config tries one bounded config change behind
                        the eval gate (kept only if strictly better).
Returns a digest. Never finishes empty-handed: it always reports what it found and
what it queued.
"""
from __future__ import annotations

from . import improve, mine, rollup
from .db import emit


def run(conn, tune=False) -> dict:
    port = rollup.portfolio_rollup(conn)
    proposals = list(port["attention"])
    # idle-but-active goals with no failures still deserve a nudge if they stalled
    for p in port["projects"]:
        if p["status"] == "active" and p["total"] and p["done"] < p["total"]:
            proposals.append(f"{p['id']} ({p['title']}): {p['done']}/{p['total']} done — drive remaining")
    for prop in proposals:
        emit(conn, "proactive.proposal", detail=prop)

    improved = improve.cycle(conn)               # failure → regression eval
    tuned = improve.tune_config(conn) if tune else None
    workflow_candidates = mine.mine(conn)        # repeated success → promotion proposal

    # external-intelligence experiments queued from ingested news (M7).
    intel_experiments = conn.execute(
        "SELECT COUNT(*) c FROM memory WHERE mtype='semantic' AND mkey LIKE 'intel.experiment:%'"
    ).fetchone()["c"]

    digest = {"proposals": proposals,
              "pending_approvals": port["pending_approvals"],
              "improve": improved.get("action"),
              "tune": (tuned or {}).get("action") if tune else "skipped",
              "intel_experiments": intel_experiments,
              "workflow_candidates": [c["recipe"] for c in workflow_candidates]}
    emit(conn, "recurring.sweep", proposals=len(proposals),
         improve=digest["improve"], tune=digest["tune"], intel_experiments=intel_experiments,
         workflow_candidates=len(workflow_candidates))
    return digest
