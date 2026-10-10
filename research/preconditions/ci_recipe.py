"""Derive a recipe from a repository's own GitHub Actions workflow (Stage B, stratum S2 reference environment; docs/research/forecast_grounding/STAGE_B.md).

Deterministic and conservative: only `pip install` lines, a pytest/unittest command and literal `env:` values are taken; anything else (matrix
expressions, secrets, services, shell tricks) is reported as unsupported and, if it is needed, the repository is simply not usable for S2.
The result always passes through the product's recipe validator."""
import re
import shlex
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
import sys  # noqa: E402
sys.path.insert(0, str(ROOT))
from agentvow import recipe as recipe_mod  # noqa: E402

_SKIP_PIP = re.compile(r"^(pip|setuptools|wheel|build|virtualenv|tox|nox|coverage|codecov|pre-commit)([<>=!~\[].*)?$", re.I)


_ENVPFX = re.compile(r"^([A-Z][A-Z0-9_]*)=([A-Za-z0-9_./:,+-]*)\s+")
_RUNNER = re.compile(r"^(?:uv run|poetry run|pipenv run|pdm run|hatch run|python3? -m )\s*(?:--\S+\s+)*")


def _norm_test(ln: str):
    """-> (test command or None, env dict) for a line that runs pytest/unittest, optionally behind literal NAME=value prefixes and a runner (uv run, poetry run...)."""
    env = {}
    while (m := _ENVPFX.match(ln)):
        env[m.group(1)] = m.group(2); ln = ln[m.end():]
    cand = _RUNNER.sub("", ln).strip()
    cand = "python -m " + cand if re.match(r"^unittest\b", cand) else cand
    return (cand, env) if re.match(r"^(python3? -m )?(pytest|py\.test|unittest)\b", cand) else (None, {})


def _lines(run: str):
    joined = re.sub(r"\\\n\s*", " ", run)
    for ln in joined.splitlines():
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
    if toks[:2] != ["pip", "install"]:
        return None
    return toks[2:]


_SYNC = re.compile(r"^(uv sync|poetry install|pdm install|pipenv install|hatch env)\b")


def _extras_from_pyproject(repo_texts: dict) -> list:
    try:
        import tomllib
        d = tomllib.loads((repo_texts or {}).get("pyproject.toml", ""))
    except Exception:
        return []
    return sorted((d.get("project", {}).get("optional-dependencies") or {}).keys())


def _sync_to_pip(ln: str, repo_texts: dict):
    """Translate an environment-sync command (uv/poetry/pdm/pipenv/hatch) to `pip install -e .[extras]`. The lockfile is NOT honoured
    (pip resolves afresh), which is recorded in the notes; dependency groups (PEP 735 / poetry groups) are not translated."""
    try:
        toks = shlex.split(ln)
    except ValueError:
        return None, "unparsable"
    extras, allx = [], False
    i = 1
    while i < len(toks):
        t = toks[i]
        if t == "--all-extras":
            allx = True
        elif t in ("--extra", "--extras", "-E") and i + 1 < len(toks):
            extras += toks[i + 1].replace(",", " ").split(); i += 1
        elif t.startswith("--extra="):
            extras += t.split("=", 1)[1].replace(",", " ").split()
        i += 1
    if allx:
        extras = _extras_from_pyproject(repo_texts)
    extras = [e for e in dict.fromkeys(extras) if re.fullmatch(r"[A-Za-z0-9_.-]+", e)]
    return "pip install -e " + (shlex.quote(".[" + ",".join(extras) + "]") if extras else "."), None


def _tox_test(repo_texts: dict):
    """-> (setup lines, pytest command) from the plain [testenv] of tox.ini; substitution expressions are not followed."""
    import configparser
    cp = configparser.ConfigParser(interpolation=None)
    try:
        cp.read_string((repo_texts or {}).get("tox.ini", ""))
    except configparser.Error:
        return [], None
    if not cp.has_section("testenv"):
        return [], None
    deps = []
    for ln in cp.get("testenv", "deps", fallback="").splitlines():
        ln = ln.strip()
        if not ln or "{" in ln or ln.startswith("#"):
            continue
        deps.append("pip install " + " ".join(shlex.quote(a) for a in shlex.split(ln)))
    test = None
    for ln in cp.get("testenv", "commands", fallback="").splitlines():
        ln = re.sub(r"\{posargs[^}]*\}", "", ln.strip().lstrip("-")).strip()
        if re.match(r"^(python3? -m )?(pytest|py\.test)\b", ln) and "{" not in ln:
            test = ln; break
    return deps, test


