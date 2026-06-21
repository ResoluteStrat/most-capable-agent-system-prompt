"""Typed, deterministic task executors.

An executor performs an ACTION. It does not certify success — that is the
verifier's separate job (verify.py). Each executor returns:
    {"ok": bool, "output": str, "artifacts": [relpath, ...]}
`ok` means "the action ran without an internal error", NOT "the task is done".

No LLM calls here. Executors are the deterministic rails the open-ended worker
runs on. Open-ended reasoning is supplied by the host agent authoring task specs.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import policy


class ExecResult(dict):
    @classmethod
    def make(cls, ok: bool, output: str = "", artifacts=None):
        return cls(ok=ok, output=output, artifacts=list(artifacts or []))


def _artifacts_dir(project_dir: Path) -> Path:
    d = project_dir / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def exec_noop(spec, project_dir):
    return ExecResult.make(True, output=spec.get("note", "checkpoint"))


def exec_write_file(spec, project_dir):
    rel = spec.get("path")
    if not rel:
        return ExecResult.make(False, "write_file: missing 'path'")
    content = spec.get("content", "")
    target = _artifacts_dir(project_dir) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return ExecResult.make(True, f"wrote {len(content)} bytes -> {target}",
                           artifacts=[str(target.relative_to(project_dir))])


def exec_shell(spec, project_dir):
    cmd = spec.get("cmd", "")
    allowed, reason = policy.check_shell(cmd)
    if not allowed:
        return ExecResult.make(False, reason)
    cwd = spec.get("cwd")
    workdir = (project_dir / cwd) if cwd else project_dir
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=str(workdir),
            capture_output=True, text=True, timeout=spec.get("timeout", 120),
        )
    except subprocess.TimeoutExpired:
        return ExecResult.make(False, "shell: timeout")
    out = (proc.stdout or "") + (proc.stderr or "")
    allowed_codes = spec.get("allowed_returncodes", [0])
    return ExecResult.make(proc.returncode in allowed_codes,
                           output=f"rc={proc.returncode}\n{out[-4000:]}")


def exec_python(spec, project_dir):
    code = spec.get("code", "")
    try:
        proc = subprocess.run(
            ["python3", "-c", code], cwd=str(project_dir),
            capture_output=True, text=True, timeout=spec.get("timeout", 120),
        )
    except subprocess.TimeoutExpired:
        return ExecResult.make(False, "python: timeout")
    out = (proc.stdout or "") + (proc.stderr or "")
    return ExecResult.make(proc.returncode == 0, output=f"rc={proc.returncode}\n{out[-4000:]}")


def exec_gather(spec, project_dir):
    """Append a fact/note to the project's knowledge file (research-mode-ish)."""
    note = spec.get("note", "")
    kf = project_dir / "knowledge.md"
    with kf.open("a") as fh:
        fh.write(f"\n- {note}\n")
    return ExecResult.make(True, f"recorded knowledge: {note[:80]}",
                           artifacts=["knowledge.md"])


REGISTRY = {
    "noop": exec_noop,
    "checkpoint": exec_noop,
    "write_file": exec_write_file,
    "shell": exec_shell,
    "python": exec_python,
    "gather": exec_gather,
}


def run_executor(kind: str, spec: dict, project_dir: Path) -> ExecResult:
    fn = REGISTRY.get(kind)
    if not fn:
        return ExecResult.make(False, f"unknown executor kind: {kind}")
    return fn(spec, project_dir)
