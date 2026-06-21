"""Bounded self-improvement loop (safe, additive, fully logged).

One cycle:
  1. measure baseline (eval suite score),
  2. pick ONE improvement hypothesis (a recurring-failure eval candidate from
     semantic memory that has not yet been materialized),
  3. apply a SAFE additive change (register a regression marker so the failure is
     now tracked — never auto-edits engine code in v1),
  4. re-measure,
  5. keep iff score did not regress; equal score → keep the simpler state (the
     marker is cheap, so it stays), else revert,
  6. log the cycle to events + a report.

This is the *mechanism* of self-improvement on transparent rails. Code-editing
self-improvement is deferred until eval coverage is deep enough to protect it
(see ROADMAP M3).
"""
from __future__ import annotations

from pathlib import Path

from . import evals
from .db import ROOT, emit, now

GEN_DIR = Path(__file__).resolve().parent / "evals" / "generated"


def _score(conn):
    results = evals.run_suite(conn, suite="improve-probe")
    passed = sum(1 for _, p, _ in results if p)
    return passed, len(results)


def cycle(conn) -> dict:
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    base_pass, total = _score(conn)

    # pick one unmaterialized eval candidate
    cand = conn.execute(
        "SELECT * FROM memory WHERE mtype='semantic' AND mkey LIKE 'eval_candidate:%'"
        " ORDER BY id DESC LIMIT 1").fetchone()

    if not cand:
        emit(conn, "improve.noop", detail="no eval candidates; system stable")
        return {"action": "noop", "baseline": f"{base_pass}/{total}",
                "note": "no recurring failures to convert into evals"}

    kind = cand["mkey"].split(":", 1)[1]
    marker = GEN_DIR / f"regression_{kind}.md"
    applied = not marker.exists()
    if applied:
        marker.write_text(
            f"# Regression guardrail: {kind}\n\n"
            f"Auto-registered by the self-improvement loop on {now()} after a\n"
            f"recurring failure.\n\nClaim: {cand['value']}\n\n"
            f"Action: failures of kind=`{kind}` are now tracked as a regression\n"
            f"concern. Promote to an executable eval case in evals/__init__.py.\n")

    new_pass, _ = _score(conn)
    kept = new_pass >= base_pass  # additive marker must never regress the suite
    if not kept and applied:
        marker.unlink(missing_ok=True)

    emit(conn, "improve.cycle", failure_kind=kind, applied=applied, kept=kept,
         baseline=f"{base_pass}/{total}", after=f"{new_pass}/{total}")
    report = ROOT / "state" / "improve_report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("a") as fh:
        fh.write(f"\n## {now()} — {kind}\n"
                 f"- baseline {base_pass}/{total} → after {new_pass}/{total}\n"
                 f"- applied marker: {applied}; kept: {kept}\n")
    return {"action": "materialize_regression_eval", "kind": kind,
            "applied": applied, "kept": kept,
            "baseline": f"{base_pass}/{total}", "after": f"{new_pass}/{total}"}
