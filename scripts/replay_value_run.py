"""Does the replay earn its place? (rules: docs/research/REPLAY_VALUE_PREREG.md, frozen; operational choices: its Amendment 1).

Usage (from the repository root):
  python3 scripts/replay_value_run.py select            -> data/replay_value_sample.csv, data/replay_value_select.json
  python3 scripts/replay_value_run.py run [workers]     -> data/replay_value_results.jsonl (resumable, one repository at a time)
  python3 scripts/replay_value_run.py summary           -> Q1 to Q3 and the pre-registered decision rule

Pull requests come from the CI study (outcome NO_CI or NO_TEST_JOB, a tests_pass claim), restricted to plain-pip repositories by the
eligibility rule below. The replay is the shipped zero-config ladder run WITHOUT --ci. Q2 plants faults only in runs that ended SUPPORTED;
Q3 adjudicates CONTRADICTED / regression results mechanically (no model labels). The pure helpers have no heavy imports so tests can use them.
"""
import ast
import json
import math
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
DATA = ROOT / "data"
SAMPLE, SELECT, OUT = DATA / "replay_value_sample.csv", DATA / "replay_value_select.json", DATA / "replay_value_results.jsonl"
SEED, TARGET, PER_REPO, MAX_MB = 2026, 60, 3, 300
MARKER_FILES = {"poetry.lock", "pipfile", "pipfile.lock", "uv.lock", "environment.yml", "environment.yaml", "conda.yml", "pdm.lock"}
MARKER_TEXT = ("[tool.poetry", "[tool.uv", "dependency-groups", "[tool.pipenv", "[tool.pdm", "[tool.hatch.envs")
THRESHOLDS = {"yield": 0.40, "detection": 0.60, "confirmed": 0.75}
MIN_CONTRADICTED = 4
HARNESS = ("harness_low_disk", "error", "skipped_low_disk")


def eligibility(names, pyproject_text, size_mb):
    """Return (True, "") or (False, reason). `names` are the repository root's file names at the pull request's head commit (not the default branch)."""
    if size_mb is None or size_mb >= MAX_MB:
        return False, "size"
    low = {n.lower() for n in names}
    hit = sorted(low & MARKER_FILES)
    if hit:
        return False, f"marker:{hit[0]}"
    text = pyproject_text or ""
    hit = [m for m in MARKER_TEXT if m in text]
    if hit:
        return False, f"marker:{hit[0]}"
    if not (any(n.startswith("requirements") and n.endswith(".txt") for n in low) or "pyproject.toml" in low or "setup.py" in low):
        return False, "no_install_files"
    return True, ""


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)


