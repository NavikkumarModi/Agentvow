"""Evidence pack: one reviewer-facing summary with three SEPARATE dimensions of evidence, never compressed into a single badge.

1. Execution receipt: what ran, on which exact state, with what result.
2. Reproducibility: does the result reproduce from the environment captured when the agent ran its tests AND, separately, from the project's own setup? When they
   disagree the pack says what was observed. A captured package list is not proof that a fresh checkout is self-sufficient.
3. Changed-line coverage: which changed executable source lines the tests reached, and which no test reached (the lines are named; "executed" is not "asserted").
The pack informs a person; it never approves, rejects or merges, and it adds no verdict of its own."""
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import changedcov, envsetup

LIMITS = ("Python packages and the interpreter version are all that a captured environment covers (no system packages, services, generated files or secrets); "
          "a test run that reproduces is not a correct change; a line that ran is not a line that was checked.")


def _t(x) -> str:
    import unicodedata
    return " ".join("".join(ch for ch in str(x) if unicodedata.category(ch) not in ("Cc", "Cf") or ch in " \n\t").split())


def _context_from_evidence(d) -> dict | None:
    runs = [e for e in d.evidence if e.type == "prior_verification" and e.counts is not None and e.freshness == "VALID" and e.independence.get("mechanism") == "separate"]
    if not runs:
        return None
    e = runs[-1]
    name = {"capsule": "captured environment", "recipe": "the agent's declared recipe"}.get(e.basis, "project-native setup")
    result, _, summary = str(e.detail).partition(": ")
    return {"name": name, "basis": e.basis or "native", "available": True, "result": result or "unknown", "counts": dict(e.counts), "summary": _t(summary)[:240], "changed_cov": e.changed_cov}


