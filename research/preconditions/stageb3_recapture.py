"""POST-HOC (not registered): re-replay the 11 valid Stage B3 runs from the saved patch with a FULLER capture of the agent's environment, to separate "capture is weak" from
"capture cannot work". Fuller capture = the agent's saved `pip freeze` with (1) setuptools and wheel KEPT (B3's filter dropped them), (2) the project's OWN distribution removed (it
shadowed the patched source), (3) editable and direct-URL entries still dropped (not re-installable), and the replay's isolation check no longer treats a plain folder as project code.
Runs that created untracked files cannot be reconstructed from the patch and are skipped. Usage: python3 research/preconditions/stageb3_recapture.py [stage=stageb3] [max_venv_gb=0.7] [pr,pr,...]  (stage stageb3|stageb5; a larger size limit tests whether the replay's 700 MB guard caused failures)"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import os
os.environ["CAPTURE"] = "1"
import stageb_run as sb  # noqa: E402
import run_pilot as rp  # noqa: E402
from agentvow import envsetup  # noqa: E402

D = ROOT / "data" / "preconditions"
STAGE = sys.argv[1] if len(sys.argv) > 1 else "stageb3"
os.environ["AGENTVOW_MAX_ENV_MB"] = str(int(float(sys.argv[2] if len(sys.argv) > 2 else 0.7) * 1024))   # inherited by the replay subprocess
envsetup.MAX_VENV = int(float(sys.argv[2] if len(sys.argv) > 2 else 0.7) * 1024**3)
ONLY = {int(x) for x in sys.argv[3].split(",")} if len(sys.argv) > 3 else None


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def main():
    rows = [json.loads(l) for l in (D / f"{STAGE}_results.jsonl").read_text().splitlines()]
    tasks = {(j["repo"], j["pr"]): j for j in map(json.loads, (D / f"{STAGE}_tasks.jsonl").read_text().splitlines())}
    valid = [r for r in rows if r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env")]
    out = []
    for r in valid:
        if ONLY is not None and int(r["pr"]) not in ONLY:
            continue
        c = tasks[(r["repo"], r["pr"])]; rd = Path(r["run_dir"])
        status = (rd / "status.txt").read_text()
        unt = [l[3:] for l in status.splitlines() if l.startswith("??") and not l[3:].startswith((".agentvow", ".pytest_cache", "__pycache__")) and not l[3:].endswith((".pyc", ".json"))]
        if unt:
            print(f"{r['repo']}#{r['pr']}: skipped (untracked files not in the patch: {unt[:2]})"); continue
        tmp = Path(tempfile.mkdtemp(prefix="recap_"))
        try:
            repo, base_sha = sb.prepare(c, tmp)
            if sb.sh(["git", "apply", "--whitespace=nowarn", str(rd / "patch.diff")], repo).returncode:
                print(f"{r['repo']}#{r['pr']}: patch did not apply"); continue
            own = norm(str(envsetup._project_name(repo) or ""))
            keep = []
            for l in (rd / "pipfreeze_agent.txt").read_text().splitlines():
                if not l or l.startswith("-e") or " @ " in l or l.lower().startswith("pip=="):
                    continue
                if own and norm(re.split(r"[=<>!~ \[]", l, maxsplit=1)[0]) == own:
                    continue
                keep.append(l)
            (repo / ".agentvow-freeze2.txt").write_text("\n".join(keep) + "\n")
            try:
                env = json.loads(r.get("recipe_text") or "{}").get("env", {}) if r.get("recipe_text") else {}
            except ValueError:
                env = {}
            env = {k: v for k, v in env.items() if k not in ("HOME", "TMPDIR", "TEMP", "TMP", "PATH") and not k.startswith("PYTHON")}
            rec = {"schema": "agentvow-recipe/1", "setup": ["pip install -r .agentvow-freeze2.txt"], "test": "pytest -q " + " ".join(c["target_files"]), "env": env}
            (repo / ".agentvow-freeze2-recipe.json").write_text(json.dumps(rec))
            msg = tmp / "m.txt"; msg.write_text((rd / "final.txt").read_text())
            new = rp.replay(repo, base_sha, msg, ["--recipe", str(repo / ".agentvow-freeze2-recipe.json"), "--test-timeout", "600"])
            ev = new.get("evidence") or {}
            old = ((r.get("freeze_replay") or {}).get("evidence") or {}).get("result")
            print(f"{r['repo']}#{r['pr']}: capture {old} -> fuller capture {ev.get('result')} (own dist dropped: {own or '-'}) {str(ev.get('summary'))[:110]}", flush=True)
            out.append({"run": f"{r['repo']}#{r['pr']}", "old": old, "new": ev.get("result"), "summary": ev.get("summary")})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    (D / f"{STAGE}_recapture.json").write_text(json.dumps(out, indent=1))
    print("fuller capture reproduces", sum(o["new"] == "pass" for o in out), "of", len(out), "reconstructable valid runs;", "of", len(valid), "valid in all")


if __name__ == "__main__":
    main()
