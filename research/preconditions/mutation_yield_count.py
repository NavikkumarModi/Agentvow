"""Yield pre-count for MUTATION_STUDY_PREREG.md: how many candidate mutants does cosmic-ray enumerate on the lines the agent's patch added, for each rebuildable valid B6 run?
Counts only: no test is run and no outcome is read. Usage: python3 research/preconditions/mutation_yield_count.py -> data/preconditions/mutation_yield.jsonl"""
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["B6"] = "1"
import stageb_run as sb  # noqa: E402

D = ROOT / "data" / "preconditions"
OUT = D / "mutation_yield.jsonl"
CR = "/tmp/mutvenv/bin/cosmic-ray"
TESTY = re.compile(r"(^|/)(tests?|testing)(/|$)|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")


def added(patch):
    out, cur, n = {}, None, 0
    for ln in patch.splitlines():
        m = re.match(r"^diff --git a/.* b/(.*)$", ln)
        if m:
            cur = m.group(1); out.setdefault(cur, set()); continue
        h = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", ln)
        if h:
            n = int(h.group(1)); continue
        if cur is None or ln.startswith(("+++", "---")):
            continue
        if ln.startswith("+"):
            out[cur].add(n); n += 1
        elif not ln.startswith("-"):
            n += 1
    return {f: s for f, s in out.items() if f.endswith(".py") and not TESTY.search(f)}


def main():
    rows = [json.loads(l) for l in (D / "stageb6_results.jsonl").read_text().splitlines() if l.strip()]
    tasks = {(j["repo"], j["pr"]): j for j in map(json.loads, (D / "stageb6_tasks.jsonl").read_text().splitlines())}
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    for r in rows:
        k = (r["repo"], r["pr"])
        if k in done or not (r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env")):
            continue
        rd = Path(r["run_dir"]); status = (rd / "status.txt").read_text()
        if [l for l in status.splitlines() if l.startswith("??") and not l[3:].startswith((".agentvow", ".pytest_cache", "__pycache__")) and not l[3:].endswith((".pyc", ".json"))]:
            OUT.open("a").write(json.dumps({"repo": k[0], "pr": k[1], "skipped": "untracked files not in the saved patch"}) + "\n"); continue
        tmp = Path(tempfile.mkdtemp(prefix="myield_"))
        try:
            repo, _ = sb.prepare(tasks[k], tmp)
            patch = (rd / "patch.diff").read_text()
            if repo is None or (patch.strip() and sb.sh(["git", "apply", "--whitespace=nowarn", str(rd / "patch.diff")], repo).returncode):
                OUT.open("a").write(json.dumps({"repo": k[0], "pr": k[1], "skipped": "could not rebuild"}) + "\n"); continue
            per_file, ops = {}, {}
            for f, lines in added(patch).items():
                if not (repo / f).is_file():
                    continue
                cfg, db = tmp / "c.toml", tmp / "s.sqlite"
                cfg.write_text(f'[cosmic-ray]\nmodule-path = {json.dumps(f)}\ntimeout = 10.0\nexcluded-modules = []\ntest-command = "true"\n\n[cosmic-ray.distributor]\nname = "local"\n')
                if db.exists():
                    db.unlink()
                p = subprocess.run([CR, "init", str(cfg), str(db)], cwd=repo, capture_output=True, text=True, timeout=300)
                if p.returncode:
                    per_file[f] = {"added_lines": len(lines), "error": (p.stderr or p.stdout)[-80:]}; continue
                c = sqlite3.connect(db)
                rs = c.execute(f"select operator_name from mutation_specs where start_pos_row in ({','.join(map(str, lines)) or '-1'})").fetchall()
                for (o,) in rs:
                    ops[o] = ops.get(o, 0) + 1
                per_file[f] = {"added_lines": len(lines), "candidates": len(rs)}
            res = {"repo": k[0], "pr": k[1], "files": per_file, "candidates": sum(v.get("candidates", 0) for v in per_file.values()), "added_lines": sum(v["added_lines"] for v in per_file.values()), "operators": ops}
            OUT.open("a").write(json.dumps(res) + "\n")
            print(f"{k[0]}#{k[1]}: {res['added_lines']} added lines -> {res['candidates']} candidate mutants", flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
