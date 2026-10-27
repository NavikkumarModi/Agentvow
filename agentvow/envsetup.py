"""Zero-config environment for running a project's tests (CI/server use). Developers should pass their own venv with --python instead.

Fixed ladder, nothing clever: venv, `pip install -e .[test|tests|testing|dev]`, requirements files, pytest. Every step's failure is
recorded. Installs run under `sandbox-exec` (network allowed, writes limited to the venv, repo and temp) and under hard resource
guards, because installs execute third-party build code and can be huge: a live size watchdog, a free-disk floor, a timeout, no pip cache.
"""
import json
import os
import re
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
MAX_VENV = int(float(os.environ.get("AGENTVOW_MAX_ENV_MB") or 700) * 1024**2)   # disk guard for a replay environment; raise it for projects with heavy pinned dependencies
MIN_FREE = 2.5 * 1024**3
BUILD_BUDGET = int(float(os.environ.get("AGENTVOW_BUILD_BUDGET") or 900))   # overall seconds for all install steps of one environment (each step also has its own timeout)


# ---- the repository's own lock file ---------------------------------------------------------------------------------------------------------------------------------
# A reconstructed environment that ignores the lock drifts: a dependency released after the change was written can break it, and the dependencies of test groups the zero-config ladder does not
# know about are simply missing (found by the foamlib case and the detection study: most inconclusive replays were missing dependencies, and a third of those repositories ship a lock file).
# The lock is read as data (never executed); only registry packages with one locked version are used; a package name must look like a package name before it reaches pip's argument list.
LOCK_FILES = ("uv.lock", "poetry.lock", "pdm.lock", "Pipfile.lock")
MAX_PINS = 600
_PIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,80}==[A-Za-z0-9][A-Za-z0-9._!+-]{0,40}")
_FOREIGN = ("git", "path", "url", "editable", "directory", "virtual", "file", "develop", "source")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(repo: Path):
    """-> (pins ['name==version', ...], lock file name) or ([], None). The first lock file found in LOCK_FILES order."""
    repo = Path(repo)
    for name in LOCK_FILES:
        f = repo / name
        try:
            if not f.is_file() or f.stat().st_size > 20 * 1024**2:
                continue
            text = f.read_text(errors="replace")
        except OSError:
            continue
        versions: dict = {}
        try:
            if name == "Pipfile.lock":
                d = json.loads(text)
                for sect in ("default", "develop"):
                    for pkg, meta in (d.get(sect) or {}).items():
                        if isinstance(meta, dict) and not any(k in meta for k in _FOREIGN) and isinstance(meta.get("version"), str) and meta["version"].startswith("=="):
                            versions.setdefault(_norm(pkg), set()).add((pkg, meta["version"][2:]))
            else:
                for pkg in tomllib.loads(text).get("package", []):
                    if not isinstance(pkg, dict) or not isinstance(pkg.get("name"), str) or not isinstance(pkg.get("version"), str):
                        continue
                    src = pkg.get("source")
                    if name == "uv.lock" and not (isinstance(src, dict) and "registry" in src and len(src) == 1):
                        continue   # git, path, editable, virtual and directory sources are not published releases
                    if name != "uv.lock" and (src or any(k in pkg for k in _FOREIGN)):
                        continue
                    versions.setdefault(_norm(pkg["name"]), set()).add((pkg["name"], pkg["version"]))
        except (ValueError, tomllib.TOMLDecodeError, AttributeError, TypeError):
            continue
        pins = []
        for key, vs in sorted(versions.items()):
            if len({v for _, v in vs}) != 1:
                continue   # locked at several versions (one per Python version or platform): leave it to the resolver
            nm, ver = sorted(vs)[0]
            pin = f"{nm}=={ver}"
            if _PIN.fullmatch(pin):
                pins.append(pin)
        if pins:
            return pins[:MAX_PINS], name
    return [], None


