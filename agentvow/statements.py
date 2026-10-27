"""Three more checkable kinds of statement an agent makes about its work, extracted by rules (no LLM) and decided from the repository alone:

  files_scope   "added `x.py`", "I did not touch `y.py`": which files were changed or left alone (git's own change list)
  docs_updated  "updated the README", "documented it in the docs": a documentation file was changed
  lint_clean    "ruff check passes": the named linter is run (lint.py) on the files the change touched

Conservative on purpose: a statement is extracted only when a verb governs a backticked path directly, and a path that cannot be resolved with certainty
(a bare file name that several files share, a path git ignores) gives UNKNOWN, never CONTRADICTED. Design and evaluation: docs/research/CHECKERS_FILES_DOCS_LINT.md."""
import re
from pathlib import Path

from . import reality as R

FILES_SCOPE = "files_scope"
DOCS_UPDATED = "docs_updated"
LINT_CLEAN = "lint_clean"

_EXT = {"py", "pyi", "md", "rst", "txt", "json", "toml", "yaml", "yml", "cfg", "ini", "html", "css", "js", "ts", "tsx", "jsx", "sh", "lock", "sample", "env", "conf", "xml", "csv", "ipynb", "c", "h", "cpp", "rs", "go", "java", "rb", "mdx", "adoc"}
_TOKEN = re.compile(r"`([^`\s]{1,200})`")
_ADD = r"added|created|wrote|written|introduced|modified|updated|changed|edited|fixed|patched|implemented|rewrote|refactored|extended|expanded|appended"
_REMOVE = r"removed|deleted"
_NOT = r"(?:did not|didn't|do not|don't|have not|haven't|will not|never|without|not)"
_TOUCH = r"(?:touch|touched|touching|modify|modified|modifying|change|changed|changing|edit|edited|editing|alter|altered|altering)"
_DET = r"(?:the|a|an|any|of|that|this|file|files|module|script|test|existing|new)"

_NEG_BEFORE = re.compile(rf"\b{_NOT}\s+(?:\w+\s+){{0,2}}?{_TOUCH}\s+(?:{_DET}\s+){{0,3}}$", re.I)
_NEG_BEFORE2 = re.compile(rf"\bno\s+(?:{_DET}\s+){{0,2}}(?:under|in|inside|within)\s+$", re.I)
_NEG_AFTER = re.compile(r"^\s*(?:itself\s+)?(?:was|were|is|are|remains?|stays?|has been|have been)?\s*(?:not\s+|n't\s+)?(?:touched|modified|changed|edited)\b|^\s*(?:was|were|is|are|remains?)\s+(?:untouched|unchanged)\b|^\s*(?:itself\s+)?(?:untouched|unchanged)\b", re.I)
_LEFT_BEFORE = re.compile(r"\bleft\s+(?:(?:the|file|files)\s+)*$", re.I)
_LEFT_AFTER = re.compile(r"^\s*(?:file\s+)?alone\b", re.I)
_POS_DIRECT = re.compile(rf"\b(?:{_ADD})\s+(?:(?:a|an|the|new|small|minimal)\s+){{0,3}}(?:file\s+|module\s+|script\s+|test file\s+)?$", re.I)
_POS_PREP = re.compile(rf"\b(?:{_ADD})\b([^.;:!?\n]{{0,80}})\b(?:to|in|into|under|of|at)\s+(?:the\s+)?(?:file\s+)?$", re.I)
_PREP_STOP = {"that", "which", "so", "because", "when", "with", "using", "uses", "use", "by", "from", "and", "or", "then", "if", "while", "for", "as", "copies", "reads", "loads", "calls", "returns", "writes", "makes", "makes", "than", "but"}


def _pos_prep(before: str) -> bool:
    """A change verb, then at most a few plain words (no second verb or conjunction), then to/in/into/under/of/at, then the path: "Added `x` support to `f.py`", "Fixed `f` in `g.py`"."""
    m = _POS_PREP.search(before)
    if not m:
        return False
    words = re.findall(r"[A-Za-z`]+", m.group(1))
    return len(words) <= 7 and not any(w.lower() in _PREP_STOP for w in words)
_REM_DIRECT = re.compile(rf"\b(?:{_REMOVE})\s+(?:(?:a|an|the|old|unused)\s+){{0,3}}(?:file\s+|module\s+|script\s+)?$", re.I)
_NEGATION_WORD = re.compile(r"\b(?:not|never|\w+n't|without|no)\b", re.I)
_FAILURE_WORD = re.compile(r"\b(?:not|never|\w+n't|cannot|unable|failed|fails?|failing|errors? out)\b", re.I)


def is_path(tok: str) -> bool:
    if not re.fullmatch(r"[\w./\-+@]+", tok) or tok.startswith(("/", "-", "..")) or "//" in tok:
        return False
    if tok.endswith("/"):
        return "/" in tok.rstrip("/") or len(tok) > 2
    ext = tok.rsplit(".", 1)[-1].lower() if "." in tok.rsplit("/", 1)[-1] else ""
    return ext in _EXT


