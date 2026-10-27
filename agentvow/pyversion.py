"""Pick the Python interpreter a reconstructed environment is built with, from what the repository itself says it supports, instead of whatever interpreter happens to run Agentvow.

Evidence, in order: `.python-version` (a pin), the Python versions the repository's own CI workflows test, and `requires-python` (a constraint every candidate must satisfy). Only interpreters
already installed on this machine are used (found by name on PATH, in pyenv's versions folder, and the running interpreter); nothing is downloaded. Files are read as text, nothing is executed
except `python -m venv` of the chosen interpreter. When no installed interpreter satisfies the constraint, the running interpreter is kept and the mismatch is reported."""
import os
import re
import shutil
import sys
from pathlib import Path

_OPS = {">=": lambda v, w: v >= w, ">": lambda v, w: v > w, "<=": lambda v, w: v <= w, "<": lambda v, w: v < w}


def _ver(text: str):
    m = re.fullmatch(r"\s*(\d+)\.(\d+)(?:\.(\d+|\*))?\s*", text)
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_spec(spec: str):
    """A predicate over (major, minor) for a requires-python string like '>=3.10,<3.13', or None when it cannot be read. Patch levels are ignored."""
    clauses = []
    for part in str(spec or "").replace("'", "").replace('"', "").split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(>=|<=|==|!=|~=|>|<)\s*(\d+\.\d+(?:\.(?:\d+|\*))?)", part)
        if not m:
            return None
        op, v = m.group(1), _ver(m.group(2))
        if v is None:
            return None
        clauses.append((op, v, m.group(2).endswith(".*")))
    if not clauses:
        return None

    def ok(version):
        for op, v, star in clauses:
            if op in _OPS:
                if not _OPS[op](version, v):
                    return False
            elif op == "==":
                if version != v:
                    return False
            elif op == "!=":
                if version == v:
                    return False
            elif op == "~=":
                if not (version >= v and version[0] == v[0]):
                    return False
        return True
    return ok


def _text(repo: Path, rel: str) -> str:
    try:
        p = Path(repo) / rel
        return p.read_text(errors="replace")[:300_000] if p.is_file() and p.stat().st_size < 2_000_000 else ""
    except OSError:
        return ""


def declared(repo: Path) -> dict:
    """{"requires": 'spec' or None, "pinned": [(3, 12)], "ci": [(3, 11), (3, 12)]} read from the repository's files."""
    repo = Path(repo)
    requires = None
    for rel, pat in (("pyproject.toml", r"requires-python\s*=\s*[\"']([^\"']+)"), ("setup.cfg", r"python_requires\s*=\s*([^\n]+)"), ("setup.py", r"python_requires\s*=\s*[\"']([^\"']+)")):
        m = re.search(pat, _text(repo, rel))
        if m and parse_spec(m.group(1)):
            requires = m.group(1).strip()
            break
    pinned = []
    v = _ver(_text(repo, ".python-version").strip().splitlines()[0] if _text(repo, ".python-version").strip() else "")
    if v:
        pinned.append(v)
    ci = set()
    wf = repo / ".github" / "workflows"
    try:
        files = sorted(p for p in wf.iterdir() if p.suffix in (".yml", ".yaml"))[:20] if wf.is_dir() else []
    except OSError:
        files = []
    for f in files:
        for line in _text(repo, f"{'.github/workflows'}/{f.name}").splitlines():
            if re.search(r"python-versions?\s*:", line, re.I) or re.match(r"\s*-?\s*['\"]?3\.\d+['\"]?\s*,?\s*$", line):
                for x in re.findall(r"(?<![\d.])3\.(\d{1,2})(?![\d])", line):
                    ci.add((3, int(x)))
    return {"requires": requires, "pinned": pinned, "ci": sorted(ci)}


def installed() -> list:
    """[(version, path)] of interpreters present on this machine, found by name; the running interpreter is always included."""
    found = {}
    cur = (sys.version_info[0], sys.version_info[1])
    found[cur] = sys.executable
    for minor in range(8, 16):
        p = shutil.which(f"python3.{minor}")
        if p and (3, minor) not in found:
            found[(3, minor)] = p
    for root in (Path.home() / ".pyenv" / "versions",):
        try:
            for d in root.iterdir():
                m = re.fullmatch(r"3\.(\d+)\.\d+", d.name)
                py = d / "bin" / "python"
                if m and py.exists() and (3, int(m.group(1))) not in found:
                    found[(3, int(m.group(1)))] = str(py)
        except OSError:
            pass
    return sorted(found.items())


def choose(repo: Path, candidates=None):
    """-> (interpreter path, (major, minor), reason). Never raises; the running interpreter is the fallback."""
    cands = installed() if candidates is None else candidates
    cur = (sys.version_info[0], sys.version_info[1])
    cur_path = sys.executable
    d = declared(repo)
    ok = parse_spec(d["requires"]) if d["requires"] else (lambda v: True)
    allowed = [(v, p) for v, p in cands if ok(v)]
    if not allowed:
        why = f"no installed Python satisfies requires-python '{d['requires']}'; kept {cur[0]}.{cur[1]}" if d["requires"] else ""
        return cur_path, cur, why
    allowed_versions = {v for v, _ in allowed}
    target = None
    reason = ""
    for v in d["pinned"]:
        if v in allowed_versions:
            target, reason = v, f".python-version pins {v[0]}.{v[1]}"
            break
    if target is None and d["ci"]:
        tested = [v for v in d["ci"] if v in allowed_versions]
        if cur in tested:   # the running interpreter is one CI tests: nothing to change (the newest version of a matrix is the one most likely to lack wheels, so it is never preferred)
            return cur_path, cur, ""
        if tested:
            lower = [v for v in tested if v < cur]
            target = max(lower) if lower else min(tested)
            reason = f"the repository's CI tests {', '.join(f'{a}.{b}' for a, b in d['ci'][:5])}"
        else:   # CI tests versions that are not installed here: the closest allowed version to the newest one CI tests, preferring the lower
            want = max(v for v in d["ci"] if ok(v)) if any(ok(v) for v in d["ci"]) else max(d["ci"])
            target = min(allowed_versions, key=lambda v: (abs(v[1] - want[1]), v[1]))
            reason = f"the repository's CI tests {', '.join(f'{a}.{b}' for a, b in d['ci'][:5])}; the closest installed version is {target[0]}.{target[1]}"
    if target is None:
        target = cur if cur in allowed_versions else max(allowed_versions)
        reason = "" if target == cur else f"requires-python '{d['requires']}' excludes {cur[0]}.{cur[1]}"
    path = dict(allowed)[target]
    if target == cur:
        return cur_path, cur, ""
    return path, target, reason
