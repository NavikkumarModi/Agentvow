"""Why does the zero-config ladder (agentvow/envsetup.py build_env) not install what the tests of these repositories import? Reads each repository's files through the GitHub API (default branch today:
an approximation of the state at the pull request), executes nothing, and compares the modules the replays reported missing with where the repository declares its dependencies.
Usage: python3 research/envsetup/classify_inconclusive.py   -> prints a table, writes data/checker_eval/classify_inconclusive.json"""
import base64
import collections
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research" / "checkers"))
import pr_body_precision as P  # noqa: E402

LADDER_EXTRAS = ("test", "tests", "testing", "dev", "develop")
LADDER_REQ = ("requirements.txt", "requirements-dev.txt", "requirements_dev.txt", "requirements-test.txt", "requirements_test.txt", "dev-requirements.txt", "test-requirements.txt", "tests/requirements.txt")
ALIAS = {"yaml": "pyyaml", "dotenv": "python-dotenv", "dateutil": "python-dateutil", "bs4": "beautifulsoup4", "gi": "pygobject", "openssl": "pyopenssl", "antlr4": "antlr4-python3-runtime", "cv2": "opencv-python",
         "pil": "pillow", "sklearn": "scikit-learn", "jwt": "pyjwt", "attr": "attrs", "git": "gitpython", "serial": "pyserial", "magic": "python-magic", "google": "google", "azure": "azure", "grpc": "grpcio"}


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def names_from_reqs(text):
    out = set()
    for ln in text.splitlines():
        ln = ln.split("#")[0].strip()
        m = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)", ln)
        if m and not ln.startswith(("-", "git+", "http")):
            out.add(norm(m.group(1)))
    return out


