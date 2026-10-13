"""Not-reproduced manifest: what a replay of this repository's tests does NOT recreate, recorded without judging it.

A replay rebuilds Python packages (and the interpreter version); it does not recreate environment-variable values, secrets, files that exist only on the agent's machine,
external programs, services, network access or the operating system. A test that depends on one of these can pass for the agent and fail or skip elsewhere. This module lists,
deterministically and by name only, where the code and tests *reference* such things. Listing an item is not a finding: it says "this was not recreated and may matter",
never "this is wrong". Static analysis only: nothing is executed, environment VALUES are never read, and an empty list is not proof that nothing is missing."""
import ast
import re
import subprocess
from pathlib import Path

from . import changedcov, reality

MAX_FILES, MAX_BYTES, MAX_NAMES = 300, 400_000, 12
_NETWORK_MODULES = {"requests", "httpx", "aiohttp", "urllib3", "websockets", "socket"}
_COMPOSE = re.compile(r"(^|/)(docker-compose[^/]*\.ya?ml|compose\.ya?ml|Dockerfile[^/]*|Vagrantfile|Procfile|\.env\.(example|sample|template))$")
_IGNORED_NOISE = re.compile(r"(^|/)(\.venv|venv|env|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|node_modules|\.agentvow|\.tox|\.nox|build|dist|\.claude|\.idea|\.vscode|\.cache|\.coverage|htmlcov)(/|$)|\.egg-info(/|$)|\.pyc$|\.DS_Store$")
_URL = re.compile(r"https?://[A-Za-z0-9.-]+\.[a-z]{2,}", re.I)


def _t(x) -> str:
    import unicodedata
    return " ".join("".join(ch for ch in str(x) if unicodedata.category(ch) not in ("Cc", "Cf") or ch in " ").split())[:80]


