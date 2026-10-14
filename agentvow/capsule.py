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


_SEG = re.compile(r"^\s*(?:\w+=\S*\s+)*(?:(?:uv|poetry|pipenv|pdm|hatch)\s+run\s+)?(?:\S*/)?(?:python[0-9.]*\s+-m\s+)?(?:pytest|py\.test|unittest|tox|nox)(?=$|\s)"
                  r"|^\s*(?:\w+=\S*\s+)*(?:\S*/)?python[0-9.]*\s+\S*manage\.py\s+test\b|^\s*make\s+(?:test|tests|check)\b")


def looks_like_test_command(cmd: str) -> bool:
    """Does a shell command line run a test suite? Each `;`, `&&`, `||`, `|` or newline separated segment is checked at its START (so `pip install pytest` is not a test run); text only,
    never executed. A false positive costs one extra capture."""
    return any(_SEG.search(seg) for seg in re.split(r"&&|\|\||;|\||\n", (cmd or "")[:2000]))


def _clean(x: str, n: int = 160) -> str:
    import unicodedata
    return " ".join("".join(ch for ch in str(x) if unicodedata.category(ch) not in ("Cc", "Cf") or ch == " ").split())[:n]


def capture(repo: Path, python: str | None = None, source: str = "stop", command: str = ""):
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
    files = {f: reality._file_hash(repo / f) if (repo / f).is_file() else None for f in reality.changed_files(repo, "HEAD")[:400]}   # what differed from HEAD when this was taken
    rec = {"schema": SCHEMA, "source": source, "command": _clean(command), "files": files,
           "commit": snap.commit, "tree": snap.tree, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "python_version": pv[0] if pv else "", "platform": pv[1] if len(pv) > 1 else "", "packages": keep, "dropped": dropped, "env_values_recorded": False}
    path = Path(".agentvow") / "capsules" / f"{snap.commit[:10]}_{(snap.tree or 'clean')[:8]}_{source}.json"
    reality.safe_write(repo, path, json.dumps(reality.sign_record(rec)))
    return rec, f"captured {len(keep)} package(s), Python {rec['python_version']}"


def _read(path: Path):
    try:
        if path.is_symlink() or not path.is_file():
            return None
        rec = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return rec if rec.get("schema") == SCHEMA and reality.verify_record(rec) else None


def history(repo: Path) -> list:
    """Every valid (signed) capsule recorded for the CURRENT commit, newest first. Forged or unsigned files are ignored."""
    repo = Path(repo).resolve()
    snap = reality.snapshot(repo)
    d = repo / ".agentvow" / "capsules"
    recs = [r for r in (_read(p) for p in sorted(d.glob(f"{snap.commit[:10]}_*.json"))) if r and r.get("commit") == snap.commit] if d.is_dir() else []
    return sorted(recs, key=lambda r: r.get("created_at", ""), reverse=True)


def load(repo: Path):
    """The capsule for the repository's CURRENT state (same commit and working-tree hash), or None. Unsigned, forged or stale capsules are ignored. When both a test-time and a stop-time
    capsule exist for the state, the one taken at the test run is preferred."""
    snap = reality.snapshot(Path(repo).resolve())
    match = [r for r in history(repo) if (r.get("tree") or "") == (snap.tree or "")]
    match.sort(key=lambda r: (r.get("source") != "post-test", r.get("created_at", "")))
    return match[0] if match else None


def timing(repo: Path, final: dict | None) -> dict:
    """How the capture relates to the agent's last test run. kind: 'same_state' (the last test-time capture is of the final state), 'edited_after' (files changed after it; they are
    listed, and so are packages added or removed since), 'stop_only' (no test-time capture exists: edits after the agent's last test run cannot be ruled out)."""
    repo = Path(repo).resolve()
    tests = [r for r in history(repo) if r.get("source") == "post-test"]
    if not tests:
        return {"kind": "stop_only", "text": "The environment was captured when the agent stopped, not at its last test run, so edits made after the agent last ran its tests cannot be ruled out."
                if final else "No environment was captured at a test run."}
    last = tests[0]
    snap = reality.snapshot(repo)
    when = last.get("created_at", "")
    cmd = _clean(last.get("command", ""), 80)
    if (last.get("tree") or "") == (snap.tree or ""):
        return {"kind": "same_state", "last_test_at": when, "command": cmd, "text": f"The last test run the agent made ({cmd or 'a test command'}, {when}) was on the final state: nothing was edited after it."}
    now = {f: reality._file_hash(repo / f) if (repo / f).is_file() else None for f in reality.changed_files(repo, "HEAD")[:400]}
    old = last.get("files") or {}
    edited = sorted(f for f in set(now) | set(old) if now.get(f) != old.get(f))
    add = rem = []
    if final and final is not last:
        a, b = set(last.get("packages", [])), set(final.get("packages", []))
        add, rem = sorted(b - a), sorted(a - b)
    text = (f"The last test run the agent made ({cmd or 'a test command'}, {when}) was on an earlier state: {len(edited)} file(s) were edited after it: " + (", ".join(_clean(f, 60) for f in edited[:6]) or "(state differs outside the listed files)")
            + ("; " + f"{len(add)} package(s) added and {len(rem)} removed after it" if add or rem else "") + ". The replay below is of the final state.")
    return {"kind": "edited_after", "last_test_at": when, "command": cmd, "edited": [_clean(f, 80) for f in edited[:20]], "packages_added": add[:10], "packages_removed": rem[:10], "text": text}


def to_recipe(cap: dict, test_argv: list):
    """-> (Recipe, extra files for the replay copy of the project). The setup is one pinned requirements file; nothing else is installed except the test runner if missing."""
    from .recipe import Recipe
    body = "\n".join(cap["packages"]) + "\n"
    sha = hashlib.sha256(json.dumps({k: cap[k] for k in ("commit", "tree", "packages", "python_version")}, sort_keys=True).encode()).hexdigest()
    rec = Recipe(setup=[["-r", REQS]], test=list(test_argv), env={}, sha256=sha)
    return rec, {REQS: body}
