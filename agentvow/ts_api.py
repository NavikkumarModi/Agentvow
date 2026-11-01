"""Public-API check for TypeScript changes (optional engine, no build): which exports or members of the changed files were removed or got incompatible parameters.
Method (docs/research/API_DIFF_TS_PROTOTYPE.md): the TypeScript *parser* (nothing is type-checked, resolved, installed or run from the repository) compares each changed file at the base commit with its working-tree text; only files that belong to a
non-private package and are re-exported from that package's source entry count as public API. Needs Node and the `typescript` npm package from a location Agentvow is told about (AGENTVOW_TYPESCRIPT=<a node_modules directory>, or the global npm root);
the repository's own node_modules is never used, because a pull request controls it. Anything that cannot be settled is a gap, not a pass."""
import json
import os
import posixpath
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from .api_diff import _show

HERE = Path(__file__).resolve().parent / "ts"
TEST = re.compile(r"(^|/)(__tests__|__mocks__|tests?|spec|e2e|stories|fixtures?)(/|$)|\.(test|spec|stories)\.[jt]sx?$|\.d\.ts$")
SRC = re.compile(r"\.tsx?$")


def is_candidate(rel: str) -> bool:
    return bool(SRC.search(rel)) and not TEST.search(rel)


@lru_cache(maxsize=1)
def _setup():
    """-> (node_path_dir, typescript_version) or None."""
    node = shutil.which("node")
    if not node:
        return None
    dirs = [os.environ.get("AGENTVOW_TYPESCRIPT", "")]
    try:
        npm = shutil.which("npm")
        if npm:
            dirs.append(subprocess.run([npm, "root", "-g"], capture_output=True, text=True, timeout=20).stdout.strip())
    except Exception:
        pass
    for d in filter(None, dirs):
        try:
            r = subprocess.run([node, "-e", "console.log(require('typescript').version)"], capture_output=True, text=True, timeout=20, cwd=tempfile.gettempdir(), env={"PATH": os.environ.get("PATH", ""), "NODE_PATH": d})
            if r.returncode == 0 and r.stdout.strip():
                return d, r.stdout.strip()
        except Exception:
            continue
    return None


def available() -> str | None:
    s = _setup()
    return s[1] if s else None


def _node(script: str, payload: dict):
    d, _ = _setup()
    with tempfile.TemporaryDirectory(prefix="agentvow_ts_") as cwd:
        r = subprocess.run([shutil.which("node"), "--no-warnings", str(HERE / script)], input=json.dumps(payload), capture_output=True, text=True, timeout=60, cwd=cwd,
                           env={"PATH": os.environ.get("PATH", ""), "NODE_PATH": d})
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None


def _read(repo: Path, rel: str):
    p = repo / rel
    try:
        return p.read_text(encoding="utf-8") if p.is_file() and p.stat().st_size < 600_000 else None
    except Exception:
        return None


def _package_for(repo: Path, rel: str):
    d = posixpath.dirname(rel)
    while True:
        t = _read(repo, (d + "/" if d else "") + "package.json")
        if t:
            try:
                return d, json.loads(t)
            except Exception:
                pass
        if not d:
            return None, None
        d = posixpath.dirname(d)


def _entries(pkg_dir: str, pj: dict) -> list:
    paths = []
    ex = pj.get("exports")
    if isinstance(ex, str):
        paths.append(ex)
    elif isinstance(ex, dict):
        node = ex.get(".", ex)
        if isinstance(node, str):
            paths.append(node)
        elif isinstance(node, dict):
            for k in ("types", "import", "default", "require"):
                v = node.get(k)
                if isinstance(v, str):
                    paths.append(v)
    paths += [pj.get(k) for k in ("types", "typings", "module", "main") if isinstance(pj.get(k), str)]
    out = []
    for p in paths:
        stem = posixpath.splitext(posixpath.normpath(p).lstrip("./"))[0].removesuffix(".d")
        for build in ("dist", "lib", "build", "out", "esm", "cjs"):
            if stem.startswith(build + "/"):
                stem = "src/" + stem[len(build) + 1:]
        out += [posixpath.normpath(posixpath.join(pkg_dir, stem + e)) for e in (".ts", ".tsx", "/index.ts")]
    out += [posixpath.normpath(posixpath.join(pkg_dir, x)) for x in ("src/index.ts", "index.ts", "src/main.ts")]
    return list(dict.fromkeys(out))


def _reachable(repo: Path, entry: str, limit: int = 150) -> set:
    seen, todo = {entry}, [entry]
    while todo and len(seen) < limit:
        f = todo.pop()
        src = _read(repo, f)
        specs = (_node("reexports.js", {"src": src, "file": f}) or []) if src is not None else []
        for spec in specs:
            if not spec.startswith("."):
                continue
            base = posixpath.normpath(posixpath.join(posixpath.dirname(f), spec))
            for cand in (base + ".ts", base + ".tsx", base + "/index.ts", base + "/index.tsx", base.removesuffix(".js") + ".ts", base.removesuffix(".js") + ".tsx"):
                if cand not in seen and (repo / cand).is_file():
                    seen.add(cand); todo.append(cand); break
    return seen


def check(repo: Path, base: str, files: list):
    """-> (found, gaps, skipped). found: breaking changes in files that are public API; gaps: could not be compared; skipped: why a changed file was not treated as public API."""
    found, gaps, skipped, reach_cache = [], [], [], {}
    for f in files:
        old = _show(repo, base, f)
        if old is None:
            continue   # new file: nothing to break
        pdir, pj = _package_for(repo, f)
        if pj is None:
            skipped.append(f"{f}: no package.json found, so no public API is declared"); continue
        if pj.get("private"):
            skipped.append(f"{f}: in a private package (an application, not a library)"); continue
        ent = next((e for e in _entries(pdir or "", pj) if (repo / e).is_file()), None)
        if ent is None:
            skipped.append(f"{f}: the package's source entry could not be found"); continue
        if ent not in reach_cache:
            reach_cache[ent] = _reachable(repo, ent)
        if not (repo / f).exists():
            gaps.append(f"{f} was removed; whether it was public API cannot be told from the working tree (a change to the package entry would show it)"); continue
        if f not in reach_cache[ent]:
            skipped.append(f"{f}: not re-exported from the package entry {ent}"); continue
        new = _read(repo, f)
        if new is None:
            gaps.append(f"could not read {f}"); continue
        res = _node("exports.js", {"old": old, "new": new, "file": f})
        if res is None:
            gaps.append(f"could not compare {f}"); continue
        found += [f"{f}: {x}" for x in res.get("breaking", [])]
        gaps += [f"{f}: {g}" for g in res.get("gaps", [])]
    return found, gaps, skipped