def imports_changed(source, test_path, changed):
    """Static proxy for 'the failing test imports a file the pull request changed': True when an import in `source` names a module whose file is in `changed`."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    mods = set()
    pkg = Path(test_path).parent.parts
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = ".".join(pkg[: len(pkg) - node.level + 1]) if node.level else ""
            name = ".".join(x for x in (base, node.module or "") if x)
            mods.add(name)
            mods |= {f"{name}.{a.name}" if name else a.name for a in node.names}
    for m in mods:
        rel = m.replace(".", "/")
        for pre in ("", "src/"):
            if f"{pre}{rel}.py" in changed or f"{pre}{rel}/__init__.py" in changed:
                return True
    return False


def adjudicate(regression_sets, test_sources, changed):
    """regression_sets: failed ids that passed at base, one set per head run (3 runs). test_sources: {test file: source or None}."""
    if all(not s for s in regression_sets):
        return {"class": "cannot_decide", "why": "no regression in any run (the verdict came from another rule)"}
    stable = set.intersection(*map(set, regression_sets))
    if not stable:
        return {"class": "not_confirmed", "why": "the regressions are not the same in 3 runs"}
    seen = False
    for tid in sorted(stable):
        if "::" not in tid:
            continue
        seen = True
        f = tid.split("::")[0]
        if f in changed or (test_sources.get(f) and imports_changed(test_sources[f], f, changed)):
            return {"class": "confirmed", "test": tid}
    return {"class": "not_confirmed" if seen else "cannot_decide", "why": "the stable failing tests import no changed file" if seen else "failing ids have no file part"}


SUPPORTED_NAMES = ("SUPPORTED", "SUPPORTED_BY_PRIOR_EVIDENCE")  # the shipped decision logic names a fresh passing run SUPPORTED_BY_PRIOR_EVIDENCE


def summarize(rows):
    """Apply the frozen decision rule to the results rows."""
    harness = [r for r in rows if r.get("stage") in HARNESS]
    ok = [r for r in rows if r.get("stage") not in HARNESS]
    yielded = [r for r in ok if r.get("verdict") in SUPPORTED_NAMES + ("CONTRADICTED",)]
    faults = [f for r in ok if r.get("verdict") in SUPPORTED_NAMES for f in r.get("faults", [])]
    detected = [f for f in faults if f["detected"]]
    adj = [r["adjudication"]["class"] for r in ok if r.get("adjudication")]
    conf, notc = adj.count("confirmed"), adj.count("not_confirmed")
    out = {
        "pull_requests": len(rows), "harness_failures": len(harness), "evaluated": len(ok), "repositories": len({r["repo"] for r in ok}),
        "stages": {s: sum(1 for r in ok if r.get("stage") == s) for s in sorted({r.get("stage") for r in ok})},
        "verdicts": {v: sum(1 for r in ok if r.get("verdict") == v) for v in sorted({r.get("verdict") for r in ok if r.get("verdict")})},
        "q1_yield": {"k": len(yielded), "n": len(ok), "rate": round(len(yielded) / len(ok), 3) if ok else None, "wilson": wilson(len(yielded), len(ok))},
        "q2_detection": {"k": len(detected), "n": len(faults), "rate": round(len(detected) / len(faults), 3) if faults else None, "wilson": wilson(len(detected), len(faults)),
                         "oracle_break": sum(1 for f in faults if f.get("oracle_break")), "runs": len({r["repo"] + str(r["pr"]) for r in ok if r.get("faults")})},
        "q3_confirmed": {"confirmed": conf, "not_confirmed": notc, "cannot_decide": adj.count("cannot_decide"),
                         "rate": round(conf / (conf + notc), 3) if conf + notc else None, "wilson": wilson(conf, conf + notc)},
    }
    q1, q2, q3 = out["q1_yield"]["rate"], out["q2_detection"]["rate"], out["q3_confirmed"]["rate"]
    out["q3_determined"] = conf + notc >= MIN_CONTRADICTED
    out["rule"] = {"yield_ok": q1 is not None and q1 >= THRESHOLDS["yield"], "detection_ok": q2 is not None and q2 >= THRESHOLDS["detection"],
                   "confirmed_ok": out["q3_determined"] and q3 >= THRESHOLDS["confirmed"]}
    out["rule"]["keep_as_headline"] = all(out["rule"].values())
    return out


# ---- everything below needs the network, GitHub and the sandbox ----

def gh(path, raw=False):
    cmd = ["gh", "api", *(["-H", "Accept: application/vnd.github.raw"] if raw else []), path]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def select():
    import pandas as pd
    from agentvow import claims
    df = pd.read_csv(DATA / "ci_study_outcomes.csv")
    df = df[df.outcome.isin(["NO_CI", "NO_TEST_JOB"]) & df["head"].notna()]
    pr = pd.read_parquet(DATA / "aidev" / "pull_request.parquet")
    rp = pd.read_parquet(DATA / "aidev" / "repository.parquet")[["id", "full_name"]].rename(columns={"id": "repo_id"})
    body = pr.merge(rp, on="repo_id")[["full_name", "number", "body"]].rename(columns={"full_name": "repo", "number": "pr"})
    df = df.merge(body, on=["repo", "pr"], how="left")
    df = df[df.body.map(lambda b: isinstance(b, str) and any(c.kind == "tests_pass" for c in claims.extract(b)))]
    cands = sorted(df.itertuples(), key=lambda r: (r.repo, r.pr))
    random.Random(SEED).shuffle(cands)
    chosen, per, excluded, sizes = [], {}, {}, {}
    for r in cands:
        if len(chosen) >= TARGET:
            break
        if per.get(r.repo, 0) >= PER_REPO:
            excluded["per_repo_cap"] = excluded.get("per_repo_cap", 0) + 1
            continue
        if r.repo not in sizes:
            s = gh(f"repos/{r.repo}")
            sizes[r.repo] = (json.loads(s).get("size", 0) / 1024) if s else None
        listing = gh(f"repos/{r.repo}/contents?ref={r.head}")
        if listing is None:
            excluded["no_listing"] = excluded.get("no_listing", 0) + 1
            continue
        names = [e["name"] for e in json.loads(listing) if e.get("type") == "file"]
        py = gh(f"repos/{r.repo}/contents/pyproject.toml?ref={r.head}", raw=True) if "pyproject.toml" in names else ""
        ok, why = eligibility(names, py, sizes[r.repo])
        if not ok:
            excluded[why] = excluded.get(why, 0) + 1
            continue
        per[r.repo] = per.get(r.repo, 0) + 1
        chosen.append({"repo": r.repo, "pr": int(r.pr), "agent": r.agent, "group": "no_ci", "outcome": r.outcome, "claimed": True, "head": r.head})
    pd.DataFrame(chosen).to_csv(SAMPLE, index=False)
    info = {"seed": SEED, "target": TARGET, "candidates_with_claim": len(cands), "selected": len(chosen), "repositories": len(per), "excluded": excluded}
    SELECT.write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


def changed_files(repo, base, head):
    import detection_v2_run as dvr
    return set(dvr.sh(["git", "diff", "--name-only", base, head], cwd=repo)[1].split())


def plant_faults(rng, wh, repo, base, head, b, argv, env_extra, claimed_counts, pc):
    import planted_faults as pf
    from agentvow import reality, runner
    import detection_v2_run as dvr
    files = [f for f in changed_files(repo, base, head) if f.endswith(".py") and not reality.is_test(f) and Path(f).name not in pf.SKIP_NAMES and (wh / f).exists()]
    out = []
    for f, ln, a, z in pf.behaviour_mutants(wh, repo, base, head, files, rng, k=3):
        dvr.sh(["git", "checkout", "-q", "-f", "--", "."], cwd=wh)
        pf.apply_mut(wh, f, ln, a, z)
        rec = runner.run_tests(wh, argv, timeout=240, write=False, baseline_failed=b["failed_ids"], baseline_passed=b["passed_ids"], env_extra=env_extra)
        v = pf.verdict(rec, claimed_counts[0] if claimed_counts else None)
        cnt = rec["counts"] or {}
        out.append({"fault": f"{f}:{ln} '{a.strip()}'->'{z.strip()}'", "verdict": v, "regressions": cnt.get("regressions"), "passed_clean": pc,
                    "passed_fault": cnt.get("passed", 0), "detected": v == "CONTRADICTED" or bool(cnt.get("regressions")),
                    "oracle_break": cnt.get("passed", 0) < pc or bool(cnt.get("failed") or cnt.get("errors"))})
    dvr.sh(["git", "checkout", "-q", "-f", "--", "."], cwd=wh)
    return out


def _one_repo(repo_name, prs):
    import detection_v2_run as dvr
    from agentvow import claims, decision, reality, runner
    import json as _json
    key = repo_name.replace("/", "_")
    repo = dvr.REPOS / key
    res, t0 = [], __import__("time").time()
    if not repo.exists():
        rc, out = dvr.sh(["git", "clone", "-q", f"https://github.com/{repo_name}.git", str(repo)], timeout=600)
        if rc:
            return [{**p, "stage": "clone_failed", "note": out[-150:]} for p in prs]
    venv, notes = dvr.setup_env(repo, key)
    if venv is not None and any("too heavy" in n or "disk low" in n for n in notes):
        return [{**p, "stage": "env_too_heavy", "note": "; ".join(notes)[:200]} for p in prs]
    if venv is None:
        return [{**p, "stage": "env_failed", "note": "; ".join(notes)} for p in prs]
    argv = [str(venv / "bin/python"), "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider"]
    rng = random.Random(SEED)
    for p in prs:
        r = {**p, "setup_notes": notes, "stage": "?"}
        if not dvr.free_ok():
            r["stage"] = "harness_low_disk"; res.append(r); continue
        try:
            n = p["pr"]
            dvr.sh(["git", "fetch", "-q", "origin", f"pull/{n}/head"], cwd=repo, timeout=120)
            info = _json.loads(subprocess.run(["gh", "api", f"repos/{repo_name}/pulls/{n}"], capture_output=True, text=True).stdout)
            head, base, body = info["head"]["sha"], info["base"]["sha"], info.get("body") or ""
            cl = [c for c in claims.extract(body) if c.kind == "tests_pass"]
            r.update(claimed_counts=[c.count for c in cl], head=head, base=base)
            if dvr.sh(["git", "checkout", "-q", "-f", "--detach", head], cwd=repo)[0] or dvr.sh(["git", "cat-file", "-e", base], cwd=repo)[0]:
                r["stage"] = "no_commits"; res.append(r); continue
            tmp = dvr.DATA / "wt_rv" / f"{key}_{n}"
            dvr.sh(["rm", "-rf", str(tmp)])
            tmp.mkdir(parents=True, exist_ok=True)
            for nm, sha in (("base", base), ("head", head)):
                dvr.sh(["git", "worktree", "add", "--detach", "-f", str(tmp / nm), sha], cwd=repo)
            wb, wh = tmp / "base", tmp / "head"
            env_b, env_h = {"PYTHONPATH": f"{wb}/src:{wb}"}, {"PYTHONPATH": f"{wh}/src:{wh}"}
            b = runner.run_tests(wb, argv, timeout=240, write=False, env_extra=env_b)
            h = runner.run_tests(wh, argv, timeout=240, write=False, baseline_failed=b["failed_ids"], baseline_passed=b["passed_ids"], env_extra=env_h)
            ev = repo / ".agentvow" / "evidence"
            ev.mkdir(parents=True, exist_ok=True)
            (ev / f"testrun_{head[:10]}_0.json").write_text(_json.dumps(reality.sign_record(h)))
            d = decision.check(repo, base, body, None, "unknown")
            f = next((x for x in d.findings if x.kind == "tests_pass"), None)
            r.update(stage="done", verdict=f.verdict if f else None, why=(f.why[:200] if f else None), base_result=b["result"], base_counts=b["counts"],
                     head_result=h["result"], head_counts=h["counts"], usable_base=bool(b["counts"].get("passed")), head_summary=h.get("summary"))
            changed = changed_files(repo, base, head)
            if r["verdict"] == "CONTRADICTED" or (h["counts"] or {}).get("regressions"):
                runs = [h] + [runner.run_tests(wh, argv, timeout=240, write=False, baseline_failed=b["failed_ids"], baseline_passed=b["passed_ids"], env_extra=env_h) for _ in range(2)]
                sets = [sorted(set(x["failed_ids"]) & set(b["passed_ids"])) for x in runs]
                srcs = {}
                for tid in set().union(*map(set, sets)):
                    tf = tid.split("::")[0]
                    if tf not in srcs and (wh / tf).is_file():
                        srcs[tf] = (wh / tf).read_text(encoding="utf-8", errors="replace")
                r["adjudication"] = adjudicate(sets, srcs, changed)
                r["regression_counts"] = [len(s) for s in sets]
            if r["verdict"] in SUPPORTED_NAMES:
                r["faults"] = plant_faults(rng, wh, repo, base, head, b, argv, env_h, r["claimed_counts"], (h["counts"] or {}).get("passed", 0))
        except Exception as e:  # report, never hide
            r.update(stage="error", note=f"{type(e).__name__}: {e}"[:200])
        finally:
            for nm in ("base", "head"):
                dvr.sh(["git", "worktree", "remove", "--force", str(dvr.DATA / "wt_rv" / f"{key}_{p['pr']}" / nm)], cwd=repo)
        res.append(r)
    for r in res:
        r["repo_seconds"] = round(__import__("time").time() - t0)
    return res


def one_repo(item):
    import shutil
    import detection_v2_run as dvr
    name, prs = item
    key = name.replace("/", "_")
    if not dvr.free_ok():
        return [{**p, "stage": "harness_low_disk"} for p in prs]
    try:
        return _one_repo(name, prs)
    except Exception as e:
        return [{**p, "stage": "error", "note": f"{type(e).__name__}: {e}"[:200]} for p in prs]
    finally:
        for d in (dvr.VENVS / key, dvr.REPOS / key, dvr.DATA / "home" / key):
            shutil.rmtree(d, ignore_errors=True)


def run(workers=1):
    import pandas as pd
    from concurrent.futures import ThreadPoolExecutor
    import detection_v2_run as dvr
    for d in (dvr.REPOS, dvr.VENVS, DATA / "home", DATA / "pipcache", DATA / "wt_rv"):
        d.mkdir(parents=True, exist_ok=True)
    sel = pd.read_csv(SAMPLE)
    done = {(j["repo"], j["pr"]) for j in map(json.loads, OUT.read_text().splitlines())} if OUT.exists() else set()
    by = {}
    for r in sel.itertuples():
        if (r.repo, int(r.pr)) not in done:
            by.setdefault(r.repo, []).append({"repo": r.repo, "pr": int(r.pr), "agent": r.agent, "group": r.group, "ci_outcome": r.outcome, "claimed": True})
    print(f"{sum(map(len, by.values()))} PRs in {len(by)} repos to run", file=sys.stderr)
    with ThreadPoolExecutor(workers) as ex, OUT.open("a") as fh:
        for res in ex.map(one_repo, by.items()):
            for r in res:
                fh.write(json.dumps(r) + "\n")
            fh.flush()
            print("done", res[0]["repo"], [r.get("stage") for r in res], file=sys.stderr)


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "select":
        select()
    elif cmd == "run":
        run(int(argv[1]) if len(argv) > 1 else 1)
    elif cmd == "summary":
        print(json.dumps(summarize([json.loads(x) for x in OUT.read_text().splitlines()]), indent=1))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
