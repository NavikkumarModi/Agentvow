"""Public-surface filter for the TypeScript prototype (docs/research/API_DIFF_TS_PROTOTYPE.md): for each flagged file decide private / no entry / unreachable / reachable.
private: the nearest package.json at the head commit has "private": true. entry: the source file the package's entry most plausibly comes from (types/typings/exports/main/module mapped from a build folder to src, or src/index.ts, index.ts).
reachable: the file is the entry or is reached from it by following re-export declarations (file-level, approximate: a reachable file may still keep some of its names internal).
Usage: NODE_PATH=<dir with typescript> python3 research/ts_apidiff/reach.py <scratch_dir>  (reads <scratch_dir>/ts_bakeoff.json)"""
import json
import os
import posixpath
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXT = (".ts", ".tsx", "/index.ts", "/index.tsx", ".d.ts")
cache = {}


def raw(repo, path, ref):
    k = (repo, path, ref)
    if k not in cache:
        r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw", f"repos/{repo}/contents/{path}?ref={ref}"], capture_output=True, text=True)
        cache[k] = r.stdout if r.returncode == 0 and len(r.stdout) < 600_000 else None
    return cache[k]


def package_for(repo, fn, ref):
    d = posixpath.dirname(fn)
    while True:
        t = raw(repo, (d + "/" if d else "") + "package.json", ref)
        if t:
            try:
                return d, json.loads(t)
            except Exception:
                pass
        if not d:
            return None, None
        d = posixpath.dirname(d)


def entry_candidates(pkg_dir, pj):
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
        p = posixpath.normpath(p).lstrip("./")
        stem = posixpath.splitext(p)[0].removesuffix(".d")
        for build in ("dist", "lib", "build", "out", "esm", "cjs"):
            if stem.startswith(build + "/"):
                stem = "src/" + stem[len(build) + 1:]
        out += [posixpath.join(pkg_dir, stem + e) for e in (".ts", ".tsx", "/index.ts")]
    out += [posixpath.join(pkg_dir, x) for x in ("src/index.ts", "index.ts", "src/main.ts")]
    return list(dict.fromkeys(out))


def reexports(src, fn):
    p = subprocess.run(["node", str(ROOT / "agentvow/ts/reexports.js")], input=json.dumps({"src": src, "file": fn}), capture_output=True, text=True, env=os.environ, timeout=30)
    try:
        return [e["spec"] for e in json.loads(p.stdout)["edges"]]   # file-level: the names are ignored here (the shipped engine tracks them)
    except Exception:
        return []


def reachable_set(repo, entry, ref, limit=150):
    seen, todo = {entry}, [entry]
    while todo and len(seen) < limit:
        f = todo.pop()
        src = raw(repo, f, ref)
        if src is None:
            continue
        for spec in reexports(src, f):
            if not spec.startswith("."):
                continue
            base = posixpath.normpath(posixpath.join(posixpath.dirname(f), spec))
            for cand in (base + ".ts", base + ".tsx", base + "/index.ts", base + "/index.tsx", base.removesuffix(".js") + ".ts", base.removesuffix(".js") + ".tsx"):
                if cand not in seen and raw(repo, cand, ref) is not None:
                    seen.add(cand); todo.append(cand); break
    return seen


def main():
    scratch = Path(sys.argv[1])
    d = json.load(open(scratch / "ts_bakeoff.json"))
    cheap = {json.loads(l)["pr"]: json.loads(l) for l in (ROOT / "data/shadow2/cheap.jsonl").read_text().splitlines()}
    res = []
    for x in d:
        ref = cheap[x["pr"]]["head"]
        for f in x["files"]:
            if not f.get("breaking"):
                continue
            pdir, pj = package_for(x["repo"], f["file"], ref)
            if pj is None:
                cls = "no package.json"
            elif pj.get("private"):
                cls = "private"
            else:
                ent = next((e for e in entry_candidates(pdir or "", pj) if raw(x["repo"], e, ref) is not None), None)
                if ent is None:
                    cls = "no entry found"
                else:
                    cls = "reachable" if f["file"] in reachable_set(x["repo"], ent, ref) else "unreachable"
            res.append({"pr": x["pr"], "repo": x["repo"], "file": f["file"], "class": cls, "breaking": f["breaking"][:5]})
    (scratch / "reach.json").write_text(json.dumps(res, indent=1))
    import collections
    print(collections.Counter(r["class"] for r in res))
    print("PRs by best class:", collections.Counter(max((r["class"] for r in res if r["pr"] == p), key=["private", "no package.json", "no entry found", "unreachable", "reachable"].index) for p in {r["pr"] for r in res}))


if __name__ == "__main__":
    main()
