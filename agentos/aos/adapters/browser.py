"""Browser / computer-use adapter slot.

Browser automation is real infrastructure with its own reliability stack, not a
gimmick bolted onto a coding agent. This module defines the STABLE INTERFACE the
rest of the system depends on, plus a deterministic in-memory backend (`SimBrowser`)
so the reliability discipline is testable today without a live browser:

  - NAMED actions (navigate / click / type / extract) over one-off DOM scripts.
  - OBSERVE-BEFORE-ACT: every action captures the page state before and after.
  - EVIDENCE capture: before/after text "screenshots" written to disk per step.

A real backend (Playwright/CDP) drops in behind `BrowserBackend` without touching
the harness or QA evaluator. Until then SimBrowser models a tiny site as data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class BrowserBackend(Protocol):
    def navigate(self, url: str) -> dict: ...
    def observe(self) -> dict: ...
    def click(self, target: str) -> dict: ...
    def type_text(self, field: str, value: str) -> dict: ...


class SimBrowser:
    """Deterministic simulated browser over a `site` dict:

        site = {
          "https://x/login": {
              "text": "Login page",
              "links": {"home": "https://x/home"},   # label -> url
              "fields": {"user": "", "pass": ""},
              "submit": {"to": "https://x/home", "requires": {"user": "ada"}}
          }, ...
        }
    """

    def __init__(self, site: dict):
        self.site = site
        self.url = None
        self.values: dict = {}

    def _page(self) -> dict:
        return self.site.get(self.url, {"text": "404 not found", "links": {}, "fields": {}})

    def navigate(self, url: str) -> dict:
        self.url = url
        self.values = dict(self._page().get("fields", {}))
        return self.observe()

    def observe(self) -> dict:
        p = self._page()
        return {"url": self.url, "text": p.get("text", ""),
                "links": list(p.get("links", {})) + (["submit"] if "submit" in p else []),
                "fields": dict(self.values)}

    def click(self, target: str) -> dict:
        p = self._page()
        if target == "submit" and "submit" in p:
            sub = p["submit"]
            requires = sub.get("requires", {})
            if all(self.values.get(k) == v for k, v in requires.items()):
                return self.navigate(sub["to"])
            return {**self.observe(), "text": p.get("text", "") + " [submit rejected: bad input]"}
        if target in p.get("links", {}):
            return self.navigate(p["links"][target])
        return {**self.observe(), "text": p.get("text", "") + f" [no such target: {target}]"}

    def type_text(self, field: str, value: str) -> dict:
        self.values[field] = value
        return self.observe()


class BrowserSession:
    """Front for any backend. Enforces observe-before-act and records evidence."""

    def __init__(self, backend: BrowserBackend, evidence_dir: str | Path):
        self.b = backend
        self.dir = Path(evidence_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.steps: list[dict] = []

    def _screenshot(self, tag: str, obs: dict) -> str:
        f = self.dir / f"step_{len(self.steps):02d}_{tag}.txt"
        f.write_text(json.dumps(obs, indent=2))
        return str(f)

    def act(self, action: str, **kw) -> dict:
        before = self.b.observe()                      # observe BEFORE
        shot_before = self._screenshot("before", before)
        if action == "navigate":
            after = self.b.navigate(kw["url"])
        elif action == "click":
            after = self.b.click(kw["target"])
        elif action == "type":
            after = self.b.type_text(kw["field"], kw["value"])
        elif action == "observe":
            after = before
        else:
            after = {**before, "error": f"unknown action {action}"}
        shot_after = self._screenshot("after", after)
        self.steps.append({"action": action, "args": kw, "before": before,
                           "after": after, "evidence": [shot_before, shot_after]})
        return after

    def final(self) -> dict:
        return self.steps[-1]["after"] if self.steps else self.b.observe()
