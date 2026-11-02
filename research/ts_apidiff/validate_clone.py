"""Run the shipped TypeScript engine (agentvow.ts_api.check) on real flagged pull requests: shallow, fetch-only clones (no install, no scripts, hooks disabled), one repository at a time, deleted afterwards.
Usage: AGENTVOW_TYPESCRIPT=<node_modules dir> python3 research/ts_apidiff/validate_clone.py <scratch_dir>   (reads <scratch_dir>/ts_bakeoff.json from run.py)"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentvow import ts_api  # noqa: E402

G = ["git", "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never", "-c", "core.fsmonitor=false"]


def sh(args, cwd, timeout=400):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def main():
    scratch = Path(sys.argv[1])
    kind = os.environ.get("KIND", "ts")
    d = json.load(open(scratch / ("ts_bakeoff.json" if kind == "ts" else "ts_bakeoff_js.json")))
    cheap = {json.loads(l)["pr"]: json.loads(l) for l in (ROOT / "data/shadow2/cheap.jsonl").read_text().splitlines()}
    out = []
    for x in d:
        if not any(f.get("breaking") for f in x["files"]):
            continue
        c = cheap[x["pr"]]; work = scratch / "clone"
        shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
        files = [f["file"] for f in x["files"]]
        rec = {"pr": x["pr"], "repo": x["repo"], "old_flagged": [f["file"] for f in x["files"] if f.get("breaking")]}
        try:
            sh(G + ["init", "-q"], work)
            sh(G + ["remote", "add", "origin", f"https://github.com/{x['repo']}.git"], work)
            r1 = sh(G + ["fetch", "-q", "--depth", "1", "origin", c["base"]], work)
            r2 = sh(G + ["fetch", "-q", "--depth", "1", "origin", c["head"]], work)
            if r1.returncode or r2.returncode:
                r2 = sh(G + ["fetch", "-q", "--depth", "1", "origin", f"pull/{c['number']}/head"], work)
            if r1.returncode or r2.returncode:
                rec["error"] = "fetch failed: " + (r1.stderr or r2.stderr)[:120]
            else:
                sh(G + ["checkout", "-q", "--detach", "FETCH_HEAD" if r2.returncode == 0 and False else c["head"]], work)
                found, gaps, skipped = ts_api.check(work, c["base"], [f for f in files if ts_api.is_candidate(f)])
                rec.update({"found": found[:6], "gaps": gaps[:4], "skipped": skipped[:4]})
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {str(e)[:100]}"
        shutil.rmtree(work, ignore_errors=True)
        out.append(rec)
        print(x["repo"], "found" if rec.get("found") else ("error" if rec.get("error") else "none"), flush=True)
    (scratch / ("validate_clone.json" if kind == "ts" else "validate_clone_js.json")).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
