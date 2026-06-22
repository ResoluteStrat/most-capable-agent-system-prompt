"""Universal ask surface — infer the mode, don't force the user to pick one.

`aos ask "<intent>"` classifies a natural-language request into a mode and routes
it. The classifier is deterministic and transparent (scored keyword signals, no
LLM) so the routing is auditable and testable. It SHOWS the chosen mode and why;
below a confidence margin it presents the top alternatives with a recommendation
instead of guessing — the "ask anything, see why" contract.

Modes:
  answer          - a question about system state → read from the control plane
  execute         - an imperative task → create a goal and drive it
  monitor         - watch/automate/recurring → proactive sweep
  harness:coding  - ship/fix/test code → recommend the coding harness
  harness:report  - report/summary/KPIs → run the report harness
  harness:browser - browse/login/navigate a site → recommend the browser harness
"""
from __future__ import annotations

import re

# mode -> (weight, signal) list. Phrase hits score 2, word hits score 1.
SIGNALS = {
    "answer": [("what", 1), ("why", 1), ("which", 1), ("how many", 2), ("show", 1),
               ("list", 1), ("status", 1), ("what's", 1), ("whats", 1), ("?", 1),
               ("how much", 2), ("are there", 2)],
    "execute": [("fix", 1), ("create", 1), ("build", 1), ("add", 1), ("write", 1),
                ("implement", 1), ("do ", 1), ("make", 1), ("draft", 1), ("set up", 2)],
    "monitor": [("monitor", 2), ("watch", 2), ("every day", 2), ("each ", 1),
                ("schedule", 2), ("recurring", 2), ("keep an eye", 2), ("alert", 1)],
    "harness:coding": [("ship", 2), ("pull request", 2), ("refactor", 2), ("the test", 2),
                       ("run tests", 2), ("code review", 2), ("deploy", 1)],
    "harness:report": [("report", 2), ("summary", 1), ("kpi", 2), ("weekly", 1),
                       ("dashboard report", 2), ("write a report", 2)],
    "harness:browser": [("browse to", 2), ("log in to", 2), ("navigate to", 2),
                        ("on the website", 2), ("fill in the", 2), ("open the site", 2),
                        ("the web page", 2)],
}

MARGIN = 2   # winner must beat runner-up by this to silent-route


def _match(sig: str, t: str) -> bool:
    """Word-boundary match for single words (so 'list' ≠ 'checklist'); substring
    for multiword phrases and punctuation signals."""
    if sig.isalpha():
        return re.search(rf"\b{re.escape(sig)}\b", t) is not None
    return sig in t


def classify(text: str) -> dict:
    t = text.lower()
    scores = {mode: 0 for mode in SIGNALS}
    hits: dict[str, list] = {mode: [] for mode in SIGNALS}
    for mode, sigs in SIGNALS.items():
        for sig, w in sigs:
            if _match(sig, t):
                scores[mode] += w
                hits[mode].append(sig)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top, top_score = ranked[0]
    runner, runner_score = ranked[1]
    # default to answer for a bare question mark; else execute as the safe default
    if top_score == 0:
        top = "answer" if "?" in t else "execute"
        confident = False
    else:
        confident = top_score - runner_score >= MARGIN or runner_score == 0
    return {"mode": top, "confident": confident, "scores": scores,
            "signals": hits[top],
            "alternatives": [m for m, s in ranked[1:3] if s > 0]}
