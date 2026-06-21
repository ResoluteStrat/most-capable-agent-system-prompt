"""Document/report harness — intake → validate → render → review.

Demonstrates two principles the prompt stresses:
  - SCHEMA-VALIDATED phase boundaries: the `validate` phase refuses to proceed
    unless the structured input carries every required field. Free-form text is
    too weak for high-reliability deliverables.
  - PROGRAMMATIC output: the report is generated deterministically from validated
    data via a template — the model never freestyles the final format.

Reuses harness/base.py unchanged, proving the state machine generalizes beyond
the coding harness.

ctx spec: {
  "data": {"title": ..., "period": ..., "metrics": {k: v}, "findings": [str]},
  "required": ["title", "period", "metrics"]   # schema for the validate gate
}
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import Harness, Phase

DEFAULT_REQUIRED = ["title", "period", "metrics"]


def _ws(ctx) -> Path:
    return Path(ctx["workspace"])


def _intake_run(ctx):
    p = _ws(ctx) / "INTAKE.json"
    p.write_text(json.dumps(ctx["spec"].get("data", {}), indent=2))
    return {"ok": True, "output": "intake stored", "artifacts": [str(p)]}


def _intake_verify(ctx, result):
    return (_ws(ctx) / "INTAKE.json").exists(), {}


def _validate_run(ctx):
    data = ctx["spec"].get("data", {})
    required = ctx["spec"].get("required", DEFAULT_REQUIRED)
    missing = [k for k in required if k not in data or data[k] in (None, "", {}, [])]
    ctx["_missing"] = missing
    (_ws(ctx) / "VALIDATION.json").write_text(json.dumps({"missing": missing}, indent=2))
    return {"ok": not missing, "output": f"missing={missing}", "artifacts": []}


def _validate_verify(ctx, result):
    """Schema boundary: refuse to render an incomplete report."""
    return len(ctx.get("_missing", [])) == 0, {"missing": ctx.get("_missing", [])}


def _render_run(ctx):
    d = ctx["spec"]["data"]
    lines = [f"# {d['title']}", "", f"Period: {d['period']}", "", "## Metrics", ""]
    for k, v in d["metrics"].items():
        lines.append(f"- **{k}**: {v}")
    findings = d.get("findings", [])
    lines += ["", "## Findings", ""]
    lines += [f"- {f}" for f in findings] or ["- (none)"]
    out = _ws(ctx) / "REPORT.md"
    out.write_text("\n".join(lines) + "\n")
    return {"ok": True, "output": "report rendered", "artifacts": [str(out)]}


def _render_verify(ctx, result):
    out = _ws(ctx) / "REPORT.md"
    if not out.exists():
        return False, {"exists": False}
    text = out.read_text()
    d = ctx["spec"]["data"]
    ok = d["title"] in text and "## Metrics" in text
    return ok, {"has_title": d["title"] in text}


def _review_run(ctx):
    text = (_ws(ctx) / "REPORT.md").read_text()
    issues = []
    if "{{" in text or "TODO" in text:
        issues.append("unfilled placeholder or TODO in output")
    for section in ("## Metrics", "## Findings"):
        if section not in text:
            issues.append(f"missing section {section}")
    ctx["_issues"] = issues
    (_ws(ctx) / "REVIEW.md").write_text("# Review\n\n" +
        ("\n".join(f"- {i}" for i in issues) if issues else "- LGTM\n"))
    return {"ok": True, "output": f"{len(issues)} issue(s)", "artifacts": []}


def _review_verify(ctx, result):
    return len(ctx.get("_issues", [])) == 0, {"issues": ctx.get("_issues", [])}


def build() -> Harness:
    return Harness("document_report", [
        Phase("intake", _intake_run, _intake_verify),
        Phase("validate", _validate_run, _validate_verify),
        Phase("render", _render_run, _render_verify),
        Phase("review", _review_run, _review_verify),
    ])
