"""Differential check of agentvow/baseline.py's small GitHub-Actions reader against PyYAML (needs `pip install pyyaml`; a developer check, not part of the product).
  python3 scripts/workflow_reader_check.py fetch REPOS.txt OUT_DIR   # read .github/workflows of each `owner/name` listed (public repositories; uses the `gh` CLI, text only, nothing is executed)
  python3 scripts/workflow_reader_check.py compare OUT_DIR           # per file: do the jobs and their `run` commands match PyYAML's (comments and skip-conditions normalised the same way)?
Prints counts and the files that differ; third-party workflow files are not stored in this repository."""
import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import baseline  # noqa: E402


def fetch(repos_file, out):
    n = 0
    for r in (x.strip() for x in Path(repos_file).read_text().splitlines() if x.strip()):
        p = subprocess.run(["gh", "api", f"repos/{r}/contents/.github/workflows"], capture_output=True, text=True, timeout=60)
        if p.returncode:
            continue
        try:
            items = json.loads(p.stdout)
        except ValueError:
            continue
        d = Path(out) / r.replace("/", "__")
        d.mkdir(parents=True, exist_ok=True)
        for it in items:
            if it.get("type") == "file" and it["name"].endswith((".yml", ".yaml")):
                q = subprocess.run(["gh", "api", it["url"], "--jq", ".content"], capture_output=True, text=True, timeout=60)
                if q.returncode == 0:
                    (d / it["name"]).write_bytes(base64.b64decode(q.stdout))
                    n += 1
    print("files fetched:", n)


def norm(s):
    return re.sub(r"\s+", " ", "\n".join(l for l in (s or "").splitlines() if not l.lstrip().startswith("#"))).strip()


def compare(root):
    import yaml
    files = sorted(Path(root).glob("*/*.y*ml"))
    ok, bad, skip, differ = 0, 0, 0, []
    for f in files:
        t = f.read_text(errors="replace")
        try:
            y = yaml.safe_load(t)
        except Exception:
            skip += 1
            continue
        if not isinstance(y, dict) or not isinstance(y.get("jobs"), dict):
            skip += 1
            continue
        try:
            _, jobs = baseline.parse_workflow(t)
        except ValueError:
            skip += 1   # outside the supported subset (refused on purpose)
            continue
        ref = []
        for jn, j in y["jobs"].items():
            j = j or {}
            if baseline._skipped_by_condition(str(j["if"]) if "if" in j else None):
                ref.append((jn, []))
                continue
            steps = [norm(str(s["run"])) for s in j.get("steps") or [] if isinstance(s, dict) and "run" in s and not baseline._skipped_by_condition(str(s["if"]) if "if" in s else None)]
            ref.append((jn, steps))
        mine = [(jn, [norm(s["run"]) for s in st if s["run"]]) for jn, _e, st in jobs]
        if ref == mine:
            ok += 1
        else:
            bad += 1
            differ.append(str(f.relative_to(root)))
    print(f"files {len(files)}: identical {ok}, different {bad}, not compared (YAML error, no jobs, or outside the supported subset, refused on purpose) {skip}")
    for d in differ:
        print("  differs:", d)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "fetch":
        fetch(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 3 and sys.argv[1] == "compare":
        compare(sys.argv[2])
    else:
        print(__doc__)
