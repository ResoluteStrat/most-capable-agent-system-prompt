"""Independent verification layer.

Verification is a SEPARATE concern from execution. The same step must not both
produce and certify a result. The verifier runs the task's declared verification
plan against the post-execution world and returns (passed, evidence).

Verification plan kinds:
  {"type": "always"}                         -> trivially passes (checkpoints)
  {"type": "exec_ok"}                        -> the executor's own ok flag
  {"type": "file_exists", "path": "..."}     -> artifact present & non-empty
  {"type": "file_contains", "path": "...", "needle": "..."}
  {"type": "json_schema", "path": "...", "required": ["k1","k2"]}
  {"type": "command", "cmd": "...", "expect_rc": 0}
Paths are resolved relative to the project dir, then its artifacts/ subdir.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _resolve(project_dir: Path, rel: str) -> Path:
    p = project_dir / rel
    if p.exists():
        return p
    return project_dir / "artifacts" / rel


def verify(plan: dict, exec_result: dict, project_dir: Path) -> tuple[bool, dict]:
    vtype = plan.get("type", "exec_ok")
    ev: dict = {"type": vtype}

    if vtype == "always":
        return True, ev

    if vtype == "exec_ok":
        ok = bool(exec_result.get("ok"))
        ev["exec_ok"] = ok
        return ok, ev

    if vtype == "file_exists":
        p = _resolve(project_dir, plan["path"])
        ok = p.exists() and p.stat().st_size > 0
        ev.update(path=str(p), exists=p.exists(),
                  size=p.stat().st_size if p.exists() else 0)
        return ok, ev

    if vtype == "file_contains":
        p = _resolve(project_dir, plan["path"])
        if not p.exists():
            ev.update(path=str(p), exists=False)
            return False, ev
        text = p.read_text(errors="replace")
        ok = plan["needle"] in text
        ev.update(path=str(p), exists=True, found=ok, needle=plan["needle"])
        return ok, ev

    if vtype == "json_schema":
        p = _resolve(project_dir, plan["path"])
        if not p.exists():
            ev.update(path=str(p), exists=False)
            return False, ev
        try:
            obj = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            ev.update(path=str(p), valid_json=False, error=str(e))
            return False, ev
        missing = [k for k in plan.get("required", []) if k not in obj]
        ev.update(path=str(p), valid_json=True, missing=missing)
        return len(missing) == 0, ev

    if vtype == "command":
        try:
            proc = subprocess.run(plan["cmd"], shell=True, cwd=str(project_dir),
                                  capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            ev.update(timeout=True)
            return False, ev
        expect = plan.get("expect_rc", 0)
        ev.update(rc=proc.returncode, expect_rc=expect,
                  output=((proc.stdout or "") + (proc.stderr or ""))[-1000:])
        return proc.returncode == expect, ev

    ev["error"] = f"unknown verification type: {vtype}"
    return False, ev
