"""Static eligibility scan for replaying JavaScript/TypeScript test and lint claims (docs/research/JS_TEST_SANDBOX_DESIGN.md, open question 2).
Reads only GitHub file contents at each pull request's head commit (package.json, the lockfile, a few config names). Nothing is cloned, installed or run.
Usage: python3 research/js_sandbox/eligibility.py <out_dir>   -> <out_dir>/js_eligibility.json (one summary per pull request; lockfile text is not kept)"""
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research/shadow2"))
from common import gh  # noqa: E402

REGISTRY = "https://registry.npmjs.org/"
TEST_RUNNERS = ("jest", "vitest", "mocha", "node --test", "ava", "tap", "playwright test")   # playwright/browsers need downloads: counted separately below
META = re.compile(r"[;&|`$<>()\\\n]|&&|\|\|")
LINT_RUNNERS = ("eslint", "biome", "prettier", "tsc", "oxlint")
LOCKS = {"package-lock.json": "npm", "npm-shrinkwrap.json": "npm", "yarn.lock": "yarn", "pnpm-lock.yaml": "pnpm", "bun.lock": "bun", "bun.lockb": "bun"}


def raw(repo, path, ref, limit=60_000_000):
    r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw", f"repos/{repo}/contents/{urllib.parse.quote(path)}?ref={ref}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 and len(r.stdout) < limit else None


def classify_script(cmd, runners):
    """-> (status, runner). Strict: one plain command from a known runner; anything with shell syntax or indirection is not eligible."""
    if not cmd:
        return "none", None
    if META.search(cmd):
        return "shell_syntax", None
    c = re.sub(r"^(cross-env\s+(\w+=\S+\s+)*|env\s+(\w+=\S+\s+)*|(\w+=\S+\s+)+)", "", cmd.strip())
    for r in runners:
        if re.match(rf"^(npx\s+|pnpm exec\s+|yarn\s+)?{re.escape(r)}(\s|$)", c):
            return "recognised", r
    if re.match(r"^(npm|yarn|pnpm)\s+(run\s+)?\w", c):
        return "indirect", None
    return "unrecognised", c.split()[0] if c.split() else None


def scan_lock(text):
    out = {"packages": 0, "non_registry": 0, "git_or_file": 0, "install_script_pkgs": []}
    try:
        d = json.loads(text)
    except ValueError:
        out["parse"] = "error"; return out
    out["lockfileVersion"] = d.get("lockfileVersion")
    pk = d.get("packages") or {}
    for path, meta in pk.items():
        if not path:
            continue
        out["packages"] += 1
        res = meta.get("resolved", "")
        if meta.get("link") or res.startswith(("git", "file:", "http://")) or "github.com" in res or res.startswith("git+"):
            out["git_or_file"] += 1
        elif res and not res.startswith(REGISTRY):
            out["non_registry"] += 1
        if meta.get("hasInstallScript"):
            out["install_script_pkgs"].append(path.rsplit("node_modules/", 1)[-1])
    if not pk:
        out["packages"] = len(d.get("dependencies") or {}); out["old_lock_format"] = True
    return out


def main():
    out_dir = Path(sys.argv[1]); out_dir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in (ROOT / "data/shadow2/cheap.jsonl").read_text().splitlines()]
    units = [x for x in rows if "head" in x and not x["changes_python"] and any(c["kind"] in ("tests_pass", "lint_clean") for c in x["claims"])]
    res = []
    for i, x in enumerate(units):
        repo, ref = x["repo"], x["head"]
        top = gh(f"repos/{repo}/contents/?ref={ref}")
        rec = {"pr": x["pr"], "repo": repo, "kinds": sorted({c["kind"] for c in x["claims"]})}
        if not isinstance(top, list):
            rec["status"] = "repo_unreadable"; res.append(rec); continue
        names = {t["name"] for t in top}
        if "package.json" not in names:
            rec["status"] = "no_package_json"; res.append(rec); continue
        pj = raw(repo, "package.json", ref, 2_000_000)
        try:
            pj = json.loads(pj)
        except Exception:
            rec["status"] = "package_json_unreadable"; res.append(rec); continue
        scripts = pj.get("scripts") or {}
        locks = [LOCKS[n] for n in names if n in LOCKS]
        rec.update(pm=sorted(set(locks)) or ["none"], workspaces=bool(pj.get("workspaces")), npmrc=".npmrc" in names, yarnrc=".yarnrc.yml" in names, pnp=".pnp.cjs" in names,
                   packageManager=(pj.get("packageManager") or "").split("@")[0], nvmrc=(".nvmrc" in names or ".node-version" in names), engines_node=(pj.get("engines") or {}).get("node"),
                   test=dict(zip(("status", "runner"), classify_script(scripts.get("test"), TEST_RUNNERS))), test_cmd=(scripts.get("test") or "")[:120],
                   lint=dict(zip(("status", "runner"), classify_script(scripts.get("lint"), LINT_RUNNERS))),
                   hooks=[k for k in ("pretest", "posttest", "preinstall", "install", "postinstall", "prepare", "prepublish") if k in scripts],
                   git_deps=[k for k, v in {**(pj.get("dependencies") or {}), **(pj.get("devDependencies") or {})}.items() if isinstance(v, str) and re.match(r"(git|github:|https?:|file:|link:|[\w.-]+/[\w.-]+$)", v)][:5])
        if "npm" in locks:
            ln = "package-lock.json" if "package-lock.json" in names else "npm-shrinkwrap.json"
            lock = raw(repo, ln, ref)
            rec["lock"] = scan_lock(lock) if lock else {"unreadable_or_huge": True}
            rec["lock_bytes"] = len(lock or "")
        rec["status"] = "scanned"
        res.append(rec)
        if i % 25 == 0:
            print(i, len(units), flush=True)
            (out_dir / "js_eligibility.json").write_text(json.dumps(res, indent=1))
    (out_dir / "js_eligibility.json").write_text(json.dumps(res, indent=1))
    print("done", len(res))


main()
