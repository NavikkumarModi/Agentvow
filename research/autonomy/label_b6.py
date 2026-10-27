"""Label the 22 valid Stage B6 runs: which action would the current policy (agentvow.policy.evaluate, default policy) take for each evidence source?
Advisory, offline. decision allow -> continue, needs_acknowledgement -> escalate, block -> stop.
Usage: python3 research/autonomy/label_b6.py [--table]   (reads data/preconditions/stageb6_*.jsonl, local only)"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentvow import decision, policy  # noqa: E402

D = ROOT / "data" / "preconditions"
ACTION = {"allow": "continue", "needs_acknowledgement": "escalate", "block": "stop"}
SOURCES = ("attested_self_run", "capture_replay", "recipe_replay", "repository_replay")


def rows(name):
    return [json.loads(l) for l in (D / name).read_text().splitlines() if l.strip()]


def harness_flags(r):
    """The warnings the current rule would raise from the files the agent changed. Shared config files (pyproject.toml, setup.cfg, tox.ini) need the diff, which is not stored: counted as undetermined."""
    files = r.get("files_changed") or []
    flags = [f for f in files if decision._runs_at_test_start(f) or f.rsplit("/", 1)[-1] in decision._ALWAYS_TEST_CONFIG]
    if r.get("tests_modified"):
        flags.append("tests_modified")
    undetermined = [f for f in files if f.rsplit("/", 1)[-1] in decision._SHARED_CONFIG]
    return flags, undetermined


def action(verdict, claim_made, source, warn=()):
    """One 'tests_pass' claim with the given verdict. Provenance as the receipt would carry it: attempt-time capture is local (authenticated, bound to the capsule); the others are not captures."""
    claims = [{"kind": "tests_pass", "verdict": verdict, "basis": "", "capture_source": "local" if source == "capture_replay" else "", "dropped_pins": 0,
               "capture_authenticated": True if source == "capture_replay" else None, "state_binding": "capsule" if source == "capture_replay" else "", "partial_replay": False,
               "harness_warning": list(warn)[:5], "changed_lines": None}] if claim_made else []
    r = {"schema": policy.RECEIPT, "tool_version": "0", "created_at": "t", "repo": "o/r", "commit": "a" * 40, "git_tree": "b" * 40, "base": "", "pr": None, "status": "", "claims": claims,
         "unexamined": 0, "reproducibility": "", "contexts": [], "coverage": None, "not_reproduced": []}
    return ACTION[policy.evaluate(r)["decision"]]


def valid_runs():
    R = rows("stageb6_results.jsonl")
    return [r for r in R if r.get("truth_in_agent_env") == "pass" and r.get("base_fails_in_agent_env")]


def verdict_of(r, key):
    x = r.get(key)
    return (x or {}).get("verdict")


def main():
    V = valid_runs()
    out = {s: collections.Counter() for s in SOURCES}
    table = []
    flagged = undetermined = 0
    for r in V:
        claim = bool(r["claim_made"])
        v = {"attested_self_run": "NOT_CONTRADICTED", "capture_replay": verdict_of(r, "freeze_replay"), "recipe_replay": verdict_of(r, "recipe_scoped_replay"), "repository_replay": verdict_of(r, "ladder")}
        # a missing replay (the recipe was rejected before replay, or nothing ran) is no evidence: UNKNOWN
        warn, undet = harness_flags(r)
        undetermined += bool(undet)
        flagged += bool(warn)
        a = {s: action(v[s] or "UNKNOWN", claim, s, warn) for s in SOURCES}
        for s in SOURCES:
            out[s][a[s]] += 1
        table.append((f"{r['repo']}#{r['pr']}", claim, v["capture_replay"], v["repository_replay"], a))
    print(f"## Valid B6 runs: {len(V)}; claim made: {sum(bool(r['claim_made']) for r in V)}\n")
    print(f"harness warning raised: {flagged}; shared test-config file changed, diff not stored (undetermined): {undetermined}\n")
    print("| evidence source | continue | escalate | stop |\n|---|---|---|---|")
    for s in SOURCES:
        print(f"| {s} | {out[s]['continue']} | {out[s]['escalate']} | {out[s]['stop']} |")
    if "--table" in sys.argv:
        print("\n| run | claim | capture verdict | repo verdict | capture | repo-only |\n|---|---|---|---|---|---|")
        for n, c, cv, rv, a in table:
            print(f"| {n} | {c} | {cv} | {rv} | {a['capture_replay']} | {a['repository_replay']} |")
    F = [f for f in rows("stageb6_faults.jsonl") if f["outcome"] == "ran"]
    print(f"\n## Fault-injected runs ({len(F)}; a fault planted on a line the agent added, claim kept; no oracle)\n")
    for ctx in ("captured", "native"):
        c = collections.Counter(action(f[ctx]["verdict"], True, "capture_replay" if ctx == "captured" else "repository_replay") for f in F)
        print(f"- {ctx}: continue {c['continue']}, escalate {c['escalate']}, stop {c['stop']}")


if __name__ == "__main__":
    main()
