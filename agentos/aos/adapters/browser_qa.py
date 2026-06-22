"""Skeptical QA evaluator for browser flows.

Builders systematically overestimate completeness, so the thing that *certifies* a
browser flow must be separate from the thing that *drove* it. This evaluator is
deliberately skeptical: it certifies success only on positive evidence and fails
closed on anything missing or ambiguous.

A goal assertion:
  {
    "final_url":     "https://x/home",      # optional: must be the final URL
    "must_contain":  ["Welcome"],            # all required in the final observation
    "must_not_contain": ["error", "rejected"]
  }
Returns (passed, report).
"""
from __future__ import annotations


def evaluate(goal: dict, session) -> tuple[bool, dict]:
    if not session.steps:                       # no evidence → fail closed
        return False, {"reason": "no actions taken; nothing to certify"}

    final = session.final()
    text = final.get("text", "")
    findings = []

    want_url = goal.get("final_url")
    if want_url and final.get("url") != want_url:
        findings.append(f"final_url is {final.get('url')!r}, expected {want_url!r}")

    for needle in goal.get("must_contain", []):
        if needle not in text:
            findings.append(f"missing required text: {needle!r}")

    for bad in goal.get("must_not_contain", []):
        if bad in text:
            findings.append(f"forbidden text present: {bad!r}")

    # skeptic's default: require at least one positive must_contain assertion,
    # otherwise we cannot prove the flow achieved anything.
    if not goal.get("must_contain") and not want_url:
        findings.append("goal has no positive assertion; cannot certify success")

    passed = len(findings) == 0
    return passed, {"final_url": final.get("url"), "steps": len(session.steps),
                    "findings": findings}
