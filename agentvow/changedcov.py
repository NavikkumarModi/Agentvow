"""Changed-line coverage: of the executable source lines a change added or modified, how many did the independent test run actually execute?

A passing test run says nothing about changed code that no test reaches. This module is deterministic and verdict-neutral: it measures, it never decides. Lines are the unit
(symbols are not resolved); deleted-only changes and non-Python files cannot be measured. Uses `coverage` (an existing, mature tool) with an empty rc file so the project's own
coverage configuration (which can name plugins that execute code) is never loaded."""
import difflib
import json
import re
import subprocess
from pathlib import Path

_TESTY = re.compile(r"(^|/)(tests?|testing)(/|$)|(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$")
_DOCY = re.compile(r"\.(md|rst|txt)$|(^|/)docs?/|^LICENSE|^README|^CHANGELOG", re.I)


def is_source(path: str) -> bool:
    """A non-test, non-docs Python file."""
    return path.endswith(".py") and not _TESTY.search(path) and not _DOCY.search(path)


def added_lines(base_text: str, head_text: str) -> set:
    """New-side line numbers (1-based) of lines that are inserted or replaced in `head_text` relative to `base_text`."""
    a, b = base_text.splitlines(), head_text.splitlines()
    out = set()
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("insert", "replace"):
            out |= set(range(j1 + 1, j2 + 1))
    return out


def coverage_argv(argv: list, rcfile: str, datafile: str):
    """`[py, -m, pytest|unittest, ...]` -> the same command run under coverage, or None when the command is not a `python -m <module>` form."""
    if len(argv) >= 3 and argv[1] == "-m" and argv[2] in ("pytest", "unittest"):
        return [argv[0], "-m", "coverage", "run", "--rcfile", rcfile, "--data-file", datafile, *argv[1:]]
    return None


def export_json(py: str, rcfile: str, datafile: str, out: str, cwd, wrap=None) -> dict | None:
    """`wrap` (e.g. the platform sandbox) is applied to the command: the data file was written by a sandboxed test process and is read inside the sandbox too."""
    try:
        argv = [py, "-m", "coverage", "json", "--rcfile", rcfile, "--data-file", datafile, "-o", out]
        subprocess.run(wrap(argv) if wrap else argv, cwd=str(cwd), capture_output=True, text=True, timeout=120)
        return json.loads(Path(out).read_text())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def measure(changed: dict, cov: dict | None, head_root: Path) -> dict:
    """changed: {relative path: set of added new-side lines} for source files. cov: parsed `coverage json`. -> a verdict-neutral summary."""
    if cov is None:
        return {"available": False, "reason": "no coverage data (is `coverage` installed in the test environment?)"}
    files = cov.get("files", {})
    by_rel = {}
    for k, v in files.items():
        p = Path(k)
        try:
            by_rel[str(p.resolve().relative_to(Path(head_root).resolve()))] = v
        except ValueError:
            by_rel[k] = v
    executed = executable = 0
    not_run, not_loaded = {}, []
    for f, lines in sorted(changed.items()):
        v = by_rel.get(f)
        if v is None:
            if lines:
                not_loaded.append(f)
            continue
        ran, miss = set(v.get("executed_lines", [])), set(v.get("missing_lines", []))
        exe = {l for l in lines if l in ran or l in miss}
        executable += len(exe)
        executed += len({l for l in exe if l in ran})
        if exe - ran:
            not_run[f] = sorted(exe - ran)
    return {"available": True, "executed": executed, "executable": executable, "not_run": not_run, "not_loaded": not_loaded}


def ranges(lines: list) -> str:
    """[3,4,5,9] -> '3-5, 9'"""
    out, start, prev = [], None, None
    for n in sorted(lines):
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"{start}-{prev}" if prev != start else str(start)); start = prev = n
    if start is not None:
        out.append(f"{start}-{prev}" if prev != start else str(start))
    return ", ".join(out)


def sentence(cc: dict) -> str:
    """Plain-language statement for a report; '' when there is nothing to say."""
    if not cc or not cc.get("available"):
        return ""
    parts = []
    if cc["executable"]:
        parts.append(f"{cc['executed']} of {cc['executable']} changed executable source lines were run by the tests")
        if cc["not_run"]:
            parts.append("not run: " + "; ".join(f"{f} lines {ranges(l)}" for f, l in list(cc["not_run"].items())[:4]))
    if cc["not_loaded"]:
        parts.append("changed source file(s) never loaded by the tests: " + ", ".join(cc["not_loaded"][:4]))
    return ("Changed-line coverage: " + "; ".join(parts) + ".") if parts else ""
