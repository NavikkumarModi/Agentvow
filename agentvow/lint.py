"""Run the linter an agent says is clean, on the files the change touched, and report what it says. The linter is an existing tool found on this machine's PATH (nothing is installed
or vendored here); it runs in the same sandbox as the tests, with the repository read-only and no network. A tool that is missing, a version that cannot be read, or an error is UNKNOWN.

A finding is the tool's own output on this machine, with the repository's own configuration: a different version of the tool may disagree, so the version is always reported."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import runner

# claim name -> (executable, arguments before the files). Static analysers/formatters only; flake8 plugins and project config run inside the sandbox.
TOOLS = {
    "ruff check": ("ruff", ["check", "--no-cache", "--output-format=concise"]),
    "ruff format": ("ruff", ["format", "--check", "--no-cache"]),
    "black": ("black", ["--check", "--quiet"]),
    "flake8": ("flake8", []),
}
MAX_FILES = 200
_OK = {"ruff check": (0,), "ruff format": (0,), "black": (0,), "flake8": (0,)}
_FINDINGS = {"ruff check": (1,), "ruff format": (1,), "black": (1,), "flake8": (1,)}


def run(repo: Path, tool: str, files: list, timeout: int = 120) -> dict:
    """-> {"status": clean|findings|error|unavailable, "version", "summary", "findings": int, "files": int}"""
    spec = TOOLS.get(tool)
    if spec is None:
        return {"status": "unavailable", "summary": f"Agentvow has no runner for '{tool}'.", "version": "", "findings": 0, "files": 0}
    exe = shutil.which(spec[0])
    if exe is None:
        return {"status": "unavailable", "summary": f"{spec[0]} is not installed here, so the claim could not be checked.", "version": "", "findings": 0, "files": 0}
    why = runner.sandbox_problem()
    if why:
        return {"status": "unavailable", "summary": f"no sandbox to run {spec[0]} in ({why})", "version": "", "findings": 0, "files": 0}
    real = Path(repo).resolve()
    keep = []
    for f in files[:MAX_FILES]:
        p = real / f
        if f.endswith(".py") and p.is_file() and not p.is_symlink() and not f.startswith("-"):
            keep.append(f)
    if not keep:
        return {"status": "unavailable", "summary": "no changed Python file to lint", "version": "", "findings": 0, "files": 0}
    scratch = Path(tempfile.mkdtemp(prefix="al", dir=runner.scratch_base())).resolve()
    try:
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(scratch), "TMPDIR": str(scratch), "XDG_CACHE_HOME": str(scratch), "RUFF_CACHE_DIR": str(scratch), "BLACK_CACHE_DIR": str(scratch),
               "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1"}

        def sandboxed(argv):   # the repository is read-only: only the scratch directory is writable
            return subprocess.run(runner.wrap(argv, scratch, scratch, env=env, readonly=[real]), cwd=real, env=env, capture_output=True, text=True, timeout=timeout)

        try:
            v = sandboxed([exe, "--version"])
            version = (v.stdout or v.stderr).strip().splitlines()[0][:60] if (v.stdout or v.stderr).strip() else ""
            p = sandboxed([exe, *spec[1], "--", *keep])
        except (OSError, subprocess.TimeoutExpired) as e:
            return {"status": "error", "summary": f"{spec[0]} could not run: {type(e).__name__}", "version": "", "findings": 0, "files": len(keep)}
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        lines = [x for x in out.splitlines() if x.strip()]
        if p.returncode in _OK[tool]:
            return {"status": "clean", "summary": out[:200], "version": version, "findings": 0, "files": len(keep)}
        if p.returncode in _FINDINGS[tool]:
            n = len([x for x in lines if ":" in x and not x.startswith(("Found", "All checks", "warning", "would reformat"))]) or len(lines)
            return {"status": "findings", "summary": out[:600], "version": version, "findings": n, "files": len(keep), "lines": lines[:8]}
        return {"status": "error", "summary": f"{spec[0]} exited with {p.returncode}: {out[:200]}", "version": version, "findings": 0, "files": len(keep)}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
