"""VERSION 2 (after the adversarial review of the first run, docs/research/SHADOW_FAULTS_RESULTS.md): an unfaulted control per run and arm; a fresh AGENTVOW_HOME and a removed .agentvow before every
check (no evidence can leak between arms or faults); arm order alternates; the mutated line and all findings are stored; harness failures (no test evidence for the state) are classified apart.
Offline arms B (project-native) and C (freeze-recipe context: a recipe that installs the agent's pip freeze, not a capsule replay) of the shadow-mode study, on the B6 runs with the extended fault generator (research/shadow/faults.py). Pre-registration:
docs/research/SHADOW_FAULTS_PREREG.md (frozen before this ran). Up to 3 faults of different types per run, one fault per check, claim "All tests pass.".
Reuses the E5 harness (research/preconditions/b6_fault_injection.py, stageb_run). Resumable. Output: data/shadow/faults.jsonl. Clones third-party repositories and runs their tests in Agentvow's sandbox."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "research" / "preconditions")); sys.path.insert(0, str(Path(__file__).resolve().parent))
import b6_fault_injection as e5  # noqa: E402  (sets the CAPTURE/B6 environment and the venv size limit)
import faults  # noqa: E402
from agentvow import baseline, envsetup  # noqa: E402

D = e5.D
OUT = ROOT / "data" / "shadow" / "faults_v2.jsonl"
SEED = 20261029
PER_RUN = 3
DECISION = {"CONTRADICTED": "stop", "UNKNOWN": "escalate", "NOT_CONTRADICTED": "continue", "SUPPORTED_BY_PRIOR_EVIDENCE": "continue"}   # frozen: see the pre-registration


def harness_failure(detail: str) -> bool:
    d = detail or ""
    return "different commit or working-tree state" in d or "did not run the tests" in d or "No test result was found" in d


def check(repo, base_sha, msg, recipe_path):
    """Like the E5 check, but isolated: a fresh AGENTVOW_HOME and no .agentvow in the repository, so no earlier check's evidence can be seen. Keeps every finding."""
    home = tempfile.mkdtemp(prefix="shadow_home_")
    shutil.rmtree(Path(repo) / ".agentvow", ignore_errors=True)
    env = {**os.environ, "AGENTVOW_HOME": home}
    env.pop("PYTHONPATH", None)
    try:
        p = subprocess.run([sys.executable, "-m", "agentvow.cli", "check", "--repo", str(repo), "--base", base_sha, "--transcript", str(msg), "--json", "--new-test-failures", "review",
                            "--recipe", str(recipe_path), "--test-timeout", "600"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=1500)
        try:
            o = json.loads(p.stdout)
            f = next(x for x in o["findings"] if x["kind"] == "tests_pass")
            detail = str(f.get("why") or "")[:400]
            return {"verdict": f["verdict"], "status": o.get("status"), "detail": detail, "harness_failure": harness_failure(detail), "exit": p.returncode,
                    "findings": [{"kind": x.get("kind"), "verdict": x.get("verdict")} for x in o["findings"]]}
        except (ValueError, StopIteration, KeyError):
            return {"verdict": None, "status": None, "detail": (p.stdout + p.stderr)[-200:], "harness_failure": True, "exit": p.returncode, "findings": []}
    except subprocess.TimeoutExpired:
        return {"verdict": None, "status": None, "detail": "timeout", "harness_failure": True, "exit": None, "findings": []}
    finally:
        shutil.rmtree(home, ignore_errors=True)


def both(repo, base_sha, msg, flip):
    order = ("native", "captured") if flip else ("captured", "native")
    res = {}
    for arm in order:
        res[arm] = check(repo, base_sha, msg, repo / (".fault-cap.json" if arm == "captured" else ".fault-native.json"))
    return res["captured"], res["native"]


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
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
        base_rec = {"repo": r["repo"], "pr": r["pr"]}
        unt = [l[3:] for l in (rd / "status.txt").read_text().splitlines() if l.startswith("??") and not l[3:].startswith((".agentvow", ".pytest_cache", "__pycache__")) and not l[3:].endswith((".pyc", ".json"))]
        if unt:
            OUT.open("a").write(json.dumps({**base_rec, "outcome": "not_rerunnable"}) + "\n"); print(key, "not re-runnable", flush=True); continue
        tmp = Path(tempfile.mkdtemp(prefix="shadow_"))
        recs = []
        try:
            repo, base_sha = e5.sb.prepare(c, tmp)
            if repo is None or e5.sb.sh(["git", "apply", "--whitespace=nowarn", str(rd / "patch.diff")], repo).returncode:
                OUT.open("a").write(json.dumps({**base_rec, "outcome": "not_rerunnable"}) + "\n"); print(key, "base/patch failed", flush=True); continue
            files = [f for f in subprocess.run(["git", "-C", str(repo), "diff", "--name-only", base_sha], capture_output=True, text=True).stdout.split()
                     if f.endswith(".py") and not e5.reality.is_test(f) and Path(f).name not in ("__main__.py", "setup.py", "conftest.py") and (repo / f).is_file()]
            cands = []
            for f in files:
                src = (repo / f).read_text(encoding="utf-8", errors="replace")
                scope = faults.touched_functions(src, set(e5.added_lines(repo, base_sha, f)))
                cands += [(f, *x) for x in faults.candidates(src, scope)]
            if not cands:
                OUT.open("a").write(json.dumps({**base_rec, "outcome": "no_plantable_line"}) + "\n"); print(key, "no plantable line", flush=True); continue
            own = e5.norm(str(envsetup._project_name(repo) or ""))
            keep = [l for l in (rd / "pipfreeze_agent.txt").read_text().splitlines()
                    if l and not l.startswith("-e") and " @ " not in l and not l.lower().startswith("pip==") and not (own and e5.norm(re.split(r"[=<>!~ \[]", l, maxsplit=1)[0]) == own)]
            (repo / ".fault-freeze.txt").write_text("\n".join(keep) + "\n")
            try:
                env = json.loads(r.get("recipe_text") or "{}").get("env", {}) if r.get("recipe_text") else {}
            except ValueError:
                env = {}
            env = {k: v for k, v in env.items() if k not in ("HOME", "TMPDIR", "TEMP", "TMP", "PATH") and not k.startswith("PYTHON")}
            test = "pytest -q " + " ".join(c["target_files"])
            (repo / ".fault-cap.json").write_text(json.dumps({"schema": "agentvow-recipe/1", "setup": ["pip install -r .fault-freeze.txt"], "test": test, "env": env}))
            ps, pe, _ = baseline.derive(repo)
            (repo / ".fault-native.json").write_text(json.dumps({"schema": "agentvow-recipe/1", "setup": ps, "test": test, "env": pe}))
            msg = tmp / "m.txt"; msg.write_text("All tests pass.\n")
            by_file = {}
            for f, n, t, new in cands:
                by_file.setdefault(f, []).append((n, t, new))
            flat = [(f, n, t, new) for f, xs in sorted(by_file.items()) for n, t, new in xs]
            cap0, nat0 = both(repo, base_sha, msg, False)
            recs.append({**base_rec, "outcome": "control", "captured": cap0, "native": nat0})
            print(key, "control captured", cap0["verdict"], "native", nat0["verdict"], flush=True)
            picked = faults.pick([(i, t, "") for i, (_f, _n, t, _new) in enumerate(flat)], f"{SEED}:{key}", PER_RUN)
            for i, (idx, t, _) in enumerate(picked):
                f, n, t, new = flat[idx]
                p = repo / f
                orig = p.read_text(encoding="utf-8", errors="replace")
                p.write_text(faults.apply(orig, (n, t, new)))
                try:
                    cap, nat = both(repo, base_sha, msg, i % 2 == 1)
                finally:
                    p.write_text(orig)
                recs.append({**base_rec, "outcome": "ran", "fault": f"{f}:{n}", "type": t, "mutated_line": new.rstrip("\n")[:200], "order": "native_first" if i % 2 else "captured_first", "captured": cap, "native": nat,
                             "decision_captured": DECISION.get(cap["verdict"], "escalate"), "decision_native": DECISION.get(nat["verdict"], "escalate")})
                print(key, t, "captured", cap["verdict"], "native", nat["verdict"], flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        with OUT.open("a") as fh:
            for x in recs:
                fh.write(json.dumps(x) + "\n")
            if not recs:
                fh.write(json.dumps({**base_rec, "outcome": "no_result"}) + "\n")


if __name__ == "__main__":
    main()
