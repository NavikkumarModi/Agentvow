"""Attempt-time capture: record the Python dependency state of the environment an agent worked in, at the moment it claims its tests pass, so that a later check can
replay the tests in a clean sandbox built from exactly those packages (a "capsule"). Motivated by the Stage B6 study (capturing the agent's installed packages
independently reproduced 91% of valid passing results against 55% for reconstruction from the repository).

Scope, stated plainly: Python packages (the `pip freeze` of one interpreter) plus the interpreter version. NOT system packages, services, generated files or secrets
(environment VALUES are never recorded). A capsule shows that a result is reproducible from the captured packages; it does not show the repository declares them,
and reproducibility is not correctness. The capsule is signed and bound to the exact commit and working-tree hash it was taken at."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import envsetup, reality, runner

SCHEMA = "agentvow-capsule/1"
REQS = ".agentvow-capsule-reqs.txt"


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def resolve_python(repo: Path, python: str | None = None):
    """The interpreter the agent most plausibly worked in: an explicit one, the project's own virtualenv, or the active VIRTUAL_ENV. Never Agentvow's own interpreter
    (capturing that would record the wrong environment). -> (path or None, reason when None)"""
    if python:
        return os.path.abspath(os.path.expanduser(python)), ""
    for d in (".venv", "venv", "env"):
        py = repo / d / "bin" / "python"
        if py.exists():
            return str(py), ""
    ve = os.environ.get("VIRTUAL_ENV")
    if ve and (Path(ve) / "bin" / "python").exists():
        return str(Path(ve) / "bin" / "python"), ""
    return None, "no project environment found (.venv, venv, env or an active VIRTUAL_ENV); pass --python"


def _run(argv: list, repo: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    scratch = Path(tempfile.mkdtemp(prefix="am", dir=runner.scratch_base()))
    try:
        return subprocess.run(runner.wrap(argv, repo, scratch=scratch, env=os.environ), cwd=str(repo), capture_output=True, text=True, timeout=timeout)
    finally:
        import shutil
        shutil.rmtree(scratch, ignore_errors=True)


def capture(repo: Path, python: str | None = None):
    """-> (capsule record or None, message). Writes .agentvow/capsules/<commit>_<tree>.json when it succeeds. The target interpreter is run inside the platform sandbox."""
    repo = Path(repo).resolve()
    py, why = resolve_python(repo, python)
    if not py:
        return None, why
    try:
        fr = _run([py, "-m", "pip", "freeze"], repo)
        ver = _run([py, "-c", "import sys,platform;print(sys.version.split()[0]);print(platform.system())"], repo)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"could not read the environment ({type(e).__name__})"
    if fr.returncode or ver.returncode:
        return None, "could not read the environment (pip freeze failed)"
    own = _norm(str(envsetup._project_name(repo) or ""))
    keep, dropped = [], {"editable": 0, "direct_url": 0, "own": ""}
    for line in fr.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-e"):
            dropped["editable"] += 1; continue
        if " @ " in line:
            dropped["direct_url"] += 1; continue
        name = re.split(r"[=<>!~ \[]", line, maxsplit=1)[0]
        if _norm(name) == "pip":
            continue
        if own and _norm(name) == own:
            dropped["own"] = name; continue
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?==[A-Za-z0-9._+!*-]+", line):
            continue   # only plain pins are replayed; anything else (markers, options, URLs) is dropped rather than executed
        keep.append(line)
    snap = reality.snapshot(repo)
    pv = ver.stdout.split()
    rec = {"schema": SCHEMA, "commit": snap.commit, "tree": snap.tree, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "python_version": pv[0] if pv else "", "platform": pv[1] if len(pv) > 1 else "", "packages": keep, "dropped": dropped, "env_values_recorded": False}
    path = Path(".agentvow") / "capsules" / f"{snap.commit[:10]}_{(snap.tree or 'clean')[:8]}.json"
    reality.safe_write(repo, path, json.dumps(reality.sign_record(rec)))
    return rec, f"captured {len(keep)} package(s), Python {rec['python_version']}"


def load(repo: Path):
    """The capsule for the repository's CURRENT state (same commit and working-tree hash), or None. Unsigned, forged or stale capsules are ignored."""
    repo = Path(repo).resolve()
    snap = reality.snapshot(repo)
    path = repo / ".agentvow" / "capsules" / f"{snap.commit[:10]}_{(snap.tree or 'clean')[:8]}.json"
    try:
        if path.is_symlink() or not path.is_file():
            return None
        rec = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if rec.get("schema") != SCHEMA or not reality.verify_record(rec) or rec.get("commit") != snap.commit or (rec.get("tree") or "") != (snap.tree or ""):
        return None
    return rec


def to_recipe(cap: dict, test_argv: list):
    """-> (Recipe, extra files for the replay copy of the project). The setup is one pinned requirements file; nothing else is installed except the test runner if missing."""
    from .recipe import Recipe
    body = "\n".join(cap["packages"]) + "\n"
    sha = hashlib.sha256(json.dumps({k: cap[k] for k in ("commit", "tree", "packages", "python_version")}, sort_keys=True).encode()).hexdigest()
    rec = Recipe(setup=[["-r", REQS]], test=list(test_argv), env={}, sha256=sha)
    return rec, {REQS: body}
