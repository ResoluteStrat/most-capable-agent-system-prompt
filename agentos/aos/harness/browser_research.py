"""Browser research harness — open → act → extract → qa.

Drives a browser flow on the SimBrowser backend with full evidence capture, then
certifies it with the SEPARATE skeptical QA evaluator (actor ≠ evaluator). Reuses
harness/base.py unchanged — the third harness on the same state machine.

ctx spec: {
  "site":    {url: {...}},                 # SimBrowser site model
  "start":   "https://x/login",
  "steps":   [{"action": "type", "field": "user", "value": "ada"},
              {"action": "click", "target": "submit"}],
  "extract": {"contains": "Welcome"},      # text expected in the final page
  "goal":    {"final_url": "https://x/home", "must_contain": ["Welcome"],
              "must_not_contain": ["rejected"]}
}
"""
from __future__ import annotations

from pathlib import Path

from ..adapters import browser, browser_qa
from .base import Harness, Phase


def _ws(ctx) -> Path:
    return Path(ctx["workspace"])


def _session(ctx) -> browser.BrowserSession:
    if "_session" not in ctx:
        backend = browser.SimBrowser(ctx["spec"]["site"])
        ctx["_session"] = browser.BrowserSession(backend, _ws(ctx) / "browser_evidence")
    return ctx["_session"]


def _open_run(ctx):
    s = _session(ctx)
    obs = s.act("navigate", url=ctx["spec"]["start"])
    return {"ok": bool(obs.get("url")), "output": f"opened {obs.get('url')}", "artifacts": []}


def _open_verify(ctx, result):
    return _session(ctx).final().get("url") == ctx["spec"]["start"], {}


def _act_run(ctx):
    s = _session(ctx)
    for step in ctx["spec"].get("steps", []):
        kw = {k: v for k, v in step.items() if k != "action"}
        s.act(step["action"], **kw)
    return {"ok": True, "output": f"{len(s.steps)} step(s)", "artifacts": []}


def _act_verify(ctx, result):
    # purely structural: actions ran and evidence exists; success is QA's call.
    return len(_session(ctx).steps) >= 1, {"steps": len(_session(ctx).steps)}


def _extract_run(ctx):
    final = _session(ctx).final()
    out = _ws(ctx) / "EXTRACT.md"
    out.write_text(f"# Extracted\n\nURL: {final.get('url')}\n\n{final.get('text','')}\n")
    ctx["_final_text"] = final.get("text", "")
    return {"ok": True, "output": "extracted final page", "artifacts": [str(out)]}


def _extract_verify(ctx, result):
    needle = ctx["spec"].get("extract", {}).get("contains")
    if not needle:
        return True, {"note": "no extract assertion"}
    return needle in ctx.get("_final_text", ""), {"needle": needle}


def _qa_run(ctx):
    passed, report = browser_qa.evaluate(ctx["spec"].get("goal", {}), _session(ctx))
    ctx["_qa"] = (passed, report)
    (_ws(ctx) / "QA.md").write_text(
        f"# Skeptical QA\n\npassed: {passed}\n\nfindings:\n" +
        ("".join(f"- {f}\n" for f in report.get("findings", [])) or "- none\n"))
    return {"ok": True, "output": f"qa passed={passed}", "artifacts": [str(_ws(ctx) / "QA.md")]}


def _qa_verify(ctx, result):
    passed, report = ctx.get("_qa", (False, {}))
    return passed, report


def build() -> Harness:
    return Harness("browser_research", [
        Phase("open", _open_run, _open_verify),
        Phase("act", _act_run, _act_verify),
        Phase("extract", _extract_run, _extract_verify),
        Phase("qa", _qa_run, _qa_verify),
    ])
