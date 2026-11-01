"""Run exports.js over the TypeScript shadow-pool pull requests that make a backward-compatibility claim (docs/research/API_DIFF_TS_PROTOTYPE.md).
Same inputs as the Python bake-off: each changed .ts/.tsx file that existed at the base commit, base text against head text from the GitHub contents API; nothing is installed from the repository or run.
Usage: NODE_PATH=<dir with typescript> python3 research/ts_apidiff/run.py <scratch_dir>"""
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research/shadow2"))
from common import gh  # noqa: E402

TEST = re.compile(r"(^|/)(__tests__|__mocks__|tests?|spec|e2e|stories|fixtures?)(/|$)|\.(test|spec|stories)\.[jt]sx?$|\.d\.ts$")


def raw(repo, path, ref):
    r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw", f"repos/{repo}/contents/{urllib.parse.quote(path)}?ref={ref}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 and len(r.stdout) < 600_000 else None


def main():
    scratch = Path(sys.argv[1]); scratch.mkdir(parents=True, exist_ok=True)
    cheap = [json.loads(l) for l in (ROOT / "data/shadow2/cheap.jsonl").read_text().splitlines()]
    units = [x for x in cheap if "head" in x and not x["changes_python"] and any(c["kind"] == "backward_compatible" for c in x["claims"])]
    out = []
    for i, x in enumerate(units):
        o, n = x["repo"].split("/")
        files = gh(f"repos/{o}/{n}/pulls/{x['number']}/files?per_page=100")
        if not isinstance(files, list):
            continue
        ts_files = [f for f in files if re.search(r"\.tsx?$", f["filename"]) and not TEST.search(f["filename"]) and f["status"] in ("modified", "removed", "renamed")]
        if not ts_files:
            continue
        rec = {"pr": x["pr"], "repo": x["repo"], "files": []}
        for f in ts_files[:30]:
            fn = f["filename"]; old = raw(x["repo"], f.get("previous_filename", fn), x["base"])
            if old is None:
                rec["files"].append({"file": fn, "note": "base unreadable"}); continue
            if f["status"] == "removed":
                rec["files"].append({"file": fn, "breaking": [f"removed file: {fn}"], "changed": [], "gaps": []}); continue
            new = raw(x["repo"], fn, x["head"])
            if new is None:
                rec["files"].append({"file": fn, "note": "head unreadable"}); continue
            p = subprocess.run(["node", str(ROOT / "agentvow/ts/exports.js")], input=json.dumps({"old": old, "new": new, "file": fn}), capture_output=True, text=True, env=os.environ, timeout=60)
            try:
                rec["files"].append({"file": fn, **json.loads(p.stdout)})
            except Exception:
                rec["files"].append({"file": fn, "note": "tool failure: " + p.stderr[:100]})
        out.append(rec)
        if i % 25 == 0:
            print(i, len(units), flush=True)
    (scratch / "ts_bakeoff.json").write_text(json.dumps(out, indent=1))
    print("done", len(out))


if __name__ == "__main__":
    main()
