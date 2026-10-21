"""E5 of docs/strategy/PRODUCT_EXPLORATION_2026-10.md section 7: plant a fault in the agent's final code, keep the claim "All tests pass.", and replay under (a) the captured environment (the agent's pip freeze) and
(b) the project-native baseline (agentvow/baseline.py). Which contexts turn a false claim into CONTRADICTED, which stay UNKNOWN? Faults are authored by us (operator flips on lines the agent added), so this is pipeline
sensitivity per context, not real-world detection. Usage: python3 research/preconditions/b6_fault_injection.py   (resumable; writes data/preconditions/stageb6_faults.jsonl)"""
import json
import os
import random
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
from agentvow import baseline, envsetup, reality  # noqa: E402

D = ROOT / "data" / "preconditions"
OUT = D / "stageb6_faults.jsonl"
envsetup.MAX_VENV = 3 * 1024**3
SEED = 20261022
OPS = [(" == ", " != "), (" != ", " == "), (" < ", " >= "), (" > ", " <= "), ("return True", "return False"), ("return False", "return True"), (" and ", " or "), (" in ", " not in ")]


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def added_lines(repo, base_sha, f):
    out = subprocess.run(["git", "-C", str(repo), "diff", "-U0", base_sha, "--", f], capture_output=True, text=True).stdout
    nums = []
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", out, re.M):
        start, n = int(m.group(1)), int(m.group(2) or 1)
        nums += range(start, start + n)
    return nums


def candidates(repo, base_sha):
    files = [f for f in subprocess.run(["git", "-C", str(repo), "diff", "--name-only", base_sha], capture_output=True, text=True).stdout.split()
             if f.endswith(".py") and not reality.is_test(f) and Path(f).name not in ("__main__.py", "setup.py", "conftest.py") and (repo / f).is_file()]
    cands = []
    for f in files:
        src = (repo / f).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        for ln in added_lines(repo, base_sha, f):
            if 0 < ln <= len(src) and not src[ln - 1].lstrip().startswith(("#", '"', "'")):
                for a, z in OPS:
                    if a in src[ln - 1]:
                        cands.append((f, ln, a, z))
    return cands


def check(repo, base_sha, msg, recipe_path):
    env = {**os.environ, "AGENTVOW_HOME": str(D / "agentvow_home")}
    env.pop("PYTHONPATH", None)
    p = subprocess.run([sys.executable, "-m", "agentvow.cli", "check", "--repo", str(repo), "--base", base_sha, "--transcript", str(msg), "--json", "--new-test-failures", "review",
                        "--recipe", str(recipe_path), "--test-timeout", "600"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=1500)
    try:
        o = json.loads(p.stdout)
        f = next(x for x in o["findings"] if x["kind"] == "tests_pass")
        return {"verdict": f["verdict"], "status": o.get("status"), "detail": str(f.get("summary") or f.get("detail") or "")[:240], "exit": p.returncode}
    except (ValueError, StopIteration, KeyError):
        return {"verdict": None, "status": None, "detail": (p.stdout + p.stderr)[-200:], "exit": p.returncode}


def main():
    rows = [json.loads(l) for l in (D / "stageb6_results.jsonl").read_text().splitlines()]
    tasks = {(j["repo"], j["pr"]): j for j in map(json.loads, (D / "stageb6_tasks.jsonl").read_text().splitlines())}
    valid = [r for r in rows if r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env") and ((r.get("freeze_replay") or {}).get("evidence") or {}).get("result") == "pass"]
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
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
            rec["outcome"] = "not_rerunnable"; OUT.open("a").write(json.dumps(rec) + "\n"); print(f"{key}: not re-runnable", flush=True); continue
        tmp = Path(tempfile.mkdtemp(prefix="fault_"))
        try:
            repo, base_sha = sb.prepare(c, tmp)
            if repo is None or sb.sh(["git", "apply", "--whitespace=nowarn", str(rd / "patch.diff")], repo).returncode:
                rec["outcome"] = "not_rerunnable"; OUT.open("a").write(json.dumps(rec) + "\n"); print(f"{key}: base/patch failed", flush=True); continue
            cands = candidates(repo, base_sha)
            if not cands:
                rec["outcome"] = "no_plantable_line"; OUT.open("a").write(json.dumps(rec) + "\n"); print(f"{key}: no plantable line", flush=True); continue
            f, ln, a, z = random.Random(f"{SEED}:{r['repo']}:{r['pr']}").choice(sorted(cands))
            own = norm(str(envsetup._project_name(repo) or ""))
            keep = [l for l in (rd / "pipfreeze_agent.txt").read_text().splitlines()
                    if l and not l.startswith("-e") and " @ " not in l and not l.lower().startswith("pip==") and not (own and norm(re.split(r"[=<>!~ \[]", l, maxsplit=1)[0]) == own)]
            (repo / ".fault-freeze.txt").write_text("\n".join(keep) + "\n")
            try:
                env = json.loads(r.get("recipe_text") or "{}").get("env", {}) if r.get("recipe_text") else {}
            except ValueError:
                env = {}
            env = {k: v for k, v in env.items() if k not in ("HOME", "TMPDIR", "TEMP", "TMP", "PATH") and not k.startswith("PYTHON")}
            test = "pytest -q " + " ".join(c["target_files"])
            (repo / ".fault-cap.json").write_text(json.dumps({"schema": "agentvow-recipe/1", "setup": ["pip install -r .fault-freeze.txt"], "test": test, "env": env}))
            ps, pe, pnotes = baseline.derive(repo)
            (repo / ".fault-native.json").write_text(json.dumps({"schema": "agentvow-recipe/1", "setup": ps, "test": test, "env": pe}))
            msg = tmp / "m.txt"; msg.write_text("All tests pass.\n")
            # the fault: one operator flip on a line the agent added
            p = repo / f
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            lines[ln - 1] = lines[ln - 1].replace(a, z, 1)
            p.write_text("".join(lines))
            rec["fault"] = f"{f}:{ln} '{a.strip()}'->'{z.strip()}'"
            rec["captured"] = check(repo, base_sha, msg, repo / ".fault-cap.json")
            rec["native"] = check(repo, base_sha, msg, repo / ".fault-native.json")
            rec["outcome"] = "ran"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        OUT.open("a").write(json.dumps(rec) + "\n")
        print(f"{key}: fault {rec.get('fault')} | captured {rec.get('captured', {}).get('verdict')} | native {rec.get('native', {}).get('verdict')}", flush=True)


if __name__ == "__main__":
    main()