def _git(repo: Path, *args) -> str:
    try:
        return subprocess.run(["git", *reality.safe_prefix(repo), "-C", str(repo), *args], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _scan_files(repo: Path, changed: list) -> list:
    """Test files, conftest, and the changed source files: the code a replay of the tests actually reaches first."""
    tracked = [f for f in _git(repo, "ls-files", "-co", "--exclude-standard").splitlines() if f.endswith(".py")]
    chosen = [f for f in tracked if changedcov._TESTY.search(f)] + [f for f in changed if f.endswith(".py")]
    seen, out = set(), []
    for f in chosen:
        if f not in seen and (repo / f).is_file() and not (repo / f).is_symlink():
            seen.add(f); out.append(f)
    return out[:MAX_FILES]


def _env_name(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _scan_source(src: str, env: dict, programs: set, network: set, urls: set) -> None:
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError, RecursionError):
        return
    for n in ast.walk(tree):
        if isinstance(n, ast.Subscript):   # os.environ["X"]: required
            v = n.value
            if isinstance(v, ast.Attribute) and v.attr == "environ":
                name = _env_name(n.slice)
                if name:
                    env[name] = "required"
        elif isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == "get" and isinstance(f.value, ast.Attribute) and f.value.attr == "environ" and n.args:   # os.environ.get("X"[, default])
                name = _env_name(n.args[0])
                if name:
                    env.setdefault(name, "optional" if len(n.args) > 1 or n.keywords else "read")
            elif isinstance(f, ast.Attribute) and f.attr == "getenv" and n.args:
                name = _env_name(n.args[0])
                if name:
                    env.setdefault(name, "optional" if len(n.args) > 1 or n.keywords else "read")
            elif isinstance(f, ast.Attribute) and f.attr in ("run", "call", "check_call", "check_output", "Popen") and isinstance(f.value, ast.Name) and f.value.id == "subprocess" and n.args:
                a0 = n.args[0]
                if isinstance(a0, (ast.List, ast.Tuple)) and a0.elts and isinstance(a0.elts[0], ast.Constant) and isinstance(a0.elts[0].value, str):
                    programs.add(Path(a0.elts[0].value).name)
                elif isinstance(a0, ast.Constant) and isinstance(a0.value, str) and a0.value.strip():
                    programs.add(Path(a0.value.split()[0]).name)
            elif isinstance(f, ast.Attribute) and f.attr == "which" and n.args and _env_name(n.args[0]):
                programs.add(Path(_env_name(n.args[0])).name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
            for m in mods:
                root = m.split(".")[0]
                if root in _NETWORK_MODULES or m.startswith("urllib.request") or m.startswith("http.client"):
                    network.add(root if root in _NETWORK_MODULES else m)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) < 300:
            m = _URL.search(n.value)
            if m and "localhost" not in n.value and "127.0.0.1" not in n.value and "example." not in n.value:
                urls.add(m.group(0).split("//")[1])


def build(repo: Path, changed: list, capsule: dict | None = None, replay_python: str = "", replay_platform: str = "") -> dict:
    """-> {"items": [{"category", "names", "note"}], "scanned": n, "caveat": str}. Names only."""
    repo = Path(repo).resolve()
    files = _scan_files(repo, changed)
    env, programs, network, urls = {}, set(), set(), set()
    for f in files:
        try:
            p = repo / f
            if p.stat().st_size > MAX_BYTES:
                continue
            _scan_source(p.read_text(errors="replace"), env, programs, network, urls)
        except OSError:
            continue
    items = []
    if env:
        req = sorted(k for k, v in env.items() if v == "required"); rest = sorted(k for k, v in env.items() if v != "required")
        items.append({"category": "environment variables", "names": [f"{_t(k)} (required: read with os.environ[...])" for k in req[:MAX_NAMES]] + [f"{_t(k)}" for k in rest[:MAX_NAMES]],
                      "note": "The replay supplies none of the agent's variable values (and never records them). Tests that read these may fail, skip or take another branch."})
    if programs:
        items.append({"category": "external programs the tests invoke", "names": sorted(_t(p) for p in programs)[:MAX_NAMES],
                      "note": "Not part of a Python package capture; the replay machine may not have them or may have other versions."})
    if network or urls:
        items.append({"category": "network use", "names": sorted(_t(x) for x in network)[:MAX_NAMES] + sorted(_t(u) for u in urls)[:MAX_NAMES],
                      "note": "Tests run in a sandbox without network access; tests that need it fail or skip in the replay even if they passed for the agent."})
    svc = sorted(f for f in _git(repo, "ls-files", "-co", "--exclude-standard").splitlines() if _COMPOSE.search(f))
    if svc:
        items.append({"category": "service and environment files present", "names": [_t(f) for f in svc[:MAX_NAMES]],
                      "note": "The repository describes services or an environment (containers, process files, example variables) that the replay does not start or read."})
    ign = []
    for line in _git(repo, "status", "--porcelain", "--ignored", "--", ".", ":(exclude).agentvow").splitlines():
        if line.startswith("!!"):
            path = line[3:].strip().strip('"')
            if not _IGNORED_NOISE.search(path):
                ign.append(path)
    if ign:
        items.append({"category": "git-ignored files in the working tree", "names": [_t(x) for x in sorted(ign)[:MAX_NAMES]],
                      "note": "These exist on this machine but not in a fresh clone; if a test reads one (a generated fixture, a local data file, a cache) a clone cannot reproduce it."})
    if capsule and replay_python:
        cv = ".".join(str(capsule.get("python_version", "")).split(".")[:2]); rv = ".".join(replay_python.split(".")[:2])
        diff = []
        if cv and rv and cv != rv:
            diff.append(f"Python {cv} when captured, {rv} in the replay")
        if capsule.get("platform") and replay_platform and capsule["platform"] != replay_platform:
            diff.append(f"{capsule['platform']} when captured, {replay_platform} in the replay")
        if diff:
            items.append({"category": "interpreter or operating system differs", "names": diff,
                          "note": "The replay runs on the machine where Agentvow runs; packages pinned for one Python version or platform may not install or behave the same on another."})
    return {"items": items, "scanned": len(files), "caveat": "Static, by name only; a reference is not proof that a test needs the item, and an empty list is not proof that nothing is missing."}


def render_text(m: dict) -> list:
    o = ["4. Not reproduced by this replay (recorded, not judged)"]
    if not m["items"]:
        o.append(f"   Nothing of these kinds was found in {m['scanned']} scanned file(s). {m['caveat']}")
    for it in m["items"]:
        o.append(f"   - {it['category']}: " + ", ".join(it["names"]) + f". {it['note']}")
    if m["items"]:
        o.append(f"   ({m['caveat']})")
    return o + [""]


def render_markdown(m: dict, esc) -> list:
    o = ["", "**4. Not reproduced by this replay** (recorded, not judged)"]
    if not m["items"]:
        o.append(f"Nothing of these kinds was found in {m['scanned']} scanned file(s). {esc(m['caveat'], 200)}")
    for it in m["items"]:
        o.append(f"- **{esc(it['category'])}:** " + ", ".join(f"`{esc(n)}`" for n in it["names"]) + f". {esc(it['note'], 220)}")
    return o + [""]


def render_html(m: dict, e) -> str:
    if not m["items"]:
        body = f"<p>Nothing of these kinds was found in {m['scanned']} scanned file(s). <small>{e(m['caveat'])}</small></p>"
    else:
        body = "<ul>" + "".join(f"<li><b>{e(it['category'])}:</b> " + ", ".join(f"<code>{e(n)}</code>" for n in it["names"]) + f". {e(it['note'])}</li>" for it in m["items"]) + f"</ul><p><small>{e(m['caveat'])}</small></p>"
    return f"<div><b>4 · Not reproduced by this replay</b>(recorded, not judged){body}</div>"