def _native_context(a, repo: Path, base: str, collect) -> dict:
    """Run the SAME tests in an environment built from the project's own declarations (zero-config ladder). Nothing is written as evidence: this is an additional context."""
    venv_root = Path(tempfile.mkdtemp(prefix="agentvow_env_"))
    try:
        py, notes, aborted = envsetup.build_env(repo, venv_root / "venv", venv_root / "home")
        if not py or aborted:
            why = f"the environment could not be built ({aborted})" if aborted else ("; ".join(notes)[:160] or "the environment could not be built")
            return {"name": "project-native setup", "basis": "native", "available": True, "result": "not built", "counts": {}, "summary": _t(why)}
        recs = collect(repo, base, [("tests", [py, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider"], "", {})], a.test_timeout, return_records=True)
        h = recs[0] if recs else {}
        return {"name": "project-native setup", "basis": "native", "available": True, "result": h.get("result", "unknown"), "counts": h.get("counts", {}), "summary": _t(h.get("summary", ""))[:240]}
    finally:
        shutil.rmtree(venv_root, ignore_errors=True)


def explain(cap: dict | None, nat: dict | None) -> tuple[str, str]:
    """-> (code, plain-language reading) comparing the captured/declared context with the project-native one."""
    if cap is None and nat is None:
        return "none", "No test run produced usable evidence, so reproducibility could not be assessed."
    if cap is None or nat is None:
        c = cap or nat
        other = "the project's own setup" if cap else "the captured environment"
        return "single", (f"Only one context ran ({c['name']}: {c['result']}). The result from {other} is not available, so it is not known whether the result reproduces there"
                          + (" (run `agentvow capture` right after the agent's tests to add a captured-environment replay)." if cap is None else "."))
    cp, np_ = cap["result"] == "pass", nat["result"] == "pass"
    if cp and np_:
        return "both", "Reproduces both from the captured packages and from the project's own setup, so a fresh checkout is likely (not guaranteed) to reproduce it."
    if cp and not np_:
        return "captured_only", (f"Reproduces from the captured packages but NOT from the project's own setup ({nat['result']}: {nat['summary'] or 'no detail'}). "
                                 "Someone who clones the repository may not be able to reproduce it.")
    if np_ and not cp:
        return "native_only", (f"Passes with the project's own setup but not from the captured packages ({cap['result']}: {cap['summary'] or 'no detail'}); "
                               "the captured list may be incomplete or out of date.")
    return "neither", f"Neither context reproduced a pass (captured: {cap['result']}; project-native: {nat['result']})."


def _coverage_section(cov: dict | None, repo: Path) -> dict:
    if not cov:
        return {"available": False, "reason": "changed-line coverage was not measured"}
    if not cov.get("available"):
        return {"available": False, "reason": _t(cov.get("reason", "unavailable"))}
    items = []
    for f, lines in cov.get("not_run", {}).items():
        snippets = []
        try:
            src = (repo / f).read_text(errors="replace").splitlines()
            snippets = [f"{n}: {_t(src[n - 1])[:80]}" for n in lines[:3] if 0 < n <= len(src)]
        except OSError:
            pass
        items.append({"file": _t(f), "lines": changedcov.ranges(lines), "snippets": snippets})
    return {"available": True, "executed": cov["executed"], "executable": cov["executable"], "not_run": items, "not_loaded": [_t(x) for x in cov.get("not_loaded", [])]}


def build(a, repo: Path, base: str, d, collect) -> dict:
    primary = _context_from_evidence(d)
    cov = primary.pop("changed_cov", None) if primary else None
    contexts, cap, nat = [], None, None
    if primary and primary["basis"] in ("capsule", "recipe"):
        cap = primary
        nat = _native_context(a, repo, base, collect)
    elif primary:
        nat = primary
    contexts = [c for c in (cap, nat) if c]
    code, reading = explain(cap, nat)
    return {"version": 1,
            "receipt": {"commit": d.commit, "dirty": d.dirty, "base": base, "command": " ".join(a.test_cmd[0].split()[1:]) if getattr(a, "test_cmd", None) else "python -m pytest -q",
                        "replay_python": ".".join(map(str, sys.version_info[:3])), "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "valid_for": "this exact commit and working tree; any later edit makes it stale"},
            "contexts": contexts, "reproducibility": {"code": code, "text": reading},
            "coverage": _coverage_section(cov, Path(repo)), "limits": LIMITS}


def render_text(p: dict) -> list:
    r = p["receipt"]
    o = ["EVIDENCE PACK (three separate dimensions; not a score)", "",
         f"1. Execution receipt: `{_t(r['command'])}` on commit {_t(r['commit'])[:8]}{' + uncommitted changes' if r['dirty'] else ''}, compared with {_t(r['base'])}; valid for {r['valid_for']}."]
    for c in p["contexts"]:
        cn = c["counts"]
        o.append(f"   - {c['name']}: {c['result']}" + (f" ({cn.get('passed', 0)} passed, {cn.get('failed', 0)} failed)" if cn else "") + (f" - {c['summary']}" if c["result"] != "pass" and c["summary"] else ""))
    if not p["contexts"]:
        o.append("   - no test run produced usable evidence")
    o += ["", f"2. Reproducibility: {p['reproducibility']['text']}", ""]
    cv = p["coverage"]
    if not cv["available"]:
        o.append(f"3. Changed-line coverage: not available ({cv['reason']}).")
    else:
        o.append(f"3. Changed-line coverage: {cv['executed']} of {cv['executable']} changed executable source lines were run by the tests."
                 + ("" if cv["not_run"] or cv["not_loaded"] else " Nothing changed was left unrun."))
        for it in cv["not_run"][:6]:
            o.append(f"   - not run: {it['file']} lines {it['lines']}" + (f"  e.g. {it['snippets'][0]}" if it["snippets"] else ""))
        for f in cv["not_loaded"][:4]:
            o.append(f"   - never loaded by the tests: {f}")
    o += ["", f"Limits: {p['limits']}", ""]
    return o


def render_markdown(p: dict, esc) -> list:
    r = p["receipt"]
    o = ["### Evidence pack", "", f"**1. Execution receipt.** `{esc(r['command'])}` on `{esc(r['commit'])[:10]}`{' plus uncommitted changes' if r['dirty'] else ''}; valid for {esc(r['valid_for'])}.", ""]
    if p["contexts"]:
        o += ["| Context | Result | Detail |", "|---|---|---|"]
        for c in p["contexts"]:
            o.append(f"| {esc(c['name'])} | **{esc(c['result'])}** | {esc(c['summary'], 120) if c['result'] != 'pass' else ''} |")
        o.append("")
    o += [f"**2. Reproducibility.** {esc(p['reproducibility']['text'], 500)}", ""]
    cv = p["coverage"]
    if cv["available"]:
        o.append(f"**3. Changed-line coverage.** {cv['executed']} of {cv['executable']} changed executable source lines were run by the tests.")
        o += [f"- not run: `{esc(it['file'])}` lines {esc(it['lines'])}" for it in cv["not_run"][:6]]
        o += [f"- never loaded by the tests: `{esc(f)}`" for f in cv["not_loaded"][:4]]
    else:
        o.append(f"**3. Changed-line coverage.** Not available ({esc(cv['reason'])}).")
    o += ["", f"_Limits: {esc(p['limits'], 400)}_", ""]
    return o


def render_html(p: dict, e) -> str:
    r = p["receipt"]
    rows = "".join(f"<tr><td>{e(c['name'])}</td><td><b>{e(c['result'])}</b></td><td>{e(c['summary']) if c['result'] != 'pass' else ''}</td></tr>" for c in p["contexts"]) or "<tr><td colspan=3>no usable test run</td></tr>"
    cv = p["coverage"]
    if cv["available"]:
        cov = (f"<p><b>{cv['executed']} of {cv['executable']}</b> changed executable source lines were run by the tests.</p><ul>"
               + "".join(f"<li>not run: <code>{e(it['file'])}</code> lines {e(it['lines'])}" + (f" <code>{e(it['snippets'][0])}</code>" if it["snippets"] else "") + "</li>" for it in cv["not_run"][:6])
               + "".join(f"<li>never loaded by the tests: <code>{e(f)}</code></li>" for f in cv["not_loaded"][:4]) + "</ul>")
    else:
        cov = f"<p>Not available ({e(cv['reason'])}).</p>"
    return (f"<h2>Evidence pack</h2><p>Three separate dimensions, not a score.</p>"
            f"<div class=\"q\"><div><b>1 · Execution receipt</b><code>{e(r['command'])}</code> on <code>{e(r['commit'])[:10]}</code>{' + uncommitted changes' if r['dirty'] else ''}; valid for {e(r['valid_for'])}."
            f"<table>{rows}</table></div>"
            f"<div><b>2 · Reproducibility</b>{e(p['reproducibility']['text'])}</div>"
            f"<div><b>3 · Changed-line coverage</b>{cov}</div></div><p><small>Limits: {e(p['limits'])}</small></p>")
