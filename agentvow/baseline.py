"""The project-native setup, as a careful newcomer would build it from files in the repository (no language model, no network lookup beyond the installs themselves).

Steps, in order: the zero-config ladder's own (`pip install .` with the detected test/dev extras, the requirements files from a fixed list); the `pip install` lines of the first
GitHub Actions job that runs pytest or unittest (plus its literal `env:` values, tox.ini deps, uv/poetry sync translated to pip, Makefile test targets); `pip install` lines in
Dockerfiles; other requirements files. Every line passes the recipe validator, at most 12 steps. The result is a recipe setup, installed with the same sandbox and size guards as any
recipe. Anything not understood (matrix expressions, secrets, services, shell tricks) is left out and noted, never guessed.

The workflow reader below is a deliberately small subset of YAML (jobs, steps, `run:` scalars and block scalars, `env:` mappings): the tool has no dependencies. It is tested against
PyYAML on real workflow files (tests/test_baseline.py and docs/EVIDENCE_PACK.md)."""
import configparser
import re
import shlex
import tomllib
from pathlib import Path

from . import envsetup, recipe as recipe_mod

MAX_SETUP = recipe_mod.MAX_STEPS
EXCLUDE_REQ = re.compile(r"doc|lint|format|typing|mypy|build|release|publish|windows|win32|benchmark|bench", re.I)
_SKIP_PIP = re.compile(r"^(pip|setuptools|wheel|build|virtualenv|tox|nox|coverage|codecov|pre-commit)([<>=!~\[].*)?$", re.I)
_ENVPFX = re.compile(r"^([A-Z][A-Z0-9_]*)=([A-Za-z0-9_./:,+-]*)\s+")
_RUNNER = re.compile(r"^(?:uv run|poetry run|pipenv run|pdm run|hatch run|python3? -m )\s*(?:--\S+\s+)*")
_SYNC = re.compile(r"^(uv sync|poetry install|pdm install|pipenv install|hatch env)\b")
_SHELL_SPLIT = re.compile(r"\s*(?:&&|;|\|\|)\s*")


# ---- a small reader for the part of GitHub Actions YAML this needs -------------------------------------------------------------------------------------------------------
def _ind(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return re.sub(r"\s+#.*$", "", v)


def _block(lines: list, i: int, key_indent: int, dash: bool = False):
    """lines after index i that are blank or indented deeper than key_indent (with dash=True also list items at the key's own indent, which YAML allows) -> (block, next index)."""
    j = i + 1
    while j < len(lines) and (not lines[j].strip() or _ind(lines[j]) > key_indent or (dash and _ind(lines[j]) == key_indent and lines[j].lstrip().startswith("-"))):
        j += 1
    return lines[i + 1:j], j


def _mapping(block: list) -> dict:
    out = {}
    for ln in block:
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*:\s*(.*)$", ln)
        if m and not ln.lstrip().startswith("#"):
            v = _unquote(m.group(2))
            if v != "" and not v.startswith(("{", "[", "|", ">")):
                out[m.group(1)] = v
    return out


def _scalar(lines: list, i: int, key_indent: int, rest: str):
    """value of a key whose text after the colon is `rest` (a scalar or a block-scalar header) -> (text, next index)."""
    r = rest.strip()
    if r[:1] in ("|", ">"):
        blk, j = _block(lines, i, key_indent)
        body = [b for b in blk]
        nz = [x for x in body if x.strip()]
        if not nz:
            return "", j
        d = min(_ind(x) for x in nz)
        text = [x[d:] if x.strip() else "" for x in body]
        return ("\n".join(text) if r[0] == "|" else " ".join(t for t in text if t)), j
    return _unquote(r), i + 1


def parse_workflow(text: str):
    """-> (top_env, [(job_name, job_env, [ {run, env} ... ])]). Raises ValueError for anything outside the subset (flow style, anchors, multi-document)."""
    if re.search(r"^---\s*$", text, re.M) and len(re.findall(r"^---\s*$", text, re.M)) > 1:
        raise ValueError("multi-document YAML")
    if re.search(r"(^|\s)[&*][A-Za-z_]", text) and re.search(r"^\s*[A-Za-z_-]+:\s*[&*]", text, re.M):
        raise ValueError("anchors or aliases")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]   # full-line comments (shell comments inside a run block are ignored later anyway)
    top_env, jobs = {}, []
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(env|jobs):\s*(.*)$", ln)
        if m and _ind(ln) == 0:
            blk, j = _block(lines, i, 0)
            if m.group(1) == "env":
                top_env = _mapping(blk)
            else:
                jobs = _parse_jobs(blk)
            i = j
            continue
        i += 1
    return top_env, jobs


