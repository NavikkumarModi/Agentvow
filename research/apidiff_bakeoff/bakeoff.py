"""Bake-off (docs/research/API_DIFF_TOOLS_SURVEY.md, recommendation 3): griffe's breaking-change finder against agentvow/api_diff.py on the Python shadow-pool pull requests that make a backward-compatibility claim.
Both tools see exactly the same input: each changed .py file that existed at the base commit, at the base and at the head commit, downloaded through the GitHub contents API into a scratch directory and compared module by module (no package context, no installs, nothing from the repository is imported or run).
Outputs per pull request the findings of each tool, for hand adjudication of disagreements. Run with a Python that has griffe installed: <venv>/bin/python research/apidiff_bakeoff/bakeoff.py <scratch_dir>"""
import json
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research/shadow2"))
from agentvow import api_diff  # noqa: E402
from common import gh  # noqa: E402
import griffe  # noqa: E402


def raw(repo, path, ref):
    r = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github.raw", f"repos/{repo}/contents/{urllib.parse.quote(path)}?ref={ref}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 and len(r.stdout) < 600_000 else None


def griffe_findings(old_src, new_src, name, work):
    d = work / "g"
    for sub, src in (("old", old_src), ("new", new_src)):
        (d / sub).mkdir(parents=True, exist_ok=True)
        (d / sub / f"{name}.py").write_text(src)
    try:
        o = griffe.load(name, search_paths=[str(d / "old")], try_relative_path=False, allow_inspection=False)
        n = griffe.load(name, search_paths=[str(d / "new")], try_relative_path=False, allow_inspection=False)
        return sorted(f"{b.kind.value}: {b.obj.path}" for b in griffe.find_breaking_changes(o, n)), None
    except Exception as e:   # tool failure is reported, not hidden
        return [], f"{type(e).__name__}: {str(e)[:120]}"


def main():
    scratch = Path(sys.argv[1]); scratch.mkdir(parents=True, exist_ok=True)
    cheap = [json.loads(l) for l in (ROOT / "data/shadow2/cheap.jsonl").read_text().splitlines()]
    units = [x for x in cheap if "head" in x and x["changes_python"] and any(c["kind"] == "backward_compatible" for c in x["claims"])]
    out = []
    for i, x in enumerate(units):
        o, n = x["repo"].split("/")
        files = gh(f"repos/{o}/{n}/pulls/{x['number']}/files?per_page=100")
        if not isinstance(files, list):
            out.append({"pr": x["pr"], "error": "file list unavailable"}); continue
        rec = {"pr": x["pr"], "repo": x["repo"], "number": x["number"], "files": []}
        for f in files:
            fn = f["filename"]
            if not fn.endswith(".py") or f["status"] not in ("modified", "removed", "renamed"):
                continue
            base_path = f.get("previous_filename", fn)
            old = raw(x["repo"], base_path, x["base"])
            new = raw(x["repo"], fn, x["head"]) if f["status"] != "removed" else None
            item = {"file": fn, "status": f["status"]}
            if old is None:
                item["note"] = "base file unreadable"; rec["files"].append(item); continue
            if f["status"] == "removed":
                item["agentvow"] = [f"removed file: {fn}"]; item["griffe"] = [f"removed file: {fn}"]; rec["files"].append(item); continue
            if new is None:
                item["note"] = "head file unreadable"; rec["files"].append(item); continue
            is_init = fn.endswith("__init__.py")
            try:
                item["agentvow"] = api_diff.breaking(api_diff.public_api(old, is_init), api_diff.public_api(new, is_init))
            except Exception as e:
                item["agentvow"] = None; item["agentvow_error"] = f"{type(e).__name__}"
            name = "m" + str(abs(hash(fn)) % 10**8)
            item["griffe"], item["griffe_error"] = griffe_findings(old, new, name, scratch)
            rec["files"].append(item)
        out.append(rec)
        if i % 20 == 0:
            print(i, len(units), flush=True)
    (scratch / "bakeoff.json").write_text(json.dumps(out, indent=1))
    print("done", len(out))


if __name__ == "__main__":
    main()
