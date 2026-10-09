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


def derive(workflow_texts: dict, repo_files: set | None = None):
    """-> (recipe dict or None, notes list). `workflow_texts`: {filename: yaml text}. Picks the first workflow job that runs pytest/unittest."""
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
                    cand = re.sub(r"^(?:uv run|poetry run|pipenv run|pdm run|hatch run|python3? -m )\s*(?:--\S+\s+)*", "", ln).strip()
                    cand = "python -m " + cand if re.match(r"^unittest\b", cand) else cand
                    if re.match(r"^(python3? -m )?(pytest|py\.test|unittest)\b", cand) and test is None:
                        test = cand
                    elif re.match(r"^(uv sync|poetry install|pdm install|pipenv install|hatch env)", ln):
                        unsupported.append(ln[:60])
            if test is None:
                continue
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
