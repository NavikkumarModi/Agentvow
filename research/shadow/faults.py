"""Fault generator for the shadow-mode study (docs/strategy/SHADOW_STUDY_DESIGN_2026-10-27.md). Extends the E5 generator (operator flips on lines the agent added) with more fault types and a wider
scope: any line of a function the change touched, not only the added line. Every fault is a single-line text edit that must still parse (ast), differ from the original, and change code (not a comment
or string). No tool under test is used here; faults are authored by us, so results are pipeline sensitivity, not real-world detection.
Types: flip (operator flip), negate (`if x:` -> `if not (x):`), constant (True <-> False), return_none (`return expr` -> `return None`, never in a generator), offbyone (integer literal +1 in a comparison or index).
Text inside strings, f-strings and comments is never edited (found by the adversarial review of the first run: raw-text matching hit string contents); matching is done on a masked copy of each line and the edit is applied to the original at the same offsets."""
import ast
import io
import random
import re
import tokenize

FLIPS = [(" == ", " != "), (" != ", " == "), (" < ", " >= "), (" > ", " <= "), (" <= ", " > "), (" >= ", " < "), (" and ", " or "), (" or ", " and "), (" in ", " not in "), (" not in ", " in ")]
TYPES = ("flip", "negate", "constant", "return_none", "offbyone")


def _parses(src: str) -> bool:
    try:
        ast.parse(src)
        return True
    except (SyntaxError, ValueError):
        return False


def masked_lines(src: str) -> list:
    """The source lines with every string, f-string and comment character replaced by an underscore, so patterns never match inside them. Falls back to fully masked lines when tokenizing fails."""
    lines = src.splitlines(keepends=True)
    out = [list(l) for l in lines]
    skip = {tokenize.STRING, tokenize.COMMENT} | {getattr(tokenize, n) for n in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END") if hasattr(tokenize, n)}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in skip:
                (sr, sc), (er, ec) = tok.start, tok.end
                for r in range(sr, er + 1):
                    a = sc if r == sr else 0
                    b = ec if r == er else len(out[r - 1])
                    for c in range(a, min(b, len(out[r - 1]))):
                        if out[r - 1][c] not in "\r\n":
                            out[r - 1][c] = "_"
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return ["_" * len(l.rstrip("\r\n")) + l[len(l.rstrip("\r\n")):] for l in lines]
    return ["".join(l) for l in out]


def generator_lines(src: str) -> set:
    """Line numbers inside any function that yields: `return x` there only ends the generator early, so return_none is not a clean fault."""
    out = set()
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return out
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.end_lineno and any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in ast.walk(node)):
            out.update(range(node.lineno, node.end_lineno + 1))
    return out


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


def mutations(line: str, masked: str = None):
    """[(type, mutated line)] for one source line; each is textually different. `masked` is the same line with strings and comments blanked (defaults to the line itself)."""
    m_ = line if masked is None else masked
    out = []

    def sub(span, text):
        return line[:span[0]] + text + line[span[1]:]
    for a, z in FLIPS:
        i = m_.find(a)
        if i >= 0:
            out.append(("flip", sub((i, i + len(a)), z)))
    m = re.match(r"^(\s*)(if|elif)\s+(.+):\s*$", m_.rstrip("\r\n"))
    if m and not m.group(3).startswith("not "):
        cond = line[m.start(3):m.end(3)]
        out.append(("negate", sub((m.start(3), m.end(3)), f"not ({cond})")))
    for a, z in (("True", "False"), ("False", "True")):
        m = re.search(rf"\b{a}\b", m_)
        if m and not re.match(r"^\s*while\b", m_):
            out.append(("constant", sub(m.span(), z)))
    m = re.match(r"^(\s*)return\s+(?!None\b)(\S.*)$", m_.rstrip("\r\n"))
    if m:
        out.append(("return_none", line[:m.start(1)] + m.group(1) + "return None" + ("\n" if line.endswith("\n") else "")))
    m = re.search(r"(?<![\w.\[])(\d+)(?![\w.])", m_)
    if m and re.search(r"[<>]=?|==|\[", m_) and not re.match(r"^\s*(def|class)\b", m_):
        out.append(("offbyone", sub(m.span(1), str(int(m.group(1)) + 1))))
    return [(t, l) for t, l in out if l != line]


def candidates(src: str, scope: set) -> list:
    """All valid single-line faults on the lines in `scope` (1-based): [(line_number, type, mutated_line)]."""
    lines = src.splitlines(keepends=True)
    masks = masked_lines(src)
    gens = generator_lines(src)
    out = []
    for n in sorted(scope):
        if 0 < n <= len(lines) and _code_line(lines[n - 1]):
            for t, new in mutations(lines[n - 1], masks[n - 1]):
                if t == "return_none" and n in gens:
                    continue
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
