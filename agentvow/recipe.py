"""Claims with preconditions: an agent-declared *recipe* for the test run its claim relies on, replayed independently.

An agent that says "all tests pass" is true only under conditions its own environment satisfies and the reader cannot see (installed packages,
environment variables, a pinned Python). The agent therefore declares those conditions in a small JSON file; Agentvow builds a clean environment
from the declared steps ONLY (nothing is added on the agent's behalf) and runs the declared test command at the base and head commits.
If the replay cannot reproduce the result, the declaration was insufficient: that is itself the finding.

The agent PROPOSES; deterministic, sandboxed execution DECIDES. Recipes are untrusted input: only a narrow, validated subset is executable
(pip installs of names/requirement files inside the repository; a pytest/unittest command; plain environment variables), never a shell line.
"""
import hashlib
import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from . import envsetup

SCHEMA = "agentvow-recipe/1"
KEYS = {"schema", "python", "setup", "prepare", "test", "env", "notes"}
MAX_STEPS, MAX_ARG = 12, 300
_BAD_CHARS = re.compile(r"[;&|`$\\\n\r\"'(){}?!]")              # no shell syntax (nothing is ever run through a shell; <,>,* stay legal in version specifiers)
_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH", re.I)
_BLOCKED_ENV = {"PATH", "HOME", "TMPDIR", "TEMP", "TMP", "USER", "SHELL", "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE",
                "PYTHONINSPECT", "PYTHONBREAKPOINT", "PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_CONFIG_FILE", "PIP_TARGET", "PIP_USER",
                "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "GIT_DIR", "GIT_CONFIG", "VIRTUAL_ENV"}
_PIP_FORBIDDEN = {"-i", "--index-url", "--extra-index-url", "--trusted-host", "-f", "--find-links", "--target", "-t", "--prefix", "--root",
                  "--user", "--no-index", "--proxy", "--cert", "--client-cert", "--config-settings", "-C", "--global-option", "--install-option", "--pre"}
_PYTEST_FORBIDDEN = {"--rootdir", "-p", "--confcutdir", "--basetemp", "--import-mode", "--pyargs", "--cache-clear"}


class RecipeError(ValueError):
    pass


@dataclass
class Recipe:
    setup: list = field(default_factory=list)      # each: list of pip arguments after `pip install`
    local_roots: list = field(default_factory=list)   # set by build_env: repository sub-directories the recipe installs from (monorepo packages), added to PYTHONPATH at run time
    prepare: list = field(default_factory=list)    # each: argv after the interpreter, e.g. ["scripts/make_fixture.py"]; run in the sandbox before the tests
    test: list = field(default_factory=list)       # argv after the interpreter, e.g. ["-m", "pytest", "-q", "tests/test_x.py"]
    env: dict = field(default_factory=dict)
    python: str = ""
    notes: str = ""
    sha256: str = ""
    runner_supplied: str = ""   # set by build_env: the test runner (pytest) Agentvow installed because the recipe used it but did not declare it


def _rel_path_ok(s: str) -> bool:
    return bool(s) and not s.startswith(("/", "~", "-")) and ".." not in Path(s).parts and "://" not in s


def _check_tokens(tokens, what):
    for t in tokens:
        if len(t) > MAX_ARG or _BAD_CHARS.search(t):
            raise RecipeError(f"{what}: argument not allowed: {t[:40]!r}")


def _parse_setup(line: str):
    if not isinstance(line, str):
        raise RecipeError("setup entries must be strings")
    toks = shlex.split(line)
    if toks[:2] == ["python", "-m"] or toks[:2] == ["python3", "-m"]:
        toks = toks[2:]
    if toks[:2] != ["pip", "install"] or len(toks) < 3:
        raise RecipeError(f"setup step must be `pip install ...`: {line[:60]!r}")
    args = toks[2:]
    _check_tokens(args, "setup")
    it = iter(range(len(args)))
    i = 0
    out = []
    while i < len(args):
        a = args[i]
        if a in _PIP_FORBIDDEN or a.split("=", 1)[0] in _PIP_FORBIDDEN:
            raise RecipeError(f"setup: option not allowed: {a}")
        if a in ("-r", "--requirement", "-c", "--constraint"):
            if i + 1 >= len(args) or not _rel_path_ok(args[i + 1]):
                raise RecipeError(f"setup: {a} needs a relative path inside the repository")
            out += [a, args[i + 1]]
            i += 2
            continue
        if a in ("-e", "--editable"):
            if i + 1 >= len(args) or not (_rel_path_ok(args[i + 1]) or args[i + 1].startswith(".")):
                raise RecipeError("setup: -e needs a path inside the repository")
            tgt = args[i + 1]
            out += [tgt if tgt.startswith(".") else "./" + tgt]   # a PATH, never a PyPI name (`-e jac` must not install the PyPI package "jac"); installed non-editable from a throwaway copy
            i += 2
            continue
        if a.startswith("-"):
            if a not in ("-q", "--quiet", "-U", "--upgrade", "--no-deps", "--no-build-isolation", "--no-cache-dir", "--only-binary=:all:"):
                raise RecipeError(f"setup: option not allowed: {a}")
            out.append(a)
        else:
            if "://" in a or a.startswith(("git+", "svn+", "hg+", "file:")) or "@" in a.split("[", 1)[0] and "==" not in a and ">=" not in a:
                raise RecipeError(f"setup: URL/VCS requirement not allowed: {a[:40]}")
            if a in (".",) or a.startswith(".[") or _rel_path_ok(a) and ("/" in a or a.endswith((".whl", ".tar.gz", ".txt"))):
                pass   # a path inside the repository
            elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._\-]*(\[[A-Za-z0-9._,\-]+\])?([<>=!~]=?[A-Za-z0-9.*+!\-]+(,[<>=!~]=?[A-Za-z0-9.*+!\-]+)*)?", a):
                raise RecipeError(f"setup: not a plain requirement: {a[:40]!r}")
            out.append(a)
        i += 1
    return out


