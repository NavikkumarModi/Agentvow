"""Post-hoc: re-replay B1 runs with the fixed instrument from the SAVED patch and recipe (no agent). New untracked files are not in the saved patch, so
runs that created files cannot be reconstructed faithfully and are skipped (reported). Usage: python3 research/preconditions/stageb_rereplay.py"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import stageb_run as sb  # noqa: E402
import run_pilot as rp  # noqa: E402

D = ROOT / "data" / "preconditions"


def main():
    rows = [json.loads(l) for l in (D / "stageb_results.jsonl").read_text().splitlines()]
    valid = {(j["repo"], j["pr"]): j for j in map(json.loads, (D / "stageb_validated.jsonl").read_text().splitlines()) if j["valid"]}
    targets = [r for r in rows if r["truth_in_agent_env"] == "pass" and ((r.get("recipe_replay") or {}).get("evidence") or {}).get("result") != "pass"]
    for r in targets:
        c = valid[(r["repo"], r["pr"])]
        rd = Path(r["run_dir"])
        status = (rd / "status.txt").read_text()
        untracked = [l[3:] for l in status.splitlines() if l.startswith("??") and not l[3:].startswith((".agentvow", ".pytest_cache", "__pycache__"))]
        old = ((r.get("recipe_replay") or {}).get("evidence") or {}).get("result")
        if not (rd / "recipe.json").read_text().strip():
            print(f"{r['repo']}#{r['pr']}: no recipe saved"); continue
        if untracked and any(not u.endswith(("/", ".json", ".pyc")) for u in untracked):
            print(f"{r['repo']}#{r['pr']}: skipped (agent created files that the saved patch does not contain: {untracked[:3]})"); continue
        tmp = Path(tempfile.mkdtemp(prefix="rereplay_"))
        try:
            repo, base_sha = sb.prepare(c, tmp)
            ap = sb.sh(["git", "apply", "--whitespace=nowarn", str(rd / "patch.diff")], repo)
            if ap.returncode:
                print(f"{r['repo']}#{r['pr']}: patch did not apply ({ap.stderr[:60]})"); continue
            (repo / ".agentvow-recipe.json").write_text((rd / "recipe.json").read_text())
            msg = tmp / "m.txt"; msg.write_text((rd / "final.txt").read_text())
            new = rp.replay(repo, base_sha, msg, ["--recipe", str(repo / ".agentvow-recipe.json"), "--test-timeout", "600"])
            ev = (new.get("evidence") or {})
            # setup sufficiency, separated from the scope of the declared test command: same setup/prepare/env, test narrowed to the claimed target tests
            data = json.loads((rd / "recipe.json").read_text())
            data["test"] = "pytest -q " + " ".join(c["target_files"])
            (repo / ".agentvow-recipe-scoped.json").write_text(json.dumps(data))
            sc = rp.replay(repo, base_sha, msg, ["--recipe", str(repo / ".agentvow-recipe-scoped.json"), "--test-timeout", "600"])
            sev = (sc.get("evidence") or {})
            print(f"{r['repo']}#{r['pr']}: recipe replay was {old} -> now {ev.get('result')} (verdict {new.get('verdict')}) | with the test command scoped to the claimed tests: {sev.get('result')} {sev.get('summary','')[:60]}", flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
