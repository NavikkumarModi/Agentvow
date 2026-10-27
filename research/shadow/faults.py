"""Fault generator for the shadow-mode study (docs/strategy/SHADOW_STUDY_DESIGN_2026-10-27.md). Extends the E5 generator (operator flips on lines the agent added) with more fault types and a wider
scope: any line of a function the change touched, not only the added line. Every fault is a single-line text edit that must still parse (ast), differ from the original, and change code (not a comment
or string). No tool under test is used here; faults are authored by us, so results are pipeline sensitivity, not real-world detection.
Types: flip (operator flip), negate (`if x:` -> `if not x:`), constant (True/False, 0/1 swap), return_none (`return expr` -> `return None`), offbyone (integer literal +1 in a comparison or index)."""
import ast
import random
import re

FLIPS = [(" == ", " != "), (" != ", " == "), (" < ", " >= "), (" > ", " <= "), (" <= ", " > "), (" >= ", " < "), (" and ", " or "), (" or ", " and "), (" in ", " not in "), (" not in ", " in ")]
TYPES = ("flip", "negate", "constant", "return_none", "offbyone")


def _parses(src: str) -> bool:
    try:
        ast.parse(src)
        return True
    except (SyntaxError, ValueError):
        return False


def _code_line(line: str) -> bool:
    s = line.strip()
    return bool(s) and not s.startswith(("#", '"', "'", "@", "import ", "from ")) and not s.endswith((",", "\\"))


def touched_functions(src: str, changed: set) -> set:
    """Line numbers inside any function (or method) that contains a changed line; module-level changed lines contribute only themselves."""
    out = set(changed)
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return out
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.end_lineno:
            span = range(node.lineno, node.end_lineno + 1)
            if any(n in changed for n in span):
                out.update(span)
    return out


def mutations(line: str):
    """[(type, mutated line)] for one source line; each is textually different."""
    out = []
    for a, z in FLIPS:
        if a in line:
            out.append(("flip", line.replace(a, z, 1)))
    m = re.match(r"^(\s*)(if|elif|while)\s+(.+):\s*$", line.rstrip("\n"))
    if m and not m.group(3).startswith("not "):
        out.append(("negate", f"{m.group(1)}{m.group(2)} not ({m.group(3)}):" + ("\n" if line.endswith("\n") else "")))
    for a, z in (("True", "False"), ("False", "True")):
        if re.search(rf"\b{a}\b", line):
            out.append(("constant", re.sub(rf"\b{a}\b", z, line, count=1)))
    m = re.match(r"^(\s*)return\s+(?!None\b)(\S.*)$", line.rstrip("\n"))
    if m:
        out.append(("return_none", f"{m.group(1)}return None" + ("\n" if line.endswith("\n") else "")))
    m = re.search(r"(?<![\w.\[])(\d+)(?![\w.])", line)
    if m and re.search(r"[<>]=?|==|\[", line) and not re.match(r"^\s*(def|class)\b", line):
        out.append(("offbyone", line[:m.start()] + str(int(m.group(1)) + 1) + line[m.end():]))
    return [(t, l) for t, l in out if l != line]


def candidates(src: str, scope: set) -> list:
    """All valid single-line faults on the lines in `scope` (1-based): [(line_number, type, mutated_line)]."""
    lines = src.splitlines(keepends=True)
    out = []
    for n in sorted(scope):
        if 0 < n <= len(lines) and _code_line(lines[n - 1]):
            for t, new in mutations(lines[n - 1]):
                mutated = "".join(lines[:n - 1] + [new] + lines[n:])
                if _parses(mutated) and mutated != src:
                    out.append((n, t, new))
    return out


def pick(cands: list, seed, k: int = 3) -> list:
    """Up to k faults of different types, chosen deterministically from the seed."""
    rng = random.Random(seed)
    by = {}
    for c in cands:
        by.setdefault(c[1], []).append(c)
    chosen = []
    for t in rng.sample(sorted(by), len(by)):
        if len(chosen) < k:
            chosen.append(rng.choice(sorted(by[t])))
    return chosen


def apply(src: str, fault) -> str:
    n, _t, new = fault
    lines = src.splitlines(keepends=True)
    lines[n - 1] = new
    return "".join(lines)
