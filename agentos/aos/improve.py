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

import json
from pathlib import Path

from . import config, evals
from .db import ROOT, emit, jloads, now

GEN_DIR = Path(__file__).resolve().parent / "evals" / "generated"

# Re-entrancy guard (structural fix for a recurring footgun): improve.cycle and
# tune_config run the eval suite; if a case in that suite calls back into the
# improvement/sweep machinery, that nested call must NOT run another suite (which
# would recurse forever). While scoring is in progress this flag is set, and the
# nested cycle/tune_config short-circuit to a no-op. This protects the whole class
# regardless of whether a new case was remembered to be added to evals.META_CASES.
_in_scoring = False


def _score(conn):
    # score against the core suite (excludes meta-cases that re-enter improve/sweep)
    global _in_scoring
    _in_scoring = True
    try:
        results = evals.run_core_suite()
    finally:
        _in_scoring = False
    passed = sum(1 for _, p, _ in results if p)
    return passed, len(results)


def cycle(conn) -> dict:
    if _in_scoring:                              # nested inside a scoring run → no-op
        return {"action": "noop", "note": "skipped: nested inside eval scoring"}
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
    payload = jloads(cand["value"], None)
    fixture = GEN_DIR / f"regression_{kind}.json"
    marker = GEN_DIR / f"regression_{kind}.md"
    applied = not fixture.exists()
    if applied and isinstance(payload, dict) and "spec" in payload:
        # a REAL, replayable regression fixture — evals._generated_cases() turns
        # this into an executable case that locks in "this failure shape fails
        # closed and gets quarantined", not just a human-facing note. Verify it
        # actually passes before keeping it: a broken auto-generated case is
        # worse than none.
        fixture.write_text(json.dumps(payload, indent=2))
        evals.invalidate_generated_cache()
        verified, verify_detail = evals.verify_fixture(payload)
        if not verified:
            fixture.unlink(missing_ok=True)
            evals.invalidate_generated_cache()
            applied = False
            emit(conn, "improve.fixture_rejected", failure_kind=kind, detail=verify_detail)
        else:
            marker.write_text(
                f"# Regression guardrail: {kind}\n\n"
                f"Auto-registered by the self-improvement loop on {now()} after a\n"
                f"recurring failure.\n\nClaim: {payload.get('reason')}\n\n"
                f"Verified on materialization: {verify_detail}\n\n"
                f"Action: a replayable eval case now exists for this failure shape\n"
                f"(see regression_{kind}.json, loaded by evals._generated_cases()).\n")
    elif applied:
        # defensive fallback for a non-JSON legacy candidate — note only, no fixture
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
        fixture.unlink(missing_ok=True)
        evals.invalidate_generated_cache()

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


# A small library of bounded tuning hypotheses on the config surface. Each is a
# single-key change the loop is allowed to try. Code stays off-limits (ROADMAP M3).
TUNE_HYPOTHESES = [
    ("medium_trust_gate", 0.0),   # "be more autonomous on medium-risk work"
    ("medium_trust_gate", 0.9),   # "be more conservative"
]


def tune_config(conn) -> dict:
    """One bounded self-improvement cycle on config. Try ONE single-key change,
    re-measure the eval suite, keep iff strictly better, else revert. Equal score
    → revert (simpler/default wins). Fully logged. Honest: with a green suite the
    expected outcome is a logged rejection, which is exactly the safety property."""
    if _in_scoring:                              # nested inside a scoring run → no-op
        return {"action": "noop", "note": "skipped: nested inside eval scoring"}
    base_pass = _eval_pass_count()
    key, candidate = TUNE_HYPOTHESES[0]
    old = config.get(key)
    if old == candidate:                       # nothing to try; pick the other
        key, candidate = TUNE_HYPOTHESES[1]
        old = config.get(key)

    config.set(key, candidate); config.invalidate()
    after_pass = _eval_pass_count()
    kept = after_pass > base_pass              # STRICTLY better, else revert
    if not kept:
        config.set(key, old); config.invalidate()

    emit(conn, "improve.tune", key=key, candidate=candidate, old=old, kept=kept,
         baseline=base_pass, after=after_pass)
    report = ROOT / "state" / "improve_report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("a") as fh:
        fh.write(f"\n## {now()} — tune {key}\n"
                 f"- tried {key}={candidate} (was {old})\n"
                 f"- eval {base_pass} → {after_pass}; kept={kept} "
                 f"({'improvement' if kept else 'reverted — no regression allowed'})\n")
    return {"action": "tune_config", "key": key, "candidate": candidate,
            "old": old, "kept": kept, "baseline": base_pass, "after": after_pass,
            "note": "reverted: change was not strictly better" if not kept else "kept improvement"}


def _eval_pass_count() -> int:
    global _in_scoring
    _in_scoring = True
    try:
        return sum(1 for _, passed, _ in evals.run_core_suite() if passed)
    finally:
        _in_scoring = False