def _make_test(repo_texts: dict, target: str):
    lines = (repo_texts or {}).get("Makefile", "").splitlines()
    on = False
    for ln in lines:
        if re.match(r"^" + re.escape(target) + r"\s*:", ln):
            on = True; continue
        if on:
            if ln and not ln.startswith(("\t", " ")):
                break
            c, e = _norm_test(ln.strip().lstrip("@-"))
            if c and not e and "$" not in c:
                return c
    return None


def derive(workflow_texts: dict, repo_texts: dict | None = None):
    """-> (recipe dict or None, notes list). `workflow_texts`: {filename: yaml text}. `repo_texts`: optional {"pyproject.toml"|"tox.ini"|"Makefile": text}
    used to translate uv/poetry/pdm sync commands and `tox` / `make <target>` test commands. Picks the first workflow job that runs pytest/unittest."""
    notes = []
    for name, text in sorted(workflow_texts.items()):
        try:
            wf = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            notes.append(f"{name}: not valid YAML"); continue
        for jname, job in (wf.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            steps = job.get("steps") or []
            setup, test, env, unsupported = [], None, {}, []
            for k, v in {**(wf.get("env") or {}), **(job.get("env") or {})}.items():
                if isinstance(v, (str, int, float)) and "${{" not in str(v):
                    env[str(k)] = str(v)
            for st in steps:
                if not isinstance(st, dict) or "run" not in st:
                    continue
                for k, v in (st.get("env") or {}).items():
                    if isinstance(v, (str, int, float)) and "${{" not in str(v):
                        env.setdefault(str(k), str(v))
                for ln in _lines(str(st["run"])):
                    if "${{" in ln:
                        unsupported.append(ln[:60]); continue
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
                        pip, why = _sync_to_pip(ln, repo_texts)
                        if pip:
                            setup.append(pip)
                            notes.append(f"{name}:{jname}: `{ln[:40]}` translated to `{pip}` (lockfile not honoured, groups not installed)")
                        else:
                            unsupported.append(ln[:60])
                    elif test is None and re.match(r"^tox\b", ln):
                        tdeps, ttest = _tox_test(repo_texts)
                        if ttest:
                            setup += tdeps; test = ttest
                            notes.append(f"{name}:{jname}: `{ln[:40]}` resolved from tox.ini [testenv]")
                        else:
                            unsupported.append(ln[:60])
                    elif test is None and (m := re.match(r"^make\s+([A-Za-z0-9_.-]+)\s*$", ln)):
                        mt = _make_test(repo_texts, m.group(1))
                        if mt:
                            test = mt
                            notes.append(f"{name}:{jname}: `{ln}` resolved from the Makefile")
                        else:
                            unsupported.append(ln[:60])
            if test is None:
                continue
            setup = list(dict.fromkeys(setup))
            data = {"schema": recipe_mod.SCHEMA, "setup": setup[:12], "test": test, "env": {k: v for k, v in env.items() if k.isupper()}}
            if unsupported:
                notes.append(f"{name}:{jname}: skipped {len(unsupported)} line(s) with expressions, e.g. {unsupported[0]!r}")
            # validate; drop env entries / setup lines the validator refuses, one at a time, so a single odd line does not discard the whole recipe
            for key in list(data["env"]):
                try:
                    recipe_mod.parse({**data, "env": {key: data["env"][key]}})
                except recipe_mod.RecipeError:
                    del data["env"][key]
            good = []
            for s in data["setup"]:
                try:
                    recipe_mod.parse({**data, "setup": [s], "env": {}})
                    good.append(s)
                except recipe_mod.RecipeError as e:
                    notes.append(f"{name}:{jname}: setup line refused ({str(e)[:50]}): {s[:50]}")
            data["setup"] = good
            try:
                recipe_mod.parse(data)
            except recipe_mod.RecipeError as e:
                notes.append(f"{name}:{jname}: test command refused ({str(e)[:60]})")
                continue
            return data, notes
    notes.append("no workflow job with a pytest/unittest command")
    return None, notes
