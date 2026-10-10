"""For each Stage B1 agent patch: rebuild the task (base + target tests + the saved patch), build the zero-config environment, run the target tests under coverage in the sandbox, and
measure which ADDED source lines the independently passing tests execute. This turns "the tests pass" into a per-change statement: how much of what the agent changed was actually
exercised by evidence a verifier controls. Lines are the unit (symbols are approximate); deleted-only changes cannot be measured. Post-hoc analysis, not part of any registered protocol.
Usage: python3 research/preconditions/coverage_of_changes.py [max_tasks] -> data/preconditions/coverage_of_changes.jsonl (resumable)"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import stageb_run as sb  # noqa: E402
from agentvow import envsetup, runner  # noqa: E402
from count_review_items import TESTY, DOCY  # noqa: E402

D = ROOT / "data" / "preconditions"
OUT = D / "coverage_of_changes.jsonl"


def added_lines(patch: str) -> dict:
    """{file: set of new-side line numbers of added lines}"""
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
        elif ln.startswith("-"):
            continue
        else:
            n += 1
    return out


def one(c, r):
    tmp = Path(tempfile.mkdtemp(prefix="cov_"))
    rec = {"repo": r["repo"], "pr": r["pr"]}
    try:
        rd = Path(r["run_dir"]); patch = (rd / "patch.diff").read_text()
        repo, base_sha = sb.prepare(c, tmp)
        if repo is None:
            return {**rec, "stage": base_sha}
        if patch.strip() and sb.sh(["git", "apply", "--whitespace=nowarn", str(rd / "patch.diff")], repo).returncode:
            return {**rec, "stage": "patch_did_not_apply"}
        venv, home = tmp / "venv", tmp / "home"
        py, notes, aborted = envsetup.build_env(repo, venv, home)
        if not py or aborted:
            return {**rec, "stage": "no_env", "note": "; ".join(notes)[:100]}
        rc, out = envsetup._pip(Path(venv), repo, Path(home), ["install", "-q", "coverage"], 300, envsetup.MAX_VENV, envsetup.MIN_FREE)
        if rc:
            return {**rec, "stage": "coverage_not_installed"}
        rcfile = tmp / "empty.rc"; rcfile.write_text("[run]\n")
        data = repo / ".agentvow" / "cov"; data.parent.mkdir(exist_ok=True)
        argv = [py, "-m", "coverage", "run", "--rcfile", str(rcfile), "--data-file", str(data), "-m", "pytest", "-q", "-p", "no:cacheprovider", *c["target_files"]]
        res = runner.run_tests(repo, argv, timeout=600, write=False)
        rec["tests"] = res.get("result")
        js = tmp / "cov.json"
        sb.sh([py, "-m", "coverage", "json", "--rcfile", str(rcfile), "--data-file", str(data), "-o", str(js)], repo)
        cov = json.loads(js.read_text()).get("files", {}) if js.exists() else {}
        by_rel = {}
        for k, v in cov.items():
            p = Path(k)
            try:
                by_rel[str(p.resolve().relative_to(repo.resolve()))] = v
            except ValueError:
                by_rel[k] = v
        total = executed = 0; per = {}
        for f, lines in added_lines(patch).items():
            if TESTY.search(f) or DOCY.search(f) or not f.endswith(".py"):
                continue
            v = by_rel.get(f)
            if v is None:
                per[f] = {"added": len(lines), "executable": None, "executed": 0, "in_coverage": False}; continue
            ex, miss = set(v.get("executed_lines", [])), set(v.get("missing_lines", []))
            exe = {l for l in lines if l in ex or l in miss}
            per[f] = {"added": len(lines), "executable": len(exe), "executed": len({l for l in exe if l in ex}), "in_coverage": True}
            total += len(exe); executed += len({l for l in exe if l in ex})
        return {**rec, "stage": "done", "added_executable": total, "added_executed": executed, "files": per,
                "files_not_imported": sum(1 for p in per.values() if not p["in_coverage"])}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(limit=40):
    rows = [json.loads(l) for l in (D / "stageb_results.jsonl").read_text().splitlines() if l.strip()]
    valid = {(j["repo"], j["pr"]): j for j in map(json.loads, (D / "stageb_validated.jsonl").read_text().splitlines()) if j["valid"]}
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    n = 0
    for r in rows:
        k = (r["repo"], r["pr"])
        if k in done or n >= limit or not r.get("run_dir"):
            continue
        res = one(valid[k], r); n += 1
        OUT.open("a").write(json.dumps(res) + "\n")
        print(f"[{n}] {k[0]}#{k[1]}: {res.get('stage')} executed {res.get('added_executed')}/{res.get('added_executable')} tests={res.get('tests')}", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
