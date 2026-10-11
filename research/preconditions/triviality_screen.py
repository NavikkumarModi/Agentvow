"""Pre-agent non-triviality screen (post-hoc design for a future stage). A task is predicted NON-trivial if the PR's added test lines mention at least one identifier that the PR's
source change introduces (appears on added source lines but on no removed/context source line). Evidence per candidate comes from the public GitHub pull-request files API.
Evaluated against the observed labels of Stage B3/B4 runs in which the agent's tests passed (valid = base fails in the agent's environment; trivial = base passes).
Usage: python3 research/preconditions/triviality_screen.py [eval]"""
import json
import re
import subprocess
import sys
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data" / "preconditions"
CACHE = D / "triviality_cache.json"
ID = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
TESTY = re.compile(r"(^|/)(tests?|testing)(/|$)|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")


def files(repo, pr):
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    k = f"{repo}#{pr}"
    if k not in cache:
        r = subprocess.run(["gh", "api", "--paginate", f"repos/{repo}/pulls/{pr}/files", "-q", ".[] | {filename, patch}"], capture_output=True, text=True)
        cache[k] = [json.loads(l) for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else None
        CACHE.write_text(json.dumps(cache))
    return cache[k]


def score(repo, pr):
    fs = files(repo, pr)
    if fs is None:
        return None
    added, other, test_added = set(), set(), set()
    for f in fs:
        patch = f.get("patch") or ""
        if TESTY.search(f["filename"]):
            for ln in patch.splitlines():
                if ln.startswith("+") and not ln.startswith("+++"):
                    test_added |= set(ID.findall(ln))
        elif f["filename"].endswith(".py"):
            for ln in patch.splitlines():
                if ln.startswith("+") and not ln.startswith("+++"):
                    added |= set(ID.findall(ln))
                else:
                    other |= set(ID.findall(ln))
    new = added - other
    return len(new & test_added)


def main():
    rows = []
    for stage in ("stageb3", "stageb4"):
        for l in open(D / f"{stage}_results.jsonl"):
            r = json.loads(l)
            if r.get("truth_in_agent_env") == "pass":
                rows.append((stage, r["repo"], r["pr"], bool(r.get("base_fails_in_agent_env"))))
    res = []
    for stage, repo, pr, valid in rows:
        s = score(repo, pr)
        res.append((stage, repo, pr, valid, s))
    ok = [x for x in res if x[4] is not None]
    print(f"{len(ok)} of {len(res)} evaluated (agent-passing runs); valid {sum(x[3] for x in ok)}, trivial {sum(not x[3] for x in ok)}")
    for thr in (1, 2, 3):
        pred = [x for x in ok if x[4] >= thr]
        tp = sum(x[3] for x in pred); fn = sum(x[3] for x in ok if x[4] < thr)
        print(f"  score >= {thr}: selected {len(pred)}, of which valid {tp} ({100 * tp // max(1, len(pred))}%); valid runs lost {fn} of {sum(x[3] for x in ok)}; base rate valid {100 * sum(x[3] for x in ok) // len(ok)}%")


if __name__ == "__main__":
    main()
