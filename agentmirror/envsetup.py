"""Zero-config environment for running a project's tests (CI/server use). Developers should pass their own venv with --python instead.

Fixed ladder, nothing clever: venv, `pip install -e .[test|tests|testing|dev]`, requirements files, pytest. Every step's failure is
recorded. Installs run under `sandbox-exec` (network allowed, writes limited to the venv, repo and temp) and under hard resource
guards, because installs execute third-party build code and can be huge: a live size watchdog, a free-disk floor, a timeout, no pip cache.
"""
import os
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

from . import runner

EXTRAS = ("test", "tests", "testing", "dev", "develop")
REQ_FILES = ("requirements.txt", "requirements-dev.txt", "requirements_dev.txt", "requirements-test.txt", "requirements_test.txt",
             "dev-requirements.txt", "test-requirements.txt", "tests/requirements.txt")
MAX_VENV = 700 * 1024**2
MIN_FREE = 2.5 * 1024**3


def dir_size(p: Path) -> int:
    total = 0
    for f in p.rglob("*"):
        try:
            if f.is_file() and not f.is_symlink():
                total += f.stat().st_size
        except OSError:
            pass
    return total


def detect_extras(repo: Path) -> list:
    pp = repo / "pyproject.toml"
    if not pp.exists():
        return []
    try:
        opt = tomllib.loads(pp.read_text()).get("project", {}).get("optional-dependencies", {})
    except Exception:
        return []
    return [e for e in EXTRAS if e in opt]


def detect_groups(repo: Path) -> list:
    """PEP 735 dependency groups that look like test/dev groups (installed with `pip install --group NAME`, pip >= 25.1)."""
    pp = repo / "pyproject.toml"
    try:
        groups = tomllib.loads(pp.read_text()).get("dependency-groups", {}) if pp.exists() else {}
    except Exception:
        return []
    return [g for g in EXTRAS if g in groups]


def default_python(repo: Path) -> str:
    """The project's own virtualenv if it has one in the usual places; otherwise the interpreter running AgentMirror."""
    for d in (".venv", "venv", "env"):
        py = repo / d / "bin" / "python"
        if py.exists():
            return str(py)
    return sys.executable


def _pip(venv: Path, repo: Path, home: Path, args: list, timeout: int, max_venv: int, min_free: float):
    venv, repo, home = Path(venv).resolve(), Path(repo).resolve(), Path(home).resolve()
    tmp = home / "tmp"   # pip unpacks wheels into TMPDIR; keep it inside the throwaway root so a killed install cannot leave GBs behind in /tmp
    tmp.mkdir(parents=True, exist_ok=True)
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "TMPDIR": str(tmp), "PIP_NO_CACHE_DIR": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    prof = runner.profile_with_network([venv, repo, home])
    proc = subprocess.Popen(["sandbox-exec", "-p", prof, str(venv / "bin/pip"), *args], cwd=repo, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, start_new_session=True)
    start = time.time()
    while proc.poll() is None:
        time.sleep(2)
        if time.time() - start > timeout:
            reason = "timeout"
        elif dir_size(venv) + dir_size(tmp) > max_venv:
            reason = "environment too heavy"
        elif shutil.disk_usage(venv).free < min_free:
            reason = "disk low"
        else:
            continue
        for kill in (lambda: os.killpg(proc.pid, 9), proc.kill):
            try:
                kill()
                break
            except (PermissionError, ProcessLookupError):
                continue
        subprocess.run(["pkill", "-9", "-f", str(venv / "bin/pip")], capture_output=True)  # the sandboxed child can outlive its parent
        proc.wait()
        return 125, reason
    return proc.returncode, proc.stdout.read()


def _project_name(repo: Path):
    try:
        return tomllib.loads((repo / "pyproject.toml").read_text()).get("project", {}).get("name")
    except Exception:
        return None


def _copy_project(repo: Path, dest: Path, limit: int = 500 * 1024**2) -> bool:
    """Install from a throwaway copy: the user's real repository is never written to, and no editable link points back at it."""
    total = 0
    for f in repo.rglob("*"):
        if ".git" in f.parts:
            continue
        try:
            total += f.lstat().st_size
        except OSError:
            pass
        if total > limit:
            return False
    ignore = shutil.ignore_patterns(".git", "node_modules", "__pycache__", ".venv", "venv", ".agentmirror", ".tox", ".mypy_cache", ".pytest_cache", "*.pyc")
    shutil.copytree(repo, dest, ignore=ignore, symlinks=True)
    return True


def build_env(repo: Path, venv: Path, home: Path, timeout: int = 300, max_venv: int = MAX_VENV, min_free: float = MIN_FREE):
    """-> (python path or None, notes, aborted_reason or None). The caller owns (and should delete) `venv` and `home`."""
    repo, venv, home = Path(repo).resolve(), Path(venv).resolve(), Path(home).resolve()  # sandbox write rules need absolute paths
    notes = []
    home.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(venv.parent if venv.parent.exists() else home).free < min_free:
        return None, ["free disk below floor; not starting"], "disk low"
    proj = home / "proj"
    if not proj.exists() and not _copy_project(repo, proj):
        return None, ["project too large to copy for installation"], "too large"
    if not (venv / "bin/python").exists():
        r = subprocess.run([sys.executable, "-m", "venv", str(venv)], capture_output=True, text=True)
        if r.returncode:
            return None, ["venv failed: " + (r.stdout + r.stderr)[-200:]], None
    extras = detect_extras(proj)
    steps = []
    if (proj / "pyproject.toml").exists() or (proj / "setup.py").exists():
        steps.append((["install", "-q", ".[" + ",".join(extras) + "]" if extras else "."], "project install"))
    for g in detect_groups(proj):
        steps.append((["install", "-q", "--group", g], f"dependency group {g}"))
    steps += [(["install", "-q", "-r", f], f) for f in REQ_FILES if (proj / f).exists()]
    steps.append((["install", "-q", "pytest"], "pytest"))
    for args, label in steps:
        rc, out = _pip(venv, proj, home, args, timeout, max_venv, min_free)
        if rc == 125:
            notes.append(f"{label}: {out}")
            return str(venv / "bin/python"), notes, out  # aborted by a resource guard
        if rc and label == "project install" and extras:
            notes.append("install with extras failed; retrying without")
            rc, out = _pip(venv, proj, home, ["install", "-q", "."], timeout, max_venv, min_free)
            if rc == 125:
                notes.append(f"project install: {out}")
                return str(venv / "bin/python"), notes, out
        if rc:
            notes.append(f"{label} failed: " + " ".join(str(out).split())[-140:])
    name = _project_name(proj)
    if name:  # keep the dependencies, drop the project itself: the tests must import the code from the worktree under test
        _pip(venv, proj, home, ["uninstall", "-y", name], 120, max_venv, min_free)
    return str(venv / "bin/python"), notes, None