def _clause(before: str) -> str:
    """The part of the text before a path that is in the same clause."""
    cut = max(before.rfind(c) for c in ".;!?\n")
    return before[cut + 1:] if cut >= 0 else before


def paths_in(sentence: str) -> list:
    out = []
    for m in _TOKEN.finditer(sentence):
        if is_path(m.group(1)):
            out.append((m.group(1).removeprefix("./"), m.start(), m.end()))
    return out


def _mask(sentence: str):
    """The sentence with every backticked token replaced by `T` (so dots inside code do not end a clause), and the path tokens with their positions in the masked text."""
    out, paths, last = [], [], 0
    masked = ""
    for m in _TOKEN.finditer(sentence):
        masked += sentence[last:m.start()]
        if is_path(m.group(1)) and not m.group(1).startswith(".agentvow"):   # Agentvow's own files (.agentvow-recipe.json) are not the agent's work
            paths.append((m.group(1).removeprefix("./"), len(masked), len(masked) + 3))
        masked += "`T`"
        last = m.end()
    return masked + sentence[last:], paths


def file_expectations(sentence: str) -> list:
    """[(path, "changed"|"unchanged"|"absent")] for the paths a verb in this sentence directly governs. Empty when nothing is certain."""
    masked, paths = _mask(sentence)
    out = []
    for path, s, e in paths:
        before, after = _clause(masked[:s]), re.split(r"[.;!?\n]", masked[e:e + 90])[0]
        if _NEG_BEFORE.search(before) or _NEG_BEFORE2.search(before) and _NEG_AFTER.search(after) or _LEFT_BEFORE.search(before) and _LEFT_AFTER.search(after) or _NEG_AFTER.search(after) and re.search(r"\b(?:not|n't|untouched|unchanged)\b", after[:40], re.I):
            out.append((path, "unchanged"))
        elif _NEGATION_WORD.search(before[-60:]) and not _REM_DIRECT.search(before):
            continue   # a negation near the path that is not one of the forms above: say nothing rather than guess
        elif _REM_DIRECT.search(before):
            out.append((path, "absent"))
        elif _POS_DIRECT.search(before) or _pos_prep(before):
            out.append((path, "changed"))
    seen, uniq = set(), []
    for p, x in out:
        if (p, x) not in seen:
            seen.add((p, x))
            uniq.append((p, x))
    return uniq[:8]


_DOCW = r"(readme|changelog|docs?|documentation)"
_DOCS = re.compile(rf"\b(?:updated|added|wrote|written|expanded|extended|revised|created|documented)\b[^.\n`]{{0,80}}?\b{_DOCW}\b|\bdocumented\b[^.\n]{{0,80}}\b(?:in|to)\b[^.\n]{{0,25}}?\b{_DOCW}\b", re.I)


def docs_target(sentence: str) -> str | None:
    """"readme" | "changelog" | "any" when the sentence says documentation was written or updated, else None."""
    m = _DOCS.search(sentence)
    if not m:
        return None
    word = next((g.lower() for g in m.groups() if g), "")
    if re.search(r"\bdocstrings?\b", sentence, re.I) and word.startswith("doc"):
        return None
    return {"readme": "readme", "changelog": "changelog"}.get(word, "any")


_DOC_EXT = (".md", ".rst", ".adoc", ".mdx")


def is_doc_file(path: str, target: str = "any") -> bool:
    name = path.rsplit("/", 1)[-1].lower()
    if target == "readme":
        return name.startswith("readme")
    if target == "changelog":
        return name.startswith(("changelog", "changes", "history", "news"))
    return name.startswith(("readme", "changelog", "changes", "history", "contributing")) or name.endswith(_DOC_EXT) or path.lower().startswith(("docs/", "doc/", "documentation/"))


_TOOLS = (("ruff format", re.compile(r"\bruff\s+format\b", re.I)), ("ruff check", re.compile(r"\bruff\b", re.I)), ("black", re.compile(r"\bblack\b", re.I)), ("flake8", re.compile(r"\bflake8\b", re.I)),
          ("isort", re.compile(r"\bisort\b", re.I)), ("mypy", re.compile(r"\bmypy\b", re.I)), ("pylint", re.compile(r"\bpylint\b", re.I)), ("pre-commit", re.compile(r"\bpre-commit\b", re.I)),
          ("lint", re.compile(r"\blint(?:ing|er|s)?\b", re.I)), ("format", re.compile(r"\bformat(?:ting|ter)?\b", re.I)))
_CLEAN = re.compile(r"\b(?:pass(?:es|ed|ing)?|clean|succe\w+|green|ok|no (?:issues|errors|warnings|problems|violations|findings|lint)|all checks passed|without (?:any )?(?:errors|issues|warnings))\b", re.I)


