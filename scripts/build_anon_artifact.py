"""Build an anonymised copy of the tool and the B6 study material for double-anonymous review. Output: data/anon_artifact/ and data/anon_artifact.zip (data/ is git-ignored). Scrubs the project name, the owner's names, home paths and e-mail addresses from text files; drops git history, titles/bodies of third-party PRs and session ids. Usage: python3 scripts/build_anon_artifact.py"""
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "anon_artifact"
SUBS = [(r"Agentvow", "ReplayTool"), (r"agentvow", "replaytool"), (r"AGENTVOW", "REPLAYTOOL"), (r"NavikkumarModi", "anon"), (r"navikkumarmodi", "anon"), (r"Navikkumar Modi", "Anonymous"),
        (r"/Users/[A-Za-z0-9_.-]+", "/home/user"), (r"[\w.+-]+@(?:googlemail|gmail)\.com", "anon@example.org"), (r"navik", "anon")]
STUDY = ["stageb6_select.py", "stageb_run.py", "stageb_candidates.py", "stageb_validate.py", "sandboxed_claude.py", "analyze_stageb6.py", "analyze_stageb6_robustness.py", "run_pilot.py"]
DOCS = ["STAGE_B6_PREREG.md", "STAGE_B6_RESULTS.md"]


def scrub(t):
    for a, b in SUBS:
        t = re.sub(a, b, t)
    return t


def copy_text(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        dst.write_text(scrub(src.read_text()))
    except UnicodeDecodeError:
        shutil.copy2(src, dst)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    for d, name in (("agentvow", "replaytool"), ("tests", "tests")):
        for f in sorted((ROOT / d).rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix not in (".pyc",):
                copy_text(f, OUT / name / f.relative_to(ROOT / d))
    for f in ("pyproject.toml", "LICENSE"):
        copy_text(ROOT / f, OUT / f)
    pp = OUT / "pyproject.toml"
    t = pp.read_text()
    t = re.sub(r"(?m)^(authors|maintainers)\s*=.*\n", "", t)
    t = re.sub(r"(?ms)^\[project\.urls\].*?(?=^\[|\Z)", "", t)
    pp.write_text(t)
    copy_text(ROOT / "examples" / "make_demo.py", OUT / "examples" / "make_demo.py")
    copy_text(ROOT / "research" / "preconditions" / "ci_recipe.py", OUT / "research" / "preconditions" / "ci_recipe.py")
    for f in STUDY:
        copy_text(ROOT / "research" / "preconditions" / f, OUT / "research" / "preconditions" / f)
    for f in DOCS:
        copy_text(ROOT / "docs" / "research" / "forecast_grounding" / f, OUT / "study" / f)
    D = ROOT / "data" / "preconditions"
    tasks = []
    for l in (D / "stageb6_tasks.jsonl").read_text().splitlines():
        r = json.loads(l)
        tasks.append({k: r[k] for k in ("repo", "pr", "agent", "base", "head", "test_files", "src_files") if k in r})
    (OUT / "study" / "stageb6_tasks.jsonl").write_text("\n".join(json.dumps(x) for x in tasks) + "\n")
    keep = ("idx", "repo", "pr", "stratum", "agent_of_pr", "target_files", "is_error", "truth_in_agent_env", "base_fails_in_agent_env", "stage")
    rows = []
    for l in (D / "stageb6_results.jsonl").read_text().splitlines():
        r = json.loads(l)
        row = {k: r[k] for k in keep if k in r}
        for k in ("ladder", "freeze_replay", "recipe_scoped_replay"):
            v = r.get(k) or {}
            ev = v.get("evidence") or {}
            row[k] = {"verdict": v.get("verdict"), "evidence": {"result": ev.get("result"), "counts": ev.get("counts")}}
        rows.append(row)
    (OUT / "data" / "preconditions").mkdir(parents=True)
    (OUT / "data" / "preconditions" / "stageb6_results.jsonl").write_text("\n".join(json.dumps(x) for x in rows) + "\n")
    (OUT / "README.md").write_text("""# Anonymised artifact (double-anonymous review)

* `replaytool/`, `tests/`, `pyproject.toml`: the replay tool and its tests (the project name is replaced; behaviour is unchanged). `pip install -e .` then `pytest -q tests`.
* `research/preconditions/`: the scripts used for the pre-registered study (task selection with a fixed seed, the agent run harness, the analysis). `study/`: the pre-registration and the results text, and the task list.
* `study/stageb6_tasks.jsonl`: the 40 task identifiers (public repository, pull-request number, base and head commit, test and source file paths). Titles, bodies, transcripts, agent patches and environment snapshots are not included (third-party content).
* `data/preconditions/stageb6_results.jsonl`: per-task outcomes (agent tests pass, valid, replay results per context). Session identifiers, paths and agent text are removed.
* Reproducing the analysis tables from the summary needs only `python3`: `python3 research/preconditions/analyze_stageb6.py` (the optional robustness script needs the same file). The tests need `pyyaml` for one research helper (`pip install pyyaml`); 298 pass and 2 skip in the clean environment used to check this copy; re-running the agent needs the Claude Code CLI, which is not included. The CLI version and model ID per run were not recorded.
""")
    with zipfile.ZipFile(ROOT / "data" / "anon_artifact.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(OUT.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(OUT))
    print("built", OUT, sum(1 for _ in OUT.rglob("*") if _.is_file()), "files")


if __name__ == "__main__":
    main()
