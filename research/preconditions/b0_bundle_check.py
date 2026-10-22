"""Gate B0 of docs/strategy/STAGE1_CAPTURE_PLAN.md on the 16 re-runnable valid B6 runs: (1) the portable capture bundle made from each run's recorded packages is accepted by the key-less verifier
(`check --from-capture`) and its replay result equals the registered capture replay result; (2) injected stale or foreign bundles (four kinds, 16 runs each) are refused at the binding step, before any replay;
(3) no environment value reaches a bundle. Usage: python3 research/preconditions/b0_bundle_check.py   (writes data/preconditions/stageb6_b0.jsonl; resumable)"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["CAPTURE"] = "1"; os.environ["B6"] = "1"; os.environ["AGENTVOW_MAX_ENV_MB"] = "3072"
import stageb_run as sb  # noqa: E402
from agentvow import bundle, cli, envsetup, reality  # noqa: E402

D = ROOT / "data" / "preconditions"
OUT = D / "stageb6_b0.jsonl"
envsetup.MAX_VENV = 3 * 1024**3
SECRET = "b0-planted-secret-value-9f3a"
os.environ["B0_SECRET_TOKEN"] = SECRET   # present in the process that exports and verifies: it must never reach a bundle


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def pins(rd, repo):
    own = norm(str(envsetup._project_name(repo) or ""))
    return [l for l in (rd / "pipfreeze_agent.txt").read_text().splitlines()
            if l and not l.startswith("-e") and " @ " not in l and not l.lower().startswith("pip==") and not (own and norm(re.split(r"[=<>!~ \[]", l, maxsplit=1)[0]) == own)
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?==[A-Za-z0-9._+!*-]+", l)]


def verify(repo, base, bpath, msg, targets):
    os.environ["AGENTVOW_HOME"] = tempfile.mkdtemp(prefix="b0h_")
    old = sys.stdin, sys.stdout, sys.stderr
    sys.stdin, out, sys.stderr = io.StringIO(msg), io.StringIO(), io.StringIO()
    sys.stdout = out
    try:
        cli.main(["check", "--repo", str(repo), "--base", base, "--run-tests", "--from-capture", str(bpath), "--json", "--test-timeout", "600", "--test-cmd", "{py} -m pytest -q -rA -p no:cacheprovider " + " ".join(targets)])
    finally:
        sys.stdin, sys.stdout, sys.stderr = old
    o = json.loads(out.getvalue())
    t = next(x for x in o["findings"] if x["kind"] == "tests_pass")
    evs = sorted((Path(repo) / ".agentvow" / "evidence").glob("testrun_*.json"), key=lambda q: q.stat().st_mtime)
    e = json.loads(evs[-1].read_text()) if evs else {}
    return t["verdict"], (e.get("evidence", e) or {}).get("result"), t.get("why", "")


def main():
    rows = [json.loads(l) for l in (D / "stageb6_results.jsonl").read_text().splitlines()]
    tasks = {(j["repo"], j["pr"]): j for j in map(json.loads, (D / "stageb6_tasks.jsonl").read_text().splitlines())}
    valid = [r for r in rows if r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env") and ((r.get("freeze_replay") or {}).get("evidence") or {}).get("result") == "pass"]
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    foreign = None
    for r in valid:
        key = (r["repo"], r["pr"])
        if key in done:
            continue
        if shutil.disk_usage(D).free < 3.5 * 1024**3:
            print("low disk; stopping", flush=True); return
        c = tasks[key]; rd = Path(r["run_dir"])
        rec = {"repo": r["repo"], "pr": r["pr"]}
        status = (rd / "status.txt").read_text()
        unt = [l[3:] for l in status.splitlines() if l.startswith("??") and not l[3:].startswith((".agentvow", ".pytest_cache", "__pycache__")) and not l[3:].endswith((".pyc", ".json"))]
        if unt:
            rec["outcome"] = "not_rerunnable"; OUT.open("a").write(json.dumps(rec) + "\n"); print(key, "not re-runnable", flush=True); continue
        tmp = Path(tempfile.mkdtemp(prefix="b0_"))
        try:
            repo, base = sb.prepare(c, tmp)
            if repo is None or sb.sh(["git", "apply", "--whitespace=nowarn", str(rd / "patch.diff")], repo).returncode:
                rec["outcome"] = "not_rerunnable"; OUT.open("a").write(json.dumps(rec) + "\n"); print(key, "base/patch failed", flush=True); continue
            tree = reality.git_tree_hash(repo)
            snap = reality.snapshot(repo)
            capsule_rec = {"packages": pins(rd, repo), "python_version": "3.13.5", "platform": "Darwin", "created_at": "b0", "source": "b0", "command": "pytest", "commit": snap.commit, "git_tree": tree}
            b = bundle.export(capsule_rec)
            rec["secret_in_bundle"] = SECRET in json.dumps(b)
            bpath = tmp / "bundle.json"; bpath.write_text(json.dumps(b))
            # (2) negatives: refused at the binding step (no replay)
            neg = {}
            tracked = next((f for f in subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True).stdout.split() if f.endswith(".py")), None)
            if tracked:
                p = repo / tracked; orig = p.read_text(errors="replace"); p.write_text(orig + "\n# edited after capture\n")
                neg["edited_after"] = bundle.bind(repo, b)[0] is None; p.write_text(orig)
            (repo / "late_untracked.py").write_text("x = 1\n"); neg["untracked_after"] = bundle.bind(repo, b)[0] is None; (repo / "late_untracked.py").unlink()
            if foreign is not None:
                neg["foreign_bundle"] = bundle.bind(repo, foreign)[0] is None
            neg["bound_before_negatives_restored"] = bundle.bind(repo, b)[1] == ""
            rec["negatives"] = neg
            foreign = b
            # (1) positive: key-less verifier replays from the bundle
            msg = tmp / "m.txt"; msg.write_text((rd / "final.txt").read_text())
            verdict, result, scope = verify(repo, base, bpath, (rd / "final.txt").read_text(), c["target_files"])
            rec.update(outcome="ran", verifier_verdict=verdict, verifier_result=result, registered_capture="pass", says_unauthenticated="NOT authenticated" in scope, secret_in_finding=SECRET in scope)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        OUT.open("a").write(json.dumps(rec) + "\n")
        print(f"{key}: verifier result {rec.get('verifier_result')} | negatives {rec.get('negatives')} | secret {rec.get('secret_in_bundle')}", flush=True)


if __name__ == "__main__":
    main()