def _parse_prepare(line: str):
    """`python scripts/x.py [plain args]`: a Python script INSIDE the repository, run before the tests (e.g. to generate a fixture). Never a shell line."""
    if not isinstance(line, str):
        raise RecipeError("prepare entries must be strings")
    toks = shlex.split(line)
    _check_tokens(toks, "prepare")
    if toks[:1] not in (["python"], ["python3"]) or len(toks) < 2 or toks[1].startswith("-") or not toks[1].endswith(".py") or not _rel_path_ok(toks[1]):
        raise RecipeError(f"prepare step must be `python <script.py inside the repository> [args]`: {line[:60]!r}")
    for a in toks[2:]:
        if not re.fullmatch(r"[A-Za-z0-9_.=:/\-]{1,120}", a) or ".." in Path(a).parts or a.startswith("/"):
            raise RecipeError(f"prepare: argument not allowed: {a[:40]!r}")
    return toks[1:]


def _parse_test(line: str):
    if not isinstance(line, str) or not line.strip():
        raise RecipeError("test must be a non-empty string")
    toks = shlex.split(line)
    _check_tokens(toks, "test")
    if toks[:1] in (["pytest"], ["py.test"]):
        argv = ["-m", "pytest", *toks[1:]]
    elif toks[:1] in (["python"], ["python3"]) and toks[1:2] == ["-m"] and toks[2:3] in (["pytest"], ["unittest"]):
        argv = toks[1:]
    else:
        raise RecipeError("test must be `pytest ...`, `python -m pytest ...` or `python -m unittest ...`")
    prev = ""
    for a in argv[2:]:
        if argv[1] == "pytest" and a.split("=", 1)[0] in _PYTEST_FORBIDDEN:   # -p loads a plugin (code); for unittest -p is just a file pattern
            raise RecipeError(f"test: option not allowed: {a}")
        if a.startswith("-"):
            pass
        elif prev in ("-k", "-m", "--maxfail", "--tb", "-n", "--timeout", "-W", "--durations"):
            if not re.fullmatch(r"[A-Za-z0-9_ .:=\-]{1,120}", a):
                raise RecipeError(f"test: value not allowed for {prev}: {a[:40]!r}")
        elif not _rel_path_ok(a.split("::", 1)[0]) and not re.fullmatch(r"[A-Za-z0-9_.]+", a):
            raise RecipeError(f"test: argument must be a relative path inside the repository: {a[:40]!r}")
        prev = a
    return argv


def parse(data: dict) -> Recipe:
    if not isinstance(data, dict):
        raise RecipeError("recipe must be a JSON object")
    extra = set(data) - KEYS
    if extra:
        raise RecipeError(f"unknown keys: {sorted(extra)}")
    if data.get("schema", SCHEMA) != SCHEMA:
        raise RecipeError(f"unsupported schema {data.get('schema')!r}")
    setup = data.get("setup", [])
    if not isinstance(setup, list) or len(setup) > MAX_STEPS:
        raise RecipeError(f"setup must be a list of at most {MAX_STEPS} steps")
    env = data.get("env", {})
    if not isinstance(env, dict) or len(env) > 20:
        raise RecipeError("env must be an object with at most 20 entries")
    clean_env = {}
    for k, v in env.items():
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,60}", str(k)) or k in _BLOCKED_ENV or k.startswith(("LD_", "DYLD_", "PIP_", "GIT_", "PYTHON", "PYTEST_", "TOX_", "UV_", "POETRY_", "PDM_", "SETUPTOOLS_", "VIRTUALENV_", "CONDA_", "COVERAGE_", "NODE_OPTIONS")) or _SECRET_NAME.search(k):
            if k in ("HOME", "TMPDIR", "TEMP", "TMP"):
                raise RecipeError(f"env: {k} is not declared: the replay already runs the tests with an empty, writable HOME and TMPDIR of its own (a redirected {k} is usually only needed to work around a sandbox in the agent's own environment); remove it")
            raise RecipeError(f"env: name not allowed: {k!r} (plain NAME=value pairs only: not PATH, PYTHONPATH or other PYTHON*, PIP_*, GIT_*, pytest/tox/uv/poetry settings, or anything secret-looking; the project's own source folders are already importable)")
        if not isinstance(v, str) or len(v) > 200 or "\n" in v or "\x00" in v:
            raise RecipeError(f"env: value not allowed for {k}")
        clean_env[k] = v
    canon = json.dumps({k: data[k] for k in sorted(data)}, sort_keys=True).encode()
    prep = data.get("prepare", [])
    if not isinstance(prep, list) or len(prep) > 3:
        raise RecipeError("prepare must be a list of at most 3 steps")
    return Recipe(setup=[_parse_setup(s) for s in setup], prepare=[_parse_prepare(p) for p in prep], test=_parse_test(data.get("test", "")), env=clean_env,
                  python=str(data.get("python", ""))[:20], notes=str(data.get("notes", ""))[:500], sha256=hashlib.sha256(canon).hexdigest()[:16])


