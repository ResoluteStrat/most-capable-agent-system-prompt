"""Coding & delivery harness — plan → change → test → review → gate.

A reliability-first state machine for shipping a code change. Deterministic and
stdlib-only: it operates on a real workspace directory, writes files, runs a real
test command, and runs a SEPARATE review pass (builder ≠ reviewer) before a final
ship gate. Every phase writes an artifact; the run is resumable from any phase.

ctx (a plain dict):
  workspace : Path to the working dir (created if absent)
  spec      : {
                "plan": "<one-line intent>",
                "files": {"relpath": "content", ...},   # the change
                "test_cmd": "python -m pytest -q",        # default: "true"
                "forbid": ["TODO", "FIXME"]               # review tokens
              }
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .. import policy
from .base import Harness, Phase

DEFAULT_FORBID = ["TODO", "FIXME", "XXX"]


def _ws(ctx) -> Path:
    return Path(ctx["workspace"])


# ---- phases ----------------------------------------------------------------
def _plan_run(ctx):
    plan = ctx["spec"].get("plan", "(no plan provided)")
    p = _ws(ctx) / "PLAN.md"
    p.write_text(f"# Delivery plan\n\n{plan}\n\nFiles:\n" +
                 "".join(f"- {f}\n" for f in ctx["spec"].get("files", {})))
    return {"ok": True, "output": "plan written", "artifacts": [str(p)]}


def _plan_verify(ctx, result):
    p = _ws(ctx) / "PLAN.md"
    return p.exists() and p.stat().st_size > 0, {"plan": str(p)}


def _change_run(ctx):
    written = []
    for rel, content in ctx["spec"].get("files", {}).items():
        target = _ws(ctx) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        written.append(str(target))
    return {"ok": True, "output": f"wrote {len(written)} file(s)", "artifacts": written}


def _change_verify(ctx, result):
    files = ctx["spec"].get("files", {})
    missing = [f for f in files if not (_ws(ctx) / f).exists()]
    return not missing, {"written": len(files), "missing": missing}


def _test_run(ctx):
    cmd = ctx["spec"].get("test_cmd", "true")
    try:
        proc = subprocess.run(cmd, shell=True, cwd=str(_ws(ctx)),
                              capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "test timeout", "artifacts": []}
    out = (proc.stdout or "") + (proc.stderr or "")
    (_ws(ctx) / "TEST_OUTPUT.txt").write_text(out)
    ctx["_test_rc"] = proc.returncode
    return {"ok": proc.returncode == 0, "output": f"rc={proc.returncode}\n{out[-2000:]}",
            "artifacts": [str(_ws(ctx) / "TEST_OUTPUT.txt")]}


def _test_verify(ctx, result):
    return ctx.get("_test_rc") == 0, {"test_rc": ctx.get("_test_rc")}


def _review_run(ctx):
    """Separate adversarial review of the CHANGED files: deny-first patterns +
    forbidden tokens. Builder never certifies its own change."""
    forbid = ctx["spec"].get("forbid", DEFAULT_FORBID)
    findings = []
    for rel, content in ctx["spec"].get("files", {}).items():
        allowed, reason = policy.check_shell(content)
        if not allowed:
            findings.append(f"{rel}: dangerous pattern ({reason})")
        for tok in forbid:
            if tok in content:
                findings.append(f"{rel}: contains forbidden token '{tok}'")
    report = _ws(ctx) / "REVIEW.md"
    report.write_text("# Review\n\n" + ("\n".join(f"- {x}" for x in findings)
                                        if findings else "- LGTM: no findings\n"))
    ctx["_review_findings"] = findings
    return {"ok": True, "output": f"{len(findings)} finding(s)", "artifacts": [str(report)]}


def _review_verify(ctx, result):
    findings = ctx.get("_review_findings", [])
    return len(findings) == 0, {"findings": findings}


def _gate_run(ctx):
    d = _ws(ctx) / "DELIVERABLE.md"
    d.write_text("# Ship gate: PASSED\n\nAll phases (plan, change, test, review) "
                 "completed and verified.\n")
    return {"ok": True, "output": "ship gate passed", "artifacts": [str(d)]}


def _gate_verify(ctx, result):
    return (_ws(ctx) / "DELIVERABLE.md").exists(), {"deliverable": str(_ws(ctx) / "DELIVERABLE.md")}


def build() -> Harness:
    return Harness("coding_delivery", [
        Phase("plan", _plan_run, _plan_verify),
        Phase("change", _change_run, _change_verify),
        Phase("test", _test_run, _test_verify),
        Phase("review", _review_run, _review_verify),
        Phase("gate", _gate_run, _gate_verify),
    ])
