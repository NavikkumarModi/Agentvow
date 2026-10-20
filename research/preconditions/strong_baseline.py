"""Strong reconstruction baseline (E3 of docs/strategy/PRODUCT_EXPLORATION_2026-10.md). Everything a careful newcomer could read from the repository at the base commit, derived
deterministically and passed through the product's recipe validator: the zero-config ladder's own steps, plus every `pip install` line in the GitHub Actions workflows (and tox.ini deps,
uv/poetry sync translated to pip, Makefile test targets), plus `pip install` lines in Dockerfiles, plus the other requirements files. The test command is NOT derived: every context replays the same
scoped target command. No language model; no knowledge of any task's outcome. Frozen before it is applied to the B6 tasks (see the pre-registration in the exploration note)."""
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
from agentvow import envsetup, recipe as recipe_mod  # noqa: E402
import ci_recipe  # noqa: E402

MAX_SETUP = 12
EXCLUDE_REQ = re.compile(r"doc|lint|format|typing|mypy|build|release|publish|windows|win32|benchmark|bench", re.I)
_SHELL_SPLIT = re.compile(r"\s*(?:&&|;|\|\|)\s*")


def dockerfile_setup(text: str) -> list:
    """`pip install ...` commands in RUN lines (continuations joined, chains split). Anything with a shell expansion is skipped."""
    out = []
    joined = re.sub(r"\\\n\s*", " ", text)
    for ln in joined.splitlines():
        ln = ln.strip()
        if not re.match(r"^RUN\s", ln, re.I):
            continue
        for part in _SHELL_SPLIT.split(ln[4:].strip()):
            part = part.strip()
            if "$" in part or "`" in part:
                continue
            args = ci_recipe._pip_args(part)
            if args is None:
                continue
            names = [a for a in args if not a.startswith("-")]
            if names and all(ci_recipe._SKIP_PIP.match(n) for n in names):
                continue
            out.append("pip install " + " ".join(shlex.quote(a) for a in args))
    return list(dict.fromkeys(out))


def other_requirements(repo: Path) -> list:
    """requirements files beyond the ladder's fixed list: requirements*.txt, requirements/*.txt, *-requirements.txt, in the repository root and one directory down for `requirements/`."""
    have = set(envsetup.REQ_FILES)
    found = []
    for pat in ("requirements*.txt", "*-requirements.txt", "*_requirements.txt", "requirements/*.txt"):
        for f in sorted(repo.glob(pat)):
            rel = str(f.relative_to(repo))
            if f.is_file() and rel not in have and not EXCLUDE_REQ.search(f.name) and rel not in found:
                found.append(rel)
    return found


def derive_strong(repo: Path, targets: list):
    """-> (recipe dict, notes). `repo` is a checkout of the base commit."""
    repo = Path(repo)
    notes, setup, env = [], [], {}
    extras = envsetup.detect_extras(repo)
    if (repo / "pyproject.toml").exists() or (repo / "setup.py").exists():
        setup.append("pip install " + (".[" + ",".join(extras) + "]" if extras else "."))
    if envsetup.detect_groups(repo):
        notes.append("dependency groups present; not installable through the recipe vocabulary")
    setup += [f"pip install -r {f}" for f in envsetup.REQ_FILES if (repo / f).exists()]
    wf = {}
    for f in sorted((repo / ".github" / "workflows").glob("*.y*ml")) if (repo / ".github" / "workflows").is_dir() else []:
        try:
            wf[f.name] = f.read_text()
        except OSError:
            pass
    texts = {}
    for n in ("pyproject.toml", "tox.ini", "Makefile"):
        if (repo / n).exists():
            try:
                texts[n] = (repo / n).read_text()
            except OSError:
                pass
    if wf:
        d, n2 = ci_recipe.derive(wf, texts)
        notes += n2
        if d:
            setup += d["setup"]
            env.update(d.get("env") or {})
            notes.append(f"CI workflow supplied {len(d['setup'])} setup line(s) and {len(d.get('env') or {})} env value(s)")
    else:
        notes.append("no GitHub Actions workflow")
    docker = []
    for f in sorted(list(repo.glob("Dockerfile*")) + list(repo.glob("*/Dockerfile*")) + list(repo.glob("docker/*/Dockerfile*"))):
        if f.is_file():
            try:
                docker += dockerfile_setup(f.read_text())
            except OSError:
                pass
    docker = list(dict.fromkeys(docker))
    if docker:
        notes.append(f"Dockerfile(s) supplied {len(docker)} pip line(s)")
    setup += docker
    setup += [f"pip install -r {f}" for f in other_requirements(repo)]
    setup = list(dict.fromkeys(setup))
    good = []
    for s in setup:
        try:
            recipe_mod.parse({"schema": recipe_mod.SCHEMA, "setup": [s], "test": "pytest -q", "env": {}})
            good.append(s)
        except recipe_mod.RecipeError as e:
            notes.append(f"setup line refused by the validator ({str(e)[:50]}): {s[:60]}")
    if len(good) > MAX_SETUP:
        notes.append(f"{len(good) - MAX_SETUP} setup line(s) beyond the 12-step limit dropped (last ones)")
    data = {"schema": recipe_mod.SCHEMA, "setup": good[:MAX_SETUP], "test": "pytest -q " + " ".join(targets),
            "env": {k: v for k, v in env.items() if k.isupper()}}
    for k in list(data["env"]):
        try:
            recipe_mod.parse({**data, "env": {k: data["env"][k]}})
        except recipe_mod.RecipeError:
            del data["env"][k]
    recipe_mod.parse(data)   # must validate as a whole
    return data, notes
