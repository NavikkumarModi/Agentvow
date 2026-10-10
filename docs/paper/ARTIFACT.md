# Artifact and reproducibility statement (draft, 2026-10-10)

What exists in this repository: the tool (`agentvow/`), studies' scripts (`research/preconditions/`, `scripts/detection_v2_*.py`), protocols and results (`docs/research/`), and tests (`tests/`, 270 Python, 32 Node; `scripts/validate_all.sh` runs 38 checks).
What is **not** in the repository (`data/` is git-ignored): third-party task snapshots, saved agent patches, transcripts, raw result files. These stay local because they contain others' code; only identifiers and aggregate results are releasable (a release is a publishing decision for the owner).

## What a stranger needs to rerun B1/B2, and its status
| item | status |
|---|---|
| Task list (repo, PR, base/head SHA, target files, stratum) | local `data/preconditions/stageb_validated.jsonl`; identifiers could be released as `tasks.jsonl` |
| Candidate order and seed | seed 2028, scripts `stageb_candidates.py`, `stageb_validate.py`; candidate list is derived from the public AIDev corpus (release the filter, not the corpus) |
| Prompts | `research/preconditions/run_pilot.py` (`BASE`, `RECIPE`, `RECIPE_P`); B2 differs by one sentence in `stageb_run.py::prompt_for` (`AMBIENT=1`) |
| Agent and sandbox | Claude Code CLI run through `research/preconditions/sandboxed_claude.py` (S0 profile, macOS `sandbox-exec`); the CLI on PATH was 2.1.263 when this was written; the per-run CLI version and exact model ID were **not recorded** (the studies say "installed default model"), a reproducibility gap |
| Python | 3.13.5 for the harness; replay environments use the interpreter that built them |
| Ambient packages (B2) | 17 package names in `stageb_run.py::AMBIENT_PKGS`; the resolved versions are in each B2 result row (`ambient_freeze`), unpinned at install time |
| Replay | `agentvow check --recipe ...`; setup steps use live PyPI with unpinned names, so reruns on another day can differ (determinism measured same-day only) |
| Analysis | `analyze_stageb.py` (B1), `analyze_stageb2.py` (B2), `analyze_pilot.py`, `analyze_stagea.py`; post-hoc re-replays: `stageb_rereplay.py [--b2]` |
| Cost | B1 $13.30, B2 $14.90, pilot $5.26 plus $0.71 (list prices) |
