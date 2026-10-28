"""Classify a repository at a given commit as "plain-pip" or not, from the files AT THAT COMMIT (docs/research/AUDIT_STUDY_PREREG.md, section 2). The earlier classification of 36 repositories read the default
branch today instead of the pull request's commit; this does not: every function takes the files of one commit, and the two readers below take the commit explicitly.

"Plain-pip" means: the zero-configuration ladder (a virtual environment, `pip install` of the project and of the named test extras/requirements files, `pytest`) has a fair chance of reconstructing a test
environment. It is a prediction from files, not a promise; a repository may still fail for reasons the files do not show. Rules are applied in order, each failure is a reason, and the result is deterministic.
Nothing is executed: files are read as text (git blobs of a local clone, or the GitHub contents API).
Usage: python3 research/audit/classify.py --repo-dir DIR --commit SHA     or     --github OWNER/REPO --commit SHA   -> JSON on stdout"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RULES_VERSION = "classify-v1"
ROOT_FILES = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "requirements-dev.txt", "requirements_dev.txt", "requirements-test.txt", "requirements_test.txt", "dev-requirements.txt", "test-requirements.txt",
              "uv.lock", "poetry.lock", "pdm.lock", "Pipfile", "Pipfile.lock", "environment.yml", "environment.yaml", "conda.yml", "package.json", "Cargo.toml", "go.mod", "tox.ini", "pytest.ini", "noxfile.py",
              "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml", "Makefile", "CMakeLists.txt", "meson.build")
REQUIREMENTS = tuple(f for f in ROOT_FILES if f.endswith(".txt") and "requirements" in f)
NON_PIP_BACKENDS = ("maturin", "setuptools-rust", "scikit-build", "scikit_build", "meson", "cmake", "cython", "pybind11", "mesonpy")
NON_PYPI_DEPENDENCY = re.compile(r"(git\+|@\s*git|@\s*https?://|@\s*file:|\{\s*(?:path|git|url)\s*=|\[tool\.uv\.sources\]|file:///)", re.I)
SERVICE_HINT = re.compile(r"\b(testcontainers|docker-compose|psycopg2|asyncpg|pymysql|redis|celery|kafka|pymongo|elasticsearch)\b", re.I)
MAX_BYTES = 300_000


def classify(tree: set, text: dict) -> dict:
    """tree: every file path at the commit. text: {path: contents} for the root files above (missing = not read). -> {"class", "reasons", "facts", "rules_version"}"""
    reasons, facts = [], {}
    root = {p for p in tree if "/" not in p}
    py_meta = [p for p in ("pyproject.toml", "setup.py", "setup.cfg") if p in root]
    reqs = [p for p in REQUIREMENTS if p in root]
    facts["python_metadata"], facts["requirements_files"] = py_meta, reqs
    if not tree:
        return {"class": "unclassifiable", "reasons": ["no file list at this commit"], "facts": facts, "rules_version": RULES_VERSION}
    if not py_meta and not reqs:
        subs = sorted({p.split("/")[0] for p in tree if p.count("/") == 1 and p.endswith(("pyproject.toml", "setup.py"))})
        facts["subprojects"] = subs[:8]
        reasons.append("no Python project metadata or requirements file at the repository root" + (f" (sub-projects: {', '.join(subs[:4])})" if subs else ""))
    if "package.json" in root:
        reasons.append("package.json at the root: tests may need Node as well")
    for lang_file in ("Cargo.toml", "go.mod"):
        if lang_file in root and not py_meta:
            reasons.append(f"{lang_file} at the root and no Python metadata: not primarily a Python project")
    for lock in ("uv.lock", "poetry.lock", "pdm.lock", "Pipfile.lock"):
        if lock in root:
            reasons.append(f"{lock} present: dependencies are pinned for another installer (zero-config pip does not read it; this rule is conservative)")
    if {"environment.yml", "environment.yaml", "conda.yml"} & root:
        reasons.append("conda environment file at the root")
    if {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"} & root:
        reasons.append("a compose file at the root: tests may need services")
    pyproject = text.get("pyproject.toml", "")
    setup_py = text.get("setup.py", "")
    meta_text = "\n".join(text.get(p, "") for p in py_meta + reqs)
    backend = re.search(r"build-backend\s*=\s*[\"']([^\"']+)", pyproject)
    facts["build_backend"] = backend.group(1) if backend else None
    reqs_line = re.search(r"requires\s*=\s*\[([^\]]*)\]", pyproject, re.S)
    build_requires = (reqs_line.group(1) if reqs_line else "") + " " + setup_py
    hit = [b for b in NON_PIP_BACKENDS if b in build_requires.lower() or (backend and b in backend.group(1).lower())]
    if hit:
        reasons.append(f"build needs a compiler toolchain or non-pip build tool: {', '.join(sorted(set(hit)))}")
    if "ext_modules" in setup_py:
        reasons.append("setup.py declares compiled extension modules")
    if NON_PYPI_DEPENDENCY.search(meta_text):
        reasons.append("a dependency comes from git, a URL, a local path or [tool.uv.sources], not PyPI")
    svc = sorted({m.group(1).lower() for m in SERVICE_HINT.finditer(meta_text)})
    facts["service_hints"] = svc
    if svc:
        reasons.append(f"test dependencies hint at services ({', '.join(svc[:4])})")
    has_tests = any(re.match(r"(tests?|test)/.*\.py$", p) or re.match(r"test_.*\.py$", p.rsplit("/", 1)[-1]) or p.endswith("_test.py") for p in tree) or "pytest" in meta_text.lower() or "pytest.ini" in root
    facts["has_tests"] = has_tests
    if not has_tests:
        reasons.append("no test files and no pytest configuration found")
    if not reasons:
        return {"class": "plain_pip", "reasons": [], "facts": facts, "rules_version": RULES_VERSION}
    return {"class": "not_plain", "reasons": reasons, "facts": facts, "rules_version": RULES_VERSION}


def from_git(repo_dir: Path, commit: str) -> tuple:
    """Read the tree and the root files at `commit` from a local clone: `git ls-tree` and `git show`, no checkout, nothing executed."""
    def git(*a):
        return subprocess.run(["git", "-C", str(repo_dir), *a], capture_output=True, text=True, timeout=120)
    ls = git("ls-tree", "-r", "--name-only", commit)
    if ls.returncode:
        return set(), {}
    tree = set(ls.stdout.splitlines())
    text = {}
    for f in ROOT_FILES:
        if f in tree:
            p = git("show", f"{commit}:{f}")
            if p.returncode == 0:
                text[f] = p.stdout[:MAX_BYTES]
    return tree, text


def from_github(slug: str, commit: str) -> tuple:
    """Same, from the GitHub API (needs `gh`); the tree is the commit's recursive tree (truncated trees are marked and classified unclassifiable by the caller)."""
    def gh(path):
        p = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=120)
        return json.loads(p.stdout) if p.returncode == 0 and p.stdout.strip() else None
    t = gh(f"repos/{slug}/git/trees/{commit}?recursive=1")
    if not t or t.get("truncated"):
        return set(), {}
    tree = {x["path"] for x in t.get("tree", []) if x.get("type") == "blob"}
    text = {}
    for f in ROOT_FILES:
        if f in tree:
            c = gh(f"repos/{slug}/contents/{f}?ref={commit}")
            if c and c.get("encoding") == "base64":
                import base64
                text[f] = base64.b64decode(c["content"]).decode("utf-8", "replace")[:MAX_BYTES]
    return tree, text


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--repo-dir")
    g.add_argument("--github")
    a = ap.parse_args(argv)
    tree, text = from_git(Path(a.repo_dir), a.commit) if a.repo_dir else from_github(a.github, a.commit)
    out = classify(tree, text)
    out["commit"] = a.commit
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