def _install_pins(venv: Path, proj: Path, home: Path, pins: list, timeout: int, max_venv: int, min_free: float):
    """Install the pins with --no-deps from published wheels only (no source builds). -> (installed count, skipped list, guard reason or None). A batch that fails is retried one by one."""
    done, skipped = 0, []
    for i in range(0, len(pins), 40):
        batch = pins[i:i + 40]
        rc, out = _pip(venv, proj, home, ["install", "-q", "--no-deps", "--only-binary=:all:", *batch], timeout, max_venv, min_free)
        if rc == 125:
            return done, skipped, str(out)
        if rc == 0:
            done += len(batch)
            continue
        for pin in batch:
            rc, out = _pip(venv, proj, home, ["install", "-q", "--no-deps", "--only-binary=:all:", pin], timeout, max_venv, min_free)
            if rc == 125:
                return done, skipped, str(out)
            if rc == 0:
                done += 1
            else:
                skipped.append(pin.split("==")[0])
    return done, skipped, None


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
    """The project's own virtualenv if it has one in the usual places; otherwise the interpreter running Agentvow."""
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
    proc = subprocess.Popen(runner.wrap([str(venv / "bin/pip"), *args], repo, network=True, writable=[venv, repo, home], env=env), cwd=repo, env=env, stdout=subprocess.PIPE,
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


_DIRECT_URL_SNIPPET = (
    "import importlib.metadata as m, json, sys\n"
    "root = sys.argv[1]\n"
    "out = []\n"
    "for d in m.distributions():\n"
    "    t = d.read_text('direct_url.json')\n"
    "    if not t:\n"
    "        continue\n"
    "    try:\n"
    "        u = json.loads(t).get('url', '')\n"
    "    except ValueError:\n"
    "        continue\n"
    "    if u.startswith('file://') and u[7:].startswith(root):\n"
    "        out.append(d.metadata['Name'])\n"
    "print(json.dumps(sorted(set(out))))\n")


def installed_from(venv: Path, proj: Path) -> list:
    """Distributions installed in `venv` from a local path inside the throwaway project copy `proj` (the project itself AND any sub-packages of a monorepo)."""
    import json
    p = runner.probe(Path(venv) / "bin" / "python", _DIRECT_URL_SNIPPET, str(Path(proj).resolve()))
    try:
        return json.loads(p.stdout or "[]") if p.returncode == 0 else []
    except ValueError:
        return []


def uninstall_project_dists(venv: Path, proj: Path, home: Path, name, max_venv: int, min_free: float):
    """Keep the dependencies, drop the code under test: tests must import it from the worktree. Handles monorepos (several local distributions)."""
    names = set(installed_from(venv, proj))
    if name:
        names.add(name)
    if names:
        _pip(venv, proj, home, ["uninstall", "-y", *sorted(names)], 120, max_venv, min_free)


def _project_name(repo: Path):
    """The project's distribution name from pyproject ([project] or [tool.poetry]), setup.cfg or a literal `name=` in setup.py; None when none says."""
    repo = Path(repo)
    try:
        d = tomllib.loads((repo / "pyproject.toml").read_text())
        n = d.get("project", {}).get("name") or d.get("tool", {}).get("poetry", {}).get("name")
        if n:
            return n
    except Exception:
        pass
    try:
        import configparser
        cp = configparser.ConfigParser(interpolation=None)
        cp.read_string((repo / "setup.cfg").read_text())
        if cp.has_option("metadata", "name"):
            return cp.get("metadata", "name").strip()
    except Exception:
        pass
    try:
        m = re.search(r"""\bname\s*=\s*['"]([A-Za-z0-9][A-Za-z0-9._-]*)['"]""", (repo / "setup.py").read_text())
        if m:
            return m.group(1)
    except Exception:
        pass
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
    ignore = shutil.ignore_patterns(".git", "node_modules", "__pycache__", ".venv", "venv", ".agentvow", ".tox", ".mypy_cache", ".pytest_cache", "*.pyc")
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
        r = subprocess.run([sys.executable, "-I", "-m", "venv", str(venv)], capture_output=True, text=True)
        if r.returncode:
            return None, ["venv failed: " + (r.stdout + r.stderr)[-200:]], None
    constraints = None
    pins, lock_name = read_lock(proj) if os.environ.get("AGENTVOW_LOCK") == "1" else ([], None)   # opt in: measured on 12 repositories it moved 4 replays from a missing dependency to a test run, produced no verdict, and cost 5 to 100 times the time (docs/research/LOCK_FILE_EXPERIMENT.md)
    if pins:
        t0 = time.time()
        done, skipped, guard = _install_pins(venv, proj, home, pins, timeout, max_venv, min_free)
        if guard:   # the locked environment is too heavy or too slow: start again without it, as before
            notes.append(f"the pinned packages of {lock_name} could not be installed within the limits ({guard}); using the ladder without them")
            shutil.rmtree(venv, ignore_errors=True)
            r = subprocess.run([sys.executable, "-I", "-m", "venv", str(venv)], capture_output=True, text=True)
            if r.returncode:
                return None, ["venv failed: " + (r.stdout + r.stderr)[-200:]], None
        else:
            notes.append(f"installed {done} of {len(pins)} pinned package(s) from {lock_name}" + (f"; not installed: {', '.join(skipped[:6])}{', ...' if len(skipped) > 6 else ''}" if skipped else ""))
            constraints = home / "constraints.txt"
            constraints.write_text("\n".join(pins) + "\n")
    extras = detect_extras(proj)
    steps = []
    if (proj / "pyproject.toml").exists() or (proj / "setup.py").exists():
        steps.append((["install", "-q", ".[" + ",".join(extras) + "]" if extras else "."], "project install"))
    for g in detect_groups(proj):
        steps.append((["install", "-q", "--group", g], f"dependency group {g}"))
    steps += [(["install", "-q", "-r", f], f) for f in REQ_FILES if (proj / f).exists()]
    steps.append((["install", "-q", "pytest"], "pytest"))
    t_start = time.time()
    for args, label in steps:
        if time.time() - t_start > BUILD_BUDGET:
            notes.append(f"the install steps used more than the overall budget of {BUILD_BUDGET} s (AGENTVOW_BUILD_BUDGET); stopped before {label}")
            return str(venv / "bin/python"), notes, "timeout"
        use_c = bool(constraints) and args[:2] == ["install", "-q"] and "pytest" not in args[2:3]
        rc, out = _pip(venv, proj, home, [*args[:2], "-c", str(constraints), *args[2:]] if use_c else args, timeout, max_venv, min_free)
        if rc and use_c and rc != 125:   # the pins conflict with what this step wants: install it as the ladder always did
            notes.append(f"{label}: conflicts with the pins; installed without them")
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
    uninstall_project_dists(venv, proj, home, _project_name(proj), max_venv, min_free)   # keep the dependencies, drop the project (and monorepo sub-packages)
    return str(venv / "bin/python"), notes, None