def _parse_jobs(blk: list):
    nz = [x for x in blk if x.strip() and not x.lstrip().startswith("#")]
    if not nz:
        return []
    ji = _ind(nz[0])
    jobs, i = [], 0
    while i < len(blk):
        m = re.match(r"^([A-Za-z0-9_.-]+):\s*$", blk[i].strip()) if _ind(blk[i]) == ji else None
        if not m:
            i += 1
            continue
        body, j = _block(blk, i, ji)
        jobs.append((m.group(1),) + _parse_job(body))
        i = j
    return jobs


def _parse_job(body: list):
    nz = [x for x in body if x.strip() and not x.lstrip().startswith("#")]
    if not nz:
        return {}, []
    bi = _ind(nz[0])
    env, steps, i = {}, [], 0
    while i < len(body):
        ln = body[i]
        m = re.match(r"^(env|steps):\s*$", ln.strip()) if _ind(ln) == bi else None
        if not m:
            i += 1
            continue
        blk, j = _block(body, i, bi, dash=(m.group(1) == "steps"))
        if m.group(1) == "env":
            env = _mapping(blk)
        else:
            steps = _parse_steps(blk)
        i = j
    return env, steps


def _parse_steps(blk: list):
    nz = [x for x in blk if x.strip() and not x.lstrip().startswith("#")]
    if not nz:
        return []
    si = _ind(nz[0])
    items, cur = [], None
    for ln in blk:
        if _ind(ln) == si and ln.lstrip().startswith("- ") or (_ind(ln) == si and ln.strip() == "-"):
            cur = [" " * (si + 2) + ln.lstrip()[2:]] if ln.strip() != "-" else []
            items.append(cur)
        elif cur is not None:
            cur.append(ln)
    out = []
    for it in items:
        k = si + 2
        step, i = {"run": None, "env": {}}, 0
        while i < len(it):
            ln = it[i]
            m = re.match(r"^(run|env):\s*(.*)$", ln.strip()) if _ind(ln) == k else None
            if not m:
                i += 1
                continue
            if m.group(1) == "run":
                step["run"], i = _scalar(it, i, k, m.group(2))
            else:
                blk2, i = _block(it, i, k)
                step["env"] = _mapping(blk2)
        out.append(step)
    return out


# ---- translation of what the workflow runs ----------------------------------------------------------------------------------------------------------------------------
def _norm_test(ln: str):
    env = {}
    while (m := _ENVPFX.match(ln)):
        env[m.group(1)] = m.group(2)
        ln = ln[m.end():]
    cand = _RUNNER.sub("", ln).strip()
    cand = "python -m " + cand if re.match(r"^unittest\b", cand) else cand
    return (cand, env) if re.match(r"^(python3? -m )?(pytest|py\.test|unittest)\b", cand) else (None, {})


def _lines(run: str):
    for ln in re.sub(r"\\\n\s*", " ", run).splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            yield ln


def _pip_args(line: str):
    try:
        toks = shlex.split(line, comments=True)
    except ValueError:
        return None
    if toks[:2] in (["python", "-m"], ["python3", "-m"]):
        toks = toks[2:]
    if toks[:2] == ["uv", "pip"]:
        toks = toks[1:]
    return toks[2:] if toks[:2] == ["pip", "install"] else None


def _extras_from_pyproject(texts: dict) -> list:
    try:
        d = tomllib.loads((texts or {}).get("pyproject.toml", ""))
    except Exception:
        return []
    return sorted((d.get("project", {}).get("optional-dependencies") or {}).keys())


def _sync_to_pip(ln: str, texts: dict):
    try:
        toks = shlex.split(ln)
    except ValueError:
        return None
    extras, allx, i = [], False, 1
    while i < len(toks):
        t = toks[i]
        if t == "--all-extras":
            allx = True
        elif t in ("--extra", "--extras", "-E") and i + 1 < len(toks):
            extras += toks[i + 1].replace(",", " ").split()
            i += 1
        elif t.startswith("--extra="):
            extras += t.split("=", 1)[1].replace(",", " ").split()
        i += 1
    if allx:
        extras = _extras_from_pyproject(texts)
    extras = [e for e in dict.fromkeys(extras) if re.fullmatch(r"[A-Za-z0-9_.-]+", e)]
    return "pip install -e " + (shlex.quote(".[" + ",".join(extras) + "]") if extras else ".")


