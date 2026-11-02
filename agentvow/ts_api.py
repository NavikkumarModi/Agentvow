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


def _targets(pj: dict) -> list:
    """Every file the package.json offers to importers: the root entry first, then the other `exports` subpaths, then the legacy fields. Strings only; data, styles and binaries are dropped."""
    out = []

    def walk(node):
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    ex = pj.get("exports")
    if isinstance(ex, dict) and any(k.startswith(".") for k in ex):
        walk(ex.get("."))
        for k, v in ex.items():
            if k.startswith(".") and k != ".":
                walk(v)
    else:
        walk(ex)
    out += [pj.get(k) for k in ("types", "typings", "module", "main") if isinstance(pj.get(k), str)]
    return [t for t in dict.fromkeys(out) if not t.endswith((".json", ".css", ".node", ".wasm", ".map"))]


def _source_for(pkg_dir: str, target: str) -> list:
    stem = posixpath.splitext(posixpath.normpath(target).lstrip("./"))[0].removesuffix(".d")
    for build in ("dist", "lib", "build", "out", "esm", "cjs"):
        if stem.startswith(build + "/"):
            stem = "src/" + stem[len(build) + 1:]
    return [posixpath.normpath(posixpath.join(pkg_dir, stem + e)) for e in (".ts", ".tsx", "/index.ts")]


def _entries(pkg_dir: str, pj: dict, repo: Path) -> list:
    """Source files that are entries of the package (existing ones). Falls back to the conventional src/index.ts only when no declared target maps to a file."""
    found = []
    for t in _targets(pj):
        for c in _source_for(pkg_dir, t):
            if (repo / c).is_file():
                found.append(c); break
    if not found:
        found = [c for c in (posixpath.normpath(posixpath.join(pkg_dir, x)) for x in ("src/index.ts", "index.ts", "src/main.ts")) if (repo / c).is_file()][:1]
    return list(dict.fromkeys(found))


def _resolve(repo: Path, frm: str, spec: str):
    base = posixpath.normpath(posixpath.join(posixpath.dirname(frm), spec))
    for cand in (base + ".ts", base + ".tsx", base + "/index.ts", base + "/index.tsx", base.removesuffix(".js") + ".ts", base.removesuffix(".js") + ".tsx"):
        if (repo / cand).is_file():
            return cand
    return None


def _public(repo: Path, entries: list, limit: int = 400) -> dict:
    """-> {file: "*" | set of names}: which names of each file are public API, by following re-exports from the entries. An entry exports all of its own names. A name-limited re-export (`export { a } from "./x"`) makes only
    `a` public in x; `export *` passes on whatever is public in the re-exporting file. A re-export alias is not tracked through a second hop (the underlying names are passed on), which can only over-include."""
    pub, work = {}, []

    def grow(f, names):
        cur = pub.get(f)
        if cur == "*":
            return
        if names == "*":
            pub[f] = "*"; work.append(f); return
        new = set(names) - (cur or set())
        if cur is None or new:
            pub[f] = (cur or set()) | set(names); work.append(f)
    for e in entries:
        grow(e, "*")
    steps = 0
    while work and steps < limit:
        f = work.pop(); steps += 1
        src = _read(repo, f)
        res = _node("reexports.js", {"src": src, "file": f}) if src is not None else None
        for edge in (res or {}).get("edges", []):
            target = _resolve(repo, f, edge["spec"]) if edge["spec"].startswith(".") else None
            if target is None:
                continue
            if edge["names"] == "*":
                grow(target, pub[f])
            else:
                grow(target, edge["names"])
    return pub


def _top(finding: str) -> str:
    """The top-level name a finding is about: 'removed: A.b' -> 'A', 'f: parameter ...' -> 'f', 'A.m: ...' -> 'A'."""
    t = finding[len("removed: "):] if finding.startswith("removed: ") else finding
    return t.split(":", 1)[0].split(".", 1)[0].split("#", 1)[0]


def check(repo: Path, base: str, files: list):
    """-> (found, gaps, skipped). found: breaking changes in names that are public API; gaps: could not be compared; skipped: why a changed file (or part of one) was not treated as public API."""
    found, gaps, skipped, pub_cache = [], [], [], {}
    for f in files:
        old = _show(repo, base, f)
        if old is None:
            continue   # new file: nothing to break
        pdir, pj = _package_for(repo, f)
        if pj is None:
            skipped.append(f"{f}: no package.json found, so no public API is declared"); continue
        if pj.get("private"):
            skipped.append(f"{f}: in a private package (an application, not a library)"); continue
        key = (pdir, json.dumps(pj, sort_keys=True))
        if key not in pub_cache:
            ents = _entries(pdir or "", pj, repo)
            pub_cache[key] = (ents, _public(repo, ents) if ents else {})
        ents, pub = pub_cache[key]
        if not ents:
            skipped.append(f"{f}: the package's source entry could not be found"); continue
        if not (repo / f).exists():
            gaps.append(f"{f} was removed; whether it was public API cannot be told from the working tree (a change to the package entry would show it)"); continue
        names = pub.get(f)
        if names is None:
            skipped.append(f"{f}: not re-exported from a package entry ({', '.join(ents[:2])})"); continue
        new = _read(repo, f)
        if new is None:
            gaps.append(f"could not read {f}"); continue
        res = _node("exports.js", {"old": old, "new": new, "file": f})
        if res is None:
            gaps.append(f"could not compare {f}"); continue
        hits = res.get("breaking", [])
        if names != "*":
            private_hits = [h for h in hits if _top(h) not in names]
            hits = [h for h in hits if _top(h) in names]
            if private_hits:
                skipped.append(f"{f}: {len(private_hits)} change(s) to names the package entry does not re-export")
        found += [f"{f}: {x}" for x in hits]
        gaps += [f"{f}: {g}" for g in res.get("gaps", [])]
    return found, gaps, skipped
