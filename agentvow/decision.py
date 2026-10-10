"""Reconcile claims with reality and build a decision object.

Design intent (fail-closed), with known gaps listed in docs/research/RISKS.md:
  * the overall status is never plainly "safe"; the best outcome is NO CONTRADICTION FOUND, scoped.
  * missing evidence, collector errors, parse gaps and unchecked claims should yield UNKNOWN. Known remaining fail-open
    paths: trivialised tests, ignored files, import-graph and API-diff blind spots (see RISKS.md).
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import claims as C
from . import api_diff
from . import reality as R

REVIEW = "REVIEW REQUIRED"
INSUFFICIENT = "INSUFFICIENT EVIDENCE"
NO_CONTRA = "NO CONTRADICTION FOUND (scoped, not a safety verdict)"


@dataclass
class Finding:
    claim: str
    kind: str
    verdict: str  # CONTRADICTED | SUPPORTED_BY_PRIOR_EVIDENCE | UNKNOWN | NOT_CONTRADICTED
    why: str
    evidence: list = field(default_factory=list)
    unknowns: list = field(default_factory=list)
    attention: bool = False   # unresolved, but a person should look (see --new-test-failures)
    meta: dict = field(default_factory=dict)


@dataclass
class Decision:
    status: str
    commit: str
    dirty: bool
    changed: list
    findings: list
    scope: str
    evidence: list
    unexamined: int = 0
    tests_touched: list = field(default_factory=list)


def _reality(repo: Path, base: str, changed_override=None):
    snap = R.snapshot(repo)
    changed = R.changed_files(repo, base) if changed_override is None else list(changed_override)
    graph = R.build_graph(repo)
    return snap, changed, graph


def check(repo: Path, base: str, transcript: str, extra_evidence=None, new_test_failures: str = "unknown", message_missing: bool = False,
          changed_override=None) -> Decision:
    extracted = C.extract(transcript)
    unexamined = C.count_unexamined(transcript, extracted)
    try:
        snap, changed, graph = _reality(repo, base, changed_override)
    except R.CollectorError as e:
        f = [Finding(c.text, c.kind, "UNKNOWN", f"could not observe the repository: {e}") for c in extracted]
        return Decision(INSUFFICIENT, "?", False, [], f or [Finding("(none)", "none", "UNKNOWN", str(e))],
                        "collector failed", [])
    evidence = R.load_prior_evidence(repo, snap) + list(extra_evidence or [])
    changed_py = [f for f in changed if f.endswith(".py") and f in graph.imports]
    for f in changed:   # a changed Python file the graph does not know (odd file name, unreadable, new type) must not silently vanish from the analysis
        if f.endswith(".py") and f not in graph.imports and (repo / f).is_file():
            graph.gaps.append(f"changed file not analysed: {f}")
    findings = []
    for c in extracted:
        if c.kind == C.NO_IMPACT:
            findings.append(_no_impact(c, changed, changed_py, graph))
        elif c.kind == C.TESTS_PASS:
            findings.append(_tests(c, evidence, snap, changed, repo))
        elif c.kind == C.BACKCOMPAT:
            findings.append(_compat(c, repo, base, changed))
        else:
            findings.append(Finding(c.text, c.kind, "UNKNOWN", "Agentvow has no check for this kind of claim; it is unverified."))
    touched = [f for f in changed if R.is_test(f) and R.existed_at(repo, base, f)]
    if touched:
        for f in findings:
            if f.kind == C.TESTS_PASS and f.verdict == "SUPPORTED_BY_PRIOR_EVIDENCE":
                f.verdict = "NOT_CONTRADICTED"
                f.why += (f" However this change modified existing test file(s) ({', '.join(touched[:3])}"
                          f"{', …' if len(touched) > 3 else ''}), and a green run does not show the tests still test what they did before.")
    if message_missing:
        findings.append(Finding("(the agent's message for this turn could not be read)", "none", "UNKNOWN",
                                "Agentvow did not receive the agent's final message (the transcript did not contain it in time, or its format is not understood), "
                                "so nothing was verified. This is not evidence that the agent made no claims."))
    elif not extracted:
        findings.append(Finding("(no checkable claims found)", "none", "UNKNOWN",
                                "The message made no claim Agentvow can check. Nothing was verified."))
    if new_test_failures == "review":
        for f in findings:
            n = f.meta.get("new_test_failures", 0)
            if n:
                f.attention = True
                f.why += (f" Policy 'review': {n} failing test(s) were added or changed by this change, so there is no baseline. If they do not "
                          "depend on the network or services, the agent's claim is probably false; a person should look.")
    if any(f.verdict == "CONTRADICTED" or f.attention for f in findings):
        status = REVIEW
    elif any(f.verdict == "UNKNOWN" for f in findings) or graph.gaps:
        status = INSUFFICIENT
    else:
        status = NO_CONTRA
    scope = "Python imports + tests discovered by naming convention; static analysis only"
    return Decision(status, snap.commit, snap.dirty, changed, findings, scope, evidence, unexamined, touched)


def _gap_summary(gaps: list) -> str:
    """Say WHAT could not be analysed (by folder), not just that something could not."""
    from collections import Counter
    unsup = [g.split(": ", 1)[1] for g in gaps if g.startswith("unsupported language")]
    other = len(gaps) - len(unsup)
    parts = []
    if unsup:
        dirs = Counter(u.split("/")[0] if "/" in u else "(top level)" for u in unsup)
        parts.append("non-Python code Agentvow cannot analyse (" + ", ".join(f"{n} file(s) in {d}" for d, n in dirs.most_common(3)) +
                     "); such code could still depend on the changed files, for example through an HTTP API or a subprocess call")
    if other:
        parts.append(f"{other} other item(s) that could not be read or have dynamic imports")
    return "No Python consumers were found, but " + "; and ".join(parts) + "."


def _no_impact(c, changed, changed_py, graph) -> Finding:
    if not changed_py:
        return Finding(c.text, c.kind, "UNKNOWN", "No changed Python files were found, so the claim cannot be checked.")
    consumers, unknowns = {}, []
    changed_set = set(changed)
    gone = [f for f in changed if f.endswith(".py") and f not in graph.imports and not R.is_test(f)]
    if gone:
        return Finding(c.text, c.kind, "UNKNOWN",
                       "Some changed Python files no longer exist (deleted or renamed), so Agentvow cannot tell who depended on them.",
                       unknowns=[f"missing: {g}" for g in gone[:6]])
    for f in changed_py:
        for d in graph.dependents(f):
            if d not in changed_set and not R.is_test(d):
                consumers.setdefault(d, []).append(f)
    if consumers:
        rev_tests = {}
        for d in consumers:
            tests = [t for t in graph.dependents(d) if R.is_test(t)]
            if not tests:
                unknowns.append(f"{d} has no test that reaches it")
        names = ", ".join(sorted(consumers))
        return Finding(c.text, c.kind, "CONTRADICTED",
                       f"The agent said there is no downstream impact, but {len(consumers)} other module(s) depend on "
                       f"what changed: {names}.", evidence=[f"import graph at snapshot: {k} imports {', '.join(v)}" for k, v in consumers.items()],
                       unknowns=unknowns)
    if graph.gaps:
        return Finding(c.text, c.kind, "UNKNOWN",
                       _gap_summary(graph.gaps), unknowns=list(graph.gaps))
    return Finding(c.text, c.kind, "NOT_CONTRADICTED",
                   "No other Python module imports the changed code. This does not cover runtime, config or other languages.")


def _compat(c, repo, base, changed) -> Finding:
    py = [f for f in changed if f.endswith(".py") and not R.is_test(f)]
    if not py:
        return Finding(c.text, c.kind, "UNKNOWN", "No changed non-test Python files were found, so the claim cannot be checked.")
    found, gaps = api_diff.diff(repo, base, py)
    if found:
        return Finding(c.text, c.kind, "CONTRADICTED",
                       f"The agent said the change is backward compatible, but the public API changed in {len(found)} way(s).",
                       evidence=found[:8])
    if gaps:
        return Finding(c.text, c.kind, "UNKNOWN", "Some changed files could not be compared.", unknowns=gaps)
    return Finding(c.text, c.kind, "NOT_CONTRADICTED",
                   "No removed names or incompatible signature changes in changed Python files. Behaviour changes, "
                   "other languages, config and runtime compatibility are not checked.")


CI_CONFIG = (".github/workflows/", ".github/actions/", ".circleci/", ".gitlab-ci", "azure-pipelines", "jenkinsfile", ".travis.yml", "buildkite", "tox.ini", "noxfile.py")


DEP_MANIFESTS = ("pyproject.toml", "setup.py", "setup.cfg", "requirements", "poetry.lock", "uv.lock", "pipfile", "environment.yml", "constraints", "tox.ini")


def _dep_manifests_changed(changed) -> list:
    return [f for f in changed if any(m in f.lower().rsplit("/", 1)[-1] for m in DEP_MANIFESTS)]


def _ci_config_changed(changed) -> list:
    return [f for f in changed if any(m in f.lower() for m in CI_CONFIG)]


def _runner_meta(runs) -> dict:
    sup = sorted({e.runner_supplied for e in runs if getattr(e, "runner_supplied", "") and e.basis == "recipe"})
    return {"runner_supplied": ", ".join(sup)} if sup else {}


def _tests(c, evidence, snap, changed=(), repo=None) -> Finding:
    valid = [e for e in evidence if e.freshness == "VALID" and e.independence["mechanism"] == "separate"]
    runs = [e for e in valid if e.counts]
    agent_only = [e for e in evidence if e.freshness == "VALID" and e.independence["mechanism"] == "same"]
    stale = [e for e in evidence if e.freshness == "STALE"]
    ci = [e for e in valid if e.type == "ci_check"]
    if ci:
        bad = [e for e in ci if e.detail.startswith("fail")]
        if bad:
            return Finding(c.text, c.kind, "CONTRADICTED",
                           "The agent said tests pass, but the project's CI reports failing test job(s) on this exact commit: "
                           + "; ".join(e.raw_reference.split(":", 1)[-1] for e in bad[:4]) + ".", evidence=[e.raw_reference for e in bad])
        good = [e for e in ci if e.detail.startswith("pass")]
        edited = _ci_config_changed(changed)
        if good and not runs and edited:   # the change under review edited how CI decides pass/fail: its green result proves much less
            return Finding(c.text, c.kind, "NOT_CONTRADICTED",
                           "The project's CI reports passing test job(s) on this exact commit, but this change also edits CI/test configuration ("
                           + ", ".join(edited[:3]) + (", …" if len(edited) > 3 else "") + "), so the green result may not mean the tests ran or still test what they did. "
                           "CI also does not check the count the agent gave.", evidence=[e.raw_reference for e in good])
        if good and not runs:
            return Finding(c.text, c.kind, "SUPPORTED_BY_PRIOR_EVIDENCE",
                           "The project's CI reports passing test job(s) on this exact commit. CI runs separately from the agent, but the change under review can edit the CI configuration, and CI does not check the count the agent gave.",
                           evidence=[e.raw_reference for e in good])
    if runs:
        f = _from_runs(c, runs)
        rec_runs = [e for e in runs if e.basis == "recipe" and e.executed_files is not None]
        if rec_runs and f.verdict in ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED"):
            ran = set().union(*[set(e.executed_files) for e in rec_runs])
            defined = [x for x in changed if re.fullmatch(r"(?:.*/)?(?:test_[^/]*|[^/]*_test)\.py", x) and (repo is None or (Path(repo) / x).is_file())]
            skipped = [x for x in defined if x not in ran]
            if skipped:   # a recipe whose test command skips the tests this change added or changed proves nothing about them (found by the adversarial review plan)
                return Finding(c.text, c.kind, "UNKNOWN",
                               "The agent's declared recipe replayed, but its test command did not execute the test file(s) this change added or changed: "
                               + ", ".join(skipped[:3]) + (", …" if len(skipped) > 3 else "") + ". The replay therefore says nothing about them.",
                               evidence=f.evidence, attention=True, meta={"narrowed": skipped})
        sc = [e for e in rec_runs if e.scoped and e.scoped.get("files") and e.counts.get("regressions", 0) == 0 and e.counts.get("uncomparable", 0) == 0]
        if f.verdict == "UNKNOWN" and sc and all(e.scoped["failed"] == 0 and e.scoped["passed"] > 0 for e in sc):
            e = sc[0]   # the declared command ran more than the claim covers; the tests this change added or changed pass, the rest fail with and without the change
            return Finding(c.text, c.kind, "NOT_CONTRADICTED",
                           f"In the replay of the agent's declared recipe, the {e.scoped['passed']} test(s) this change added or changed ({', '.join(e.scoped['files'][:3])}) pass. "
                           f"{e.counts.get('failed', 0) + e.counts.get('errors', 0)} other test(s) in the replay fail, and they fail without the change too, so 'all tests pass' is not shown. "
                           "Basis: the AGENT's own declared recipe; this does not show the repository reproduces it from its own setup instructions.",
                           evidence=f.evidence, attention=False, meta={"support_basis": "agent_recipe", "scope": "changed_tests", **_runner_meta(rec_runs)})
        if any(e.basis == "recipe" for e in runs) and f.verdict in ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED"):
            f.why += (" Basis: the AGENT's own declared recipe (conditioned support): the result holds under the conditions the agent declared; "
                      "this does not show the repository reproduces it from its own setup instructions.")
            f.meta = {**f.meta, "support_basis": "agent_recipe", **_runner_meta(runs)}
            if f.meta.get("runner_supplied"):
                f.why += (f" Agentvow installed {f.meta['runner_supplied']} itself because the recipe's test command uses it but the recipe does not declare it, so the recipe alone was not "
                          "enough to run the tests; the support is for the agent's declared conditions plus that runner.")
        deps = _dep_manifests_changed(changed)
        if f.verdict == "CONTRADICTED" and deps:
            # Found by the v2 detection study (foamlib#453, a false alarm): the test environment is built for ONE commit, so when the change itself edits
            # dependency declarations a "regression" can just be a version mismatch. Do not call it a contradiction; ask for a review.
            return Finding(c.text, c.kind, "UNKNOWN",
                           f.why + " However this change also edits dependency declarations (" + ", ".join(deps[:3]) + (", …" if len(deps) > 3 else "") +
                           "), and Agentvow's test environment was not built from them, so these failures may come from a dependency mismatch and not from the code. "
                           "Run the suite in an environment built from this change before relying on either result.", evidence=f.evidence, attention=True,
                           meta={**f.meta, "downgraded_from": "CONTRADICTED", "dependency_files": deps})
        return f
    usable = [e for e in valid if e.detail.startswith("pass")]
    if usable:
        return Finding(c.text, c.kind, "SUPPORTED_BY_PRIOR_EVIDENCE",
                       "A passing result from a separate tool exists for this exact state.",
                       evidence=[e.raw_reference for e in usable])
    if stale:
        return Finding(c.text, c.kind, "UNKNOWN",
                       "The only test evidence belongs to a different commit or working-tree state than the current one, so it is out of date.",
                       evidence=[f"{e.raw_reference} (commit {e.snapshot[:8]}, now {snap.commit[:8]})" for e in stale])
    if agent_only:
        return Finding(c.text, c.kind, "UNKNOWN",
                       "The only evidence was produced by the agent itself. That is its claim, not independent evidence.",
                       evidence=[e.raw_reference for e in agent_only])
    return Finding(c.text, c.kind, "UNKNOWN", "No test result was found for this state. Agentvow did not run the tests.")


def _from_runs(c, runs) -> Finding:
    refs = [e.raw_reference for e in runs]
    ok = [e for e in runs if not e.detail.startswith("inconclusive")]
    if not ok:
        return Finding(c.text, c.kind, "UNKNOWN",
                       f"The test run was inconclusive ({runs[0].detail}); it could not confirm or refute the claim.", evidence=refs)
    def tot(k):
        return sum(e.counts.get(k, 0) for e in ok)
    passed, failed, skipped = tot("passed"), tot("failed") + tot("errors"), tot("skipped")
    per = "; ".join(f"{e.suite or 'tests'}: {e.counts.get('passed', 0)} passed, {e.counts.get('failed', 0) + e.counts.get('errors', 0)} failed" for e in ok)
    ran = f"Agentvow ran {len(ok)} test suite(s) on this exact state ({per}); total {passed} passed, {failed} failed, {skipped} skipped."
    partial = f" {len(runs) - len(ok)} suite(s) were inconclusive and are not counted." if len(ok) < len(runs) else ""
    missing = sum(e.counts.get("missing", 0) for e in ok)
    if not failed and passed == 0:
        return Finding(c.text, c.kind, "UNKNOWN",
                       f"{ran} No test passed (everything was skipped or nothing ran), so the claim cannot be confirmed.{partial}", evidence=refs)
    if not failed and missing:
        return Finding(c.text, c.kind, "UNKNOWN",
                       f"{ran} {missing} test(s) that passed before the change are no longer reported (deleted, renamed, skipped or not collected), "
                       f"so a clean run does not show the suite is intact.{partial}", evidence=refs)
    sizes = {passed, passed + skipped} | {e.counts.get("passed", 0) for e in ok}
    totals = {passed + failed} | {e.counts.get("passed", 0) + e.counts.get("failed", 0) + e.counts.get("errors", 0) for e in ok}
    if failed:
        regs = [e.counts.get("regressions") for e in ok if e.counts.get("failed", 0) + e.counts.get("errors", 0)]
        if any(r for r in regs if r):
            return Finding(c.text, c.kind, "CONTRADICTED",
                           f"The agent said tests pass, but {ran} {sum(r for r in regs if r)} test(s) that passed before the change now fail.{partial}", evidence=refs)
        if any(r is None for r in regs):
            why = "Agentvow did not run the tests before the change, so it cannot tell whether the failures are new."
        elif sum(e.counts.get("uncomparable", 0) for e in ok):
            new_failing = 0 if any(e.counts.get("no_baseline") for e in ok) else sum(e.counts.get("uncomparable", 0) for e in ok)
            why = ("Some failing tests did not exist before the change (new or renamed), so there is nothing to compare them with; "
                   "they may reflect Agentvow's environment (for example, no network).")
        else:
            nfail = sum(e.counts.get("failed", 0) + e.counts.get("errors", 0) for e in ok)
            return Finding(c.text, c.kind, "UNKNOWN",
                           f"{ran} {nfail} test(s) fail in Agentvow's run, so 'all tests pass' was not observed. The same tests also fail without the "
                           f"change (likely Agentvow's environment, such as no network), and no test that passed before fails now.{partial} "
                           f"Whether they pass in the project's own setup is unknown.", evidence=refs)
        return Finding(c.text, c.kind, "UNKNOWN", f"{ran} {why}{partial} The claim could be neither confirmed nor refuted.", evidence=refs,
                       meta={"new_test_failures": locals().get("new_failing", 0)})
    if c.count is not None and c.count not in sizes:
        return Finding(c.text, c.kind, "UNKNOWN",
                       f"The agent reported {c.count} passing tests but {ran}{partial} The numbers differ, which may mean the agent ran a different set or configuration.",
                       evidence=refs)
    extra = f" It matches the agent's count of {c.count}." if c.count is not None else " The agent did not state a count."
    return Finding(c.text, c.kind, "SUPPORTED_BY_PRIOR_EVIDENCE" if not partial else "UNKNOWN", ran + extra + partial, evidence=refs)


def _t(x) -> str:
    """Plain-text output is shown in terminals and hook messages: strip control/format characters (an ESC sequence could overwrite the real STATUS
    line) and collapse newlines (a claim must not be able to start a fake line)."""
    import unicodedata
    return " ".join("".join(ch for ch in str(x) if unicodedata.category(ch) not in ("Cc", "Cf") or ch in " \n\t").split())


def render(d: Decision) -> str:
    lines = ["AGENTVOW", "", f"STATUS: {_t(d.status)}", f"Checked commit {_t(d.commit)[:8]}"
             + (" (including uncommitted changes)" if d.dirty else "") + f". Changed files: {', '.join(_t(c) for c in d.changed) or 'none'}.", ""]
    for f in d.findings:
        mark = {"CONTRADICTED": "✗", "SUPPORTED_BY_PRIOR_EVIDENCE": "✓", "NOT_CONTRADICTED": "~", "UNKNOWN": "?"}[f.verdict]
        lines += [f'{mark} The agent said: "{_t(f.claim)}"', f"   {f.verdict}: {_t(f.why)}"]
        lines += [f"   evidence: {_t(e)}" for e in f.evidence]
        lines += [f"   unknown:  {_t(u)}" for u in f.unknowns]
        lines.append("")
    if d.unexamined:
        lines.append(f"Not examined: {d.unexamined} other statement(s) in the agent's message were not checked by Agentvow.")
        lines.append("")
    lines += [f"Scope of this check: {_t(d.scope)}.",
              "This tool informs your decision; it does not approve, reject or merge anything."]
    return "\n".join(lines)