def _tox_test(texts: dict):
    cp = configparser.ConfigParser(interpolation=None)
    try:
        cp.read_string((texts or {}).get("tox.ini", ""))
    except configparser.Error:
        return [], None
    if not cp.has_section("testenv"):
        return [], None
    deps = []
    for ln in cp.get("testenv", "deps", fallback="").splitlines():
        ln = ln.strip()
        if ln and "{" not in ln and not ln.startswith("#"):
            try:
                deps.append("pip install " + " ".join(shlex.quote(a) for a in shlex.split(ln)))
            except ValueError:
                pass
    test = None
    for ln in cp.get("testenv", "commands", fallback="").splitlines():
        ln = re.sub(r"\{posargs[^}]*\}", "", ln.strip().lstrip("-")).strip()
        if re.match(r"^(python3? -m )?(pytest|py\.test)\b", ln) and "{" not in ln:
            test = ln
            break
    return deps, test


def _make_test(texts: dict, target: str):
    on = False
    for ln in (texts or {}).get("Makefile", "").splitlines():
        if re.match(r"^" + re.escape(target) + r"\s*:", ln):
            on = True
            continue
        if on:
            if ln and not ln.startswith(("\t", " ")):
                break
            c, e = _norm_test(ln.strip().lstrip("@-"))
            if c and not e and "$" not in c:
                return c
    return None


def ci_setup(workflows: dict, texts: dict):
    """-> (setup lines, env dict, notes) from the FIRST workflow job that runs pytest/unittest, or ([], {}, notes)."""
    notes = []
    for name, text in sorted(workflows.items()):
        try:
            top_env, jobs = parse_workflow(text)
        except ValueError as e:
            notes.append(f"{name}: workflow not read ({e})")
            continue
        for jname, job_env, steps in jobs:
            setup, test, env, unsupported = [], None, {}, []
            for src in (top_env, job_env):
                env.update({k: v for k, v in src.items() if "${{" not in v})
            for st in steps:
                if not st.get("run"):
                    continue
                for k, v in (st.get("env") or {}).items():
                    if "${{" not in v:
                        env.setdefault(k, v)
                for ln in _lines(str(st["run"])):
                    if "${{" in ln:
                        unsupported.append(ln[:60])
                        continue
                    args = _pip_args(ln)
                    if args is not None:
                        names = [a for a in args if not a.startswith("-")]
                        if names and all(_SKIP_PIP.match(n) for n in names):
                            continue
                        setup.append("pip install " + " ".join(shlex.quote(a) for a in args))
                        continue
                    cand, penv = _norm_test(ln)
                    if cand and test is None:
                        test = cand
                        for k, v in penv.items():
                            env.setdefault(k, v)
                    elif _SYNC.match(ln):
                        pip = _sync_to_pip(ln, texts)
                        if pip:
                            setup.append(pip)
                            notes.append(f"{name}:{jname}: `{ln[:40]}` translated to `{pip}` (lockfile not honoured, groups not installed)")
                        else:
                            unsupported.append(ln[:60])
                    elif test is None and re.match(r"^tox\b", ln):
                        tdeps, ttest = _tox_test(texts)
                        if ttest:
                            setup += tdeps
                            test = ttest
                            notes.append(f"{name}:{jname}: `{ln[:40]}` resolved from tox.ini")
                        else:
                            unsupported.append(ln[:60])
                    elif test is None and (m := re.match(r"^make\s+([A-Za-z0-9_.-]+)\s*$", ln)):
                        mt = _make_test(texts, m.group(1))
                        if mt:
                            test = mt
                            notes.append(f"{name}:{jname}: `{ln}` resolved from the Makefile")
                        else:
                            unsupported.append(ln[:60])
            if test is None:
                continue
            if unsupported:
                notes.append(f"{name}:{jname}: skipped {len(unsupported)} line(s) with expressions, e.g. {unsupported[0]!r}")
            return list(dict.fromkeys(setup)), {k: v for k, v in env.items() if k.isupper()}, notes
    notes.append("no workflow job with a pytest/unittest command")
    return [], {}, notes