def names_from_specs(specs):
    return {norm(re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", s).group(1)) for s in specs if isinstance(s, str) and re.match(r"\s*[A-Za-z0-9]", s)}


def get_file(repo, path):
    meta = P.gh(f"repos/{repo}/contents/{path}")
    if isinstance(meta, dict) and meta.get("content"):
        return base64.b64decode(meta["content"]).decode("utf-8", "replace")
    return ""


def declared(repo):
    """-> {"ladder": set of dist names the ladder would install, "elsewhere": {name: where}, "facts": {...}}"""
    tree = P.gh(f"repos/{repo}/git/trees/HEAD?recursive=1")
    paths = [t["path"] for t in tree.get("tree", [])] if isinstance(tree, dict) else []
    facts = {"tree_truncated": bool(isinstance(tree, dict) and tree.get("truncated"))}
    ladder, elsewhere = set(), {}
    root_py = get_file(repo, "pyproject.toml") if "pyproject.toml" in paths else ""
    facts["root_pyproject"] = bool(root_py); facts["root_setup_py"] = "setup.py" in paths
    try:
        d = tomllib.loads(root_py) if root_py else {}
    except Exception:
        d = {}
    proj = d.get("project", {})
    ladder |= names_from_specs(proj.get("dependencies", []))
    for extra, specs in (proj.get("optional-dependencies") or {}).items():
        (ladder if extra in LADDER_EXTRAS else elsewhere.setdefault("_extras", set())).update(names_from_specs(specs)) if extra in LADDER_EXTRAS else [elsewhere.setdefault(n, f"extra '{extra}'") for n in names_from_specs(specs)]
    for g, specs in (d.get("dependency-groups") or {}).items():
        flat = [s for s in specs if isinstance(s, str)]
        if g in LADDER_EXTRAS:
            ladder |= names_from_specs(flat)
        else:
            for n in names_from_specs(flat):
                elsewhere.setdefault(n, f"dependency group '{g}'")
    poetry = d.get("tool", {}).get("poetry", {})
    for n in names_from_specs(list((poetry.get("dependencies") or {}).keys())):
        ladder.add(n)
    for gname, g in (poetry.get("group") or {}).items():
        for n in names_from_specs(list((g.get("dependencies") or {}).keys())):
            elsewhere.setdefault(n, f"poetry group '{gname}'")
    facts["uv_workspace"] = bool(d.get("tool", {}).get("uv", {}).get("workspace"))
    for p in paths:
        base = p.rsplit("/", 1)[-1]
        if re.fullmatch(r"requirements[^/]*\.txt", base) and p.count("/") <= 3:
            names = names_from_reqs(get_file(repo, p))
            if p in LADDER_REQ:
                ladder |= names
            else:
                for n in names:
                    elsewhere.setdefault(n, f"{p}")
        elif base == "pyproject.toml" and p != "pyproject.toml" and p.count("/") <= 3 and len([1 for q in elsewhere.values() if q.startswith("sub:")]) < 400:
            try:
                sd = tomllib.loads(get_file(repo, p))
            except Exception:
                continue
            specs = list(sd.get("project", {}).get("dependencies", []))
            for g in (sd.get("dependency-groups") or {}).values():
                specs += [s for s in g if isinstance(s, str)]
            for n in names_from_specs(specs):
                elsewhere.setdefault(n, f"sub:{p}")
        elif base in ("Pipfile",) and p.count("/") <= 2:
            for n in re.findall(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*=", get_file(repo, p), re.M):
                elsewhere.setdefault(norm(n), p)
        elif base in ("environment.yml", "environment.yaml"):
            for n in names_from_reqs("\n".join(l.strip("- ") for l in get_file(repo, p).splitlines())):
                elsewhere.setdefault(n, p)
    facts["has_setup_py_or_pyproject_root"] = facts["root_pyproject"] or facts["root_setup_py"]
    return {"ladder": ladder, "elsewhere": elsewhere, "facts": facts}


def where(module, info):
    m = norm(module)
    cands = {m, ALIAS.get(m, m), m.replace("-", "")}
    def hit(names):
        return any(n in cands or n.replace("-", "") in cands or (len(m) >= 5 and n.startswith(m)) or (m in ("google", "azure", "opentelemetry") and n.startswith(m)) for n in names)
    if hit(info["ladder"]):
        return "installed by the ladder (declared where it looks)"
    el = [(n, w) for n, w in info["elsewhere"].items() if hit([n])]
    if el:
        w = el[0][1]
        kind = "an extra" if w.startswith("extra") else "a dependency group" if w.startswith("dependency group") else "a poetry group" if w.startswith("poetry") else "a subproject" if w.startswith("sub:") else "another requirements/Pipfile/conda file"
        return "declared in " + kind
    return "declared nowhere the files show (transitive, local, or system)"


def main():
    rows = [json.loads(l) for l in (ROOT / "data" / "detection_v2_results_plus.jsonl").read_text().splitlines()]
    missing = collections.defaultdict(set)
    for r in rows:
        if r["head_result"] == "inconclusive" or r["base_result"] == "inconclusive":
            for k in ("head_summary", "base_hint", "head_hint"):
                m = re.search(r"missing dependency in Agentvow's environment: ([\w.\-, ]+?)(?: \(|$)", r.get(k) or "")
                if m:
                    missing[r["repo"]] |= {x.strip() for x in m.group(1).split(",") if len(x.strip()) >= 3}
            if not missing[r["repo"]]:
                missing[r["repo"]] |= set()
    repos = sorted({r["repo"] for r in rows if r["head_result"] == "inconclusive" or r["base_result"] == "inconclusive"})
    out, tally, mod_tally = {}, collections.Counter(), collections.Counter()
    for repo in repos:
        info = declared(repo)
        f = info["facts"]
        mods = sorted(missing.get(repo, []))
        w = {m: where(m, info) for m in mods}
        for v in w.values():
            mod_tally[v] += 1
        if not mods:
            cause = "no missing module named (the run failed another way)"
        elif not f["has_setup_py_or_pyproject_root"] and not any("installed" in v for v in w.values()):
            cause = "no root project to install: dependencies live elsewhere or nowhere declared"
        elif any(v.startswith("declared in") for v in w.values()):
            cause = "declared in a place the ladder does not read"
        elif all("installed" in v for v in w.values()):
            cause = "declared where the ladder looks, yet missing (install failed or limits)"
        else:
            cause = "declared nowhere the files show"
        tally[cause] += 1
        out[repo] = {"cause": cause, "modules": w, "facts": f}
        print(repo.ljust(38), cause[:62].ljust(62), "; ".join(f"{m}:{v[:22]}" for m, v in list(w.items())[:3]))
    print(); [print(f"{v:3d}  {k}") for k, v in tally.most_common()]
    print(); [print(f"{v:3d}  {k}") for k, v in mod_tally.most_common()]
    (ROOT / "data" / "checker_eval" / "classify_inconclusive.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