def lint_tools(sentence: str) -> list:
    """The linters this sentence says are clean/passing. `ruff format` also counts as ruff check only if both are named."""
    if not _CLEAN.search(sentence):
        return []
    found = []
    for name, pat in _TOOLS:
        if pat.search(sentence):
            if name == "ruff check" and re.search(r"\bruff\s+format\b", sentence, re.I) and not re.search(r"\bruff\s+(?:check|lint)\b|\bruff\b(?!\s+format)", sentence, re.I):
                continue
            found.append(name)
    if "lint" in found and any(t in found for t in ("ruff check", "flake8", "pylint")):
        found.remove("lint")
    if "format" in found and "ruff check" in found and "ruff format" not in found:   # "Ruff lint and format checks pass": both ruff modes
        found.append("ruff format")
    if "format" in found and any(t in found for t in ("ruff format", "black")):
        found.remove("format")
    return found


def extract_sentence(sentence: str) -> list:
    """[(kind, detail)] for the new kinds in one sentence."""
    out = []
    exp = file_expectations(sentence)
    if exp:
        out.append((FILES_SCOPE, {"checks": [{"path": p, "expect": x} for p, x in exp]}))
    if not _FAILURE_WORD.search(sentence):
        doc = docs_target(sentence)
        if doc and not any(is_doc_file(p, doc) for p, _ in exp):
            out.append((DOCS_UPDATED, {"target": doc}))
        for t in lint_tools(sentence):
            out.append((LINT_CLEAN, {"tool": t, "paths": sorted(set(re.findall(r"(?<![\w./\-])((?:[\w.\-]+/)*[\w\-]+\.py)\b", sentence)))[:8]}))
    return out


# ---- the checks -------------------------------------------------------------------------------------------------------------------------------------------

def _tracked(repo: Path) -> list:
    try:
        return [x for x in R._git(repo, "ls-files", "-z").split("\0") if x]
    except R.CollectorError:
        return []


def _ignored(repo: Path, path: str) -> bool:
    import subprocess
    return subprocess.run(["git", *R.safe_prefix(repo), "-C", str(repo), "check-ignore", "-q", "--", path], capture_output=True).returncode == 0


def resolve(repo: Path, changed: list, path: str, tracked: list):
    """-> (matches in the change list, ambiguous). A bare name matches by its last path components; a trailing slash matches a directory prefix."""
    if path.endswith("/"):
        return [f for f in changed if f.startswith(path)], False
    exact = [f for f in changed if f == path]
    if exact or "/" in path:
        if exact:
            return exact, False
        return [f for f in changed if f.endswith("/" + path)], False
    cand = [f for f in changed if f.endswith("/" + path) or f == path]
    same = [t for t in tracked if t == path or t.endswith("/" + path)]
    return cand, len(set(same) | set(cand)) > 1


def check_files(repo: Path, changed: list, detail: dict):
    """-> (verdict, why, evidence). CONTRADICTED only when a statement is certainly false; UNKNOWN when the path cannot be settled."""
    tracked = _tracked(repo)
    bad, unsure, ok = [], [], []
    for c in detail["checks"]:
        path, expect = c["path"], c["expect"]
        hits, ambiguous = resolve(repo, changed, path, tracked)
        exists = (repo / path).exists() if not path.endswith("/") else (repo / path).is_dir()
        if expect == "changed":
            if ambiguous:
                unsure.append(f"{path}: several files have this name")
            elif hits:
                ok.append(f"{path}: in the change list")
            elif exists and _ignored(repo, path.rstrip("/")):
                unsure.append(f"{path}: git ignores it, so the change list cannot show whether it changed")
            else:
                bad.append(f"{path}: said to be changed, but it is not in the change list")
        elif expect == "unchanged":
            if hits and not ambiguous:
                bad.append(f"{path}: said to be left alone, but it was changed ({', '.join(hits[:3])})")
            elif ambiguous:
                unsure.append(f"{path}: several files have this name")
            else:
                ok.append(f"{path}: not in the change list")
        else:   # absent
            if exists:
                bad.append(f"{path}: said to be removed, but it still exists")
            else:
                ok.append(f"{path}: does not exist")
    if bad:
        return "CONTRADICTED", "The repository contradicts what the agent said about files: " + "; ".join(bad[:3]) + ".", bad + ok
    if unsure:
        return "UNKNOWN", "Some files named by the agent could not be settled from git's change list: " + "; ".join(unsure[:3]) + ".", ok
    return "NOT_CONTRADICTED", "What the agent said about files agrees with git's change list (" + "; ".join(ok[:3]) + "). This checks which files changed, not what changed in them.", ok


def check_docs(changed: list, detail: dict):
    target = detail.get("target", "any")
    docs = [f for f in changed if is_doc_file(f, target)]
    if docs:
        return "NOT_CONTRADICTED", f"A documentation file was changed ({', '.join(docs[:3])}). This does not show that it says what the agent described.", docs
    if any(f.endswith(".py") for f in changed) and target == "any":
        return "UNKNOWN", "No documentation file changed. Documentation may have been written as docstrings or comments in source files, which this check does not read.", []
    label = {"readme": "a README", "changelog": "a changelog"}.get(target, "a documentation file")
    return "CONTRADICTED", f"The agent said documentation was updated, but {label} is not among the changed files.", []