def dockerfile_setup(text: str) -> list:
    out = []
    for ln in re.sub(r"\\\n\s*", " ", text).splitlines():
        ln = ln.strip()
        if not re.match(r"^RUN\s", ln, re.I):
            continue
        for part in _SHELL_SPLIT.split(ln[4:].strip()):
            if "$" in part or "`" in part:
                continue
            args = _pip_args(part.strip())
            if args is None:
                continue
            names = [a for a in args if not a.startswith("-")]
            if names and all(_SKIP_PIP.match(n) for n in names):
                continue
            out.append("pip install " + " ".join(shlex.quote(a) for a in args))
    return list(dict.fromkeys(out))


def other_requirements(repo: Path) -> list:
    have, found = set(envsetup.REQ_FILES), []
    for pat in ("requirements*.txt", "*-requirements.txt", "*_requirements.txt", "requirements/*.txt"):
        for f in sorted(repo.glob(pat)):
            rel = str(f.relative_to(repo))
            if f.is_file() and rel not in have and not EXCLUDE_REQ.search(f.name) and rel not in found:
                found.append(rel)
    return found


def _read(p: Path) -> str:
    try:
        return p.read_text(errors="replace")
    except OSError:
        return ""


def derive(repo: Path):
    """-> (setup lines, env dict, notes) for a checkout. Every setup line is accepted by the recipe validator; refused ones are dropped and noted."""
    repo = Path(repo)
    notes, setup, env = [], [], {}
    extras = envsetup.detect_extras(repo)
    if (repo / "pyproject.toml").exists() or (repo / "setup.py").exists():
        setup.append("pip install " + (".[" + ",".join(extras) + "]" if extras else "."))
    if envsetup.detect_groups(repo):
        notes.append("dependency groups present; not installed (outside the recipe vocabulary)")
    setup += [f"pip install -r {f}" for f in envsetup.REQ_FILES if (repo / f).exists()]
    wdir = repo / ".github" / "workflows"
    wf = {f.name: _read(f) for f in sorted(wdir.glob("*.y*ml"))} if wdir.is_dir() else {}
    texts = {n: _read(repo / n) for n in ("pyproject.toml", "tox.ini", "Makefile") if (repo / n).exists()}
    if wf:
        s2, e2, n2 = ci_setup(wf, texts)
        setup += s2
        env.update(e2)
        notes += n2
        if s2 or e2:
            notes.append(f"CI workflow supplied {len(s2)} setup line(s) and {len(e2)} env value(s)")
    docker = []
    for f in sorted(list(repo.glob("Dockerfile*")) + list(repo.glob("*/Dockerfile*")) + list(repo.glob("docker/*/Dockerfile*"))):
        if f.is_file():
            docker += dockerfile_setup(_read(f))
    docker = list(dict.fromkeys(docker))
    if docker:
        notes.append(f"Dockerfile(s) supplied {len(docker)} pip line(s)")
    setup += docker + [f"pip install -r {f}" for f in other_requirements(repo)]
    good = []
    for s in dict.fromkeys(setup):
        try:
            recipe_mod.parse({"schema": recipe_mod.SCHEMA, "setup": [s], "test": "python -m pytest -q", "env": {}})
            good.append(s)
        except recipe_mod.RecipeError as e:
            notes.append(f"setup line refused by the validator ({str(e)[:50]}): {s[:60]}")
    if len(good) > MAX_SETUP:
        notes.append(f"{len(good) - MAX_SETUP} setup line(s) beyond the {MAX_SETUP}-step limit left out (the last ones)")
    clean_env = {}
    for k, v in env.items():
        try:
            recipe_mod.parse({"schema": recipe_mod.SCHEMA, "setup": [], "test": "python -m pytest -q", "env": {k: v}})
            clean_env[k] = v
        except recipe_mod.RecipeError:
            pass
    return good[:MAX_SETUP], clean_env, notes


def prepare(repo: Path, venv: Path, home: Path, timeout: int = 300):
    """Build the project-native environment. -> (python path or None, recipe or None, notes, aborted reason or None). The caller owns (and deletes) venv and home."""
    setup, env, notes = derive(repo)
    rec = recipe_mod.parse({"schema": recipe_mod.SCHEMA, "setup": setup, "test": "python -m pytest -q", "env": env})
    py, n2, aborted = recipe_mod.build_env(repo, rec, venv, home, timeout=timeout)
    return py, rec, notes + n2, aborted