def load(path) -> Recipe:
    p = Path(path)
    if p.stat().st_size > 20_000:
        raise RecipeError("recipe file too large")
    try:
        return parse(json.loads(p.read_text(encoding="utf-8")))
    except json.JSONDecodeError as e:
        raise RecipeError(f"not valid JSON: {e}")


def _uses_pytest(recipe) -> bool:
    t = list(recipe.test)
    return "pytest" in t[:2] or (t[:1] == ["-m"] and t[1:2] == ["pytest"])


def build_env(repo: Path, recipe: Recipe, venv: Path, home: Path, timeout: int = 300):
    """Clean venv + ONLY the declared setup steps (sandboxed pip, size/disk guards from envsetup). -> (python path or None, notes, aborted)."""
    import subprocess, sys
    repo, venv, home = Path(repo).resolve(), Path(venv).resolve(), Path(home).resolve()
    home.mkdir(parents=True, exist_ok=True)
    proj = home / "proj"
    if not proj.exists() and not envsetup._copy_project(repo, proj):
        return None, ["project too large to copy for installation"], "too large"
    r = subprocess.run([sys.executable, "-I", "-m", "venv", str(venv)], capture_output=True, text=True)
    if r.returncode:
        return None, ["venv failed: " + (r.stdout + r.stderr)[-200:]], None
    notes = []
    own = envsetup._project_name(proj)
    if own:   # a setup step that installs a distribution with the PROJECT'S OWN name could shadow the code under test with someone else's package
        for args in recipe.setup:
            for a in args:
                if not a.startswith("-") and a != "." and not a.startswith(".") and "/" not in a and re.split(r"[\[<>=!~ ]", a, 1)[0].replace("_", "-").lower() == str(own).replace("_", "-").lower():
                    return None, [f"setup installs a package with the project's own name ({own}); refused"], "shadowing"
    for args in recipe.setup:
        rc, out = envsetup._pip(venv, proj, home, ["install", "-q", *args], timeout, envsetup.MAX_VENV, envsetup.MIN_FREE)
        if rc == 125:
            notes.append(f"setup `pip install {' '.join(args)}`: {out}")
            return str(venv / "bin/python"), notes, out
        if rc:
            notes.append(f"setup `pip install {' '.join(args)}` failed: " + " ".join(str(out).split())[-140:])
    for args in recipe.setup:   # directories INSIDE the repository that the recipe installs from (monorepo sub-packages): their sources must stay importable from each worktree
        for a in args:
            if not a.startswith("-") and a not in (".",) and not a.startswith("./.") and (proj / a.split("[", 1)[0]).is_dir() and ".." not in Path(a).parts:
                rel = a.split("[", 1)[0].strip("./") or "."
                if rel != "." and rel not in recipe.local_roots:
                    recipe.local_roots.append(rel)
    envsetup.uninstall_project_dists(venv, proj, home, envsetup._project_name(proj), envsetup.MAX_VENV, envsetup.MIN_FREE)   # the project and any monorepo sub-packages
    if _uses_pytest(recipe) and subprocess.run([str(venv / "bin/python"), "-I", "-c", "import pytest"], capture_output=True).returncode:
        # the declared command runs pytest but nothing declared installs it (typically preinstalled in the agent's own environment). Supply ONLY the runner, and say so.
        rc, out = envsetup._pip(venv, proj, home, ["install", "-q", "pytest"], timeout, envsetup.MAX_VENV, envsetup.MIN_FREE)
        if rc == 0:
            recipe.runner_supplied = "pytest"
            notes.append("the recipe's test command uses pytest but the recipe does not install it; Agentvow installed pytest (the runner only)")
        else:
            notes.append("the recipe's test command uses pytest, which the recipe does not install, and Agentvow could not install it: " + " ".join(str(out).split())[-100:])
    return str(venv / "bin/python"), notes, None
