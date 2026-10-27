"""Run the linter an agent says is clean, on the files the change touched, and report what it says. The linter is an existing tool found on this machine's PATH (nothing is installed
or vendored here); it runs in the same sandbox as the tests, with the repository read-only and no network. A tool that is missing, a version that cannot be read, or an error is UNKNOWN.

A finding is the tool's own output on this machine, with the repository's own configuration: a different version of the tool may disagree, so the version is always reported.

Hostile repositories (found by the adversarial review): flake8 runs Python named in the repository's own configuration (`local-plugins`), so flake8 is refused when it finds one; the tool's
raw output is never reported (it is repository-controlled text and the sandbox can read files outside the repository), only parsed `path CODE` pairs; the tool is looked up only in absolute PATH
entries outside the repository; a timeout kills the whole process group."""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import runner

# claim name -> (executable, arguments before the files). Static analysers/formatters only.
TOOLS = {
    "ruff check": ("ruff", ["check", "--no-cache", "--output-format=concise"]),
    "ruff format": ("ruff", ["format", "--check", "--no-cache"]),
    "black": ("black", ["--check", "--quiet"]),
    "flake8": ("flake8", []),
}
MAX_FILES = 200
_OK = (0,)
_FINDINGS = (1,)
CONFIG_FILES = ("pyproject.toml", "ruff.toml", ".ruff.toml", "setup.cfg", "tox.ini", ".flake8")
_LOCAL_PLUGINS = re.compile(r"local[-_]plugins", re.I)
_VIOLATION = re.compile(r"^(?P<path>[^\s:][^:\n]*):\d+(?::\d+)?:?\s+(?P<code>[A-Z]{1,5}\d{1,5})\b")
_REFORMAT = re.compile(r"^would reformat (?P<path>.+)$")


# A statement that only says "lint passes" names no tool. It is resolved from the repository's own configuration, never guessed: the Python linters the repository configures, and only when
# the change touches no other language (a "lint" about a TypeScript change is not about ruff).
_OTHER_LANGUAGE = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".swift", ".m", ".scala", ".dart", ".ex", ".exs", ".vue", ".svelte")
HOOK_TOOLS = {"ruff": "ruff check", "ruff-check": "ruff check", "ruff-format": "ruff format", "black": "black", "flake8": "flake8"}
GENERIC = ("lint", "format", "pre-commit")


def _text(repo: Path, name: str) -> str:
    try:
        return (Path(repo) / name).read_text(errors="replace")[:300_000]
    except OSError:
        return ""


def configured(repo: Path) -> dict:
    """{"ruff": file, "black": file, "flake8": file} for the runnable tools the repository configures (value: where), found by reading its files; nothing is executed."""
    out = {}
    pyproject, setup_cfg, tox = _text(repo, "pyproject.toml"), _text(repo, "setup.cfg"), _text(repo, "tox.ini")
    if re.search(r"^\[tool\.ruff[\].]", pyproject, re.M):
        out["ruff"] = "pyproject.toml [tool.ruff]"
    for n in ("ruff.toml", ".ruff.toml"):
        if (Path(repo) / n).is_file():
            out["ruff"] = n
    if re.search(r"^\[tool\.black\]", pyproject, re.M):
        out["black"] = "pyproject.toml [tool.black]"
    if (Path(repo) / ".flake8").is_file():
        out["flake8"] = ".flake8"
    elif re.search(r"^\[flake8\]", setup_cfg, re.M):
        out["flake8"] = "setup.cfg [flake8]"
    elif re.search(r"^\[flake8\]", tox, re.M):
        out["flake8"] = "tox.ini [flake8]"
    return out


def hooks(repo: Path) -> list:
    """The hook ids of .pre-commit-config.yaml, read as text (no YAML parser, nothing executed)."""
    return re.findall(r"^\s*-?\s*id:\s*['\"]?([\w.\-]+)", _text(repo, ".pre-commit-config.yaml"), re.M)[:80]


def resolve(repo: Path, generic: str, changed: list):
    """-> (tools, notes, blocked). tools: concrete runner names; notes: what was resolved or left out; blocked: why a generic statement cannot be resolved (then tools is empty)."""
    other = sorted({f.rsplit(".", 1)[-1] for f in changed if f.lower().endswith(_OTHER_LANGUAGE)})
    if other:
        return [], [], f"the change also touches {', '.join('.' + x for x in other[:3])} files, so 'lint' may mean another language's linter, which Agentvow cannot run"
    conf = configured(repo)
    notes = []
    if generic == "pre-commit":
        ids = hooks(repo)
        if not ids:
            return [], [], "there is no .pre-commit-config.yaml to say which hooks run"
        tools = sorted({HOOK_TOOLS[i] for i in ids if i in HOOK_TOOLS})
        left = sorted({i for i in ids if i not in HOOK_TOOLS})
        if left:
            notes.append(f"{len(left)} other hook(s) were not run ({', '.join(left[:4])}{', ...' if len(left) > 4 else ''})")
        if not tools:
            return [], notes, "none of the repository's pre-commit hooks is a linter Agentvow can run"
        return tools, notes + [f"resolved from .pre-commit-config.yaml: {', '.join(tools)}"], None
    if generic == "format":
        tools = [t for t, k in (("ruff format", "ruff"), ("black", "black")) if k in conf]
    else:
        tools = [t for t, k in (("ruff check", "ruff"), ("flake8", "flake8")) if k in conf]
    if not tools:
        return [], [], "the repository configures none of ruff, black or flake8"
    return tools, [f"resolved from this repository's configuration: {', '.join(f'{t} ({conf[k]})' for t, k in (('ruff check', 'ruff'), ('flake8', 'flake8'), ('ruff format', 'ruff'), ('black', 'black')) if t in tools)}"], None


def trusted_path(repo: Path) -> str:
    """PATH for finding the tool: absolute entries only, none inside the repository (a repository-relative or empty entry would pick the repository's own `ruff`)."""
    real = os.path.realpath(str(repo))
    keep = []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if d and os.path.isabs(d):
            r = os.path.realpath(d)
            if r != real and not r.startswith(real + os.sep):
                keep.append(d)
    return os.pathsep.join(keep)


def runs_repository_code(repo: Path, tool: str) -> str | None:
    """Why this tool must not be run on this repository, or None. flake8 imports plugins named in the repository's configuration."""
    if tool != "flake8":
        return None
    for name in ("setup.cfg", "tox.ini", ".flake8"):
        try:
            if _LOCAL_PLUGINS.search((Path(repo) / name).read_text(errors="replace")[:200_000]):
                return f"{name} names flake8 local plugins, which would run code from the repository"
        except OSError:
            continue
    return None


def parse(tool: str, lines: list, allowed: set) -> list:
    """['path CODE', ...] from the tool's output; only paths this run was given and codes that look like codes. Everything else in the output is dropped."""
    out = []
    for ln in lines:
        reformat = tool in ("ruff format", "black")
        m = (_REFORMAT if reformat else _VIOLATION).match(ln)
        if not m:
            continue
        path = m.group("path").strip()
        path = path[2:] if path.startswith("./") else path
        if path not in allowed:
            continue
        out.append(f"{path} would be reformatted" if reformat else f"{path} {m.group('code')}")
    return out


def run(repo: Path, tool: str, files: list, timeout: int = 120) -> dict:
    """-> {"status": clean|findings|error|unavailable, "version", "summary", "findings": int, "files": int, "lines": [parsed 'path CODE']}"""
    def res(status, summary="", version="", n=0, files_=0, lines=None):
        return {"status": status, "summary": summary, "version": version, "findings": n, "files": files_, "lines": lines or []}
    spec = TOOLS.get(tool)
    if spec is None:
        return res("unavailable", f"Agentvow has no runner for '{tool}'.")
    why = runs_repository_code(repo, tool)
    if why:
        return res("unavailable", f"{tool} was not run: {why}.")
    exe = shutil.which(spec[0], path=trusted_path(repo))
    if exe is None:
        return res("unavailable", f"{spec[0]} is not installed in a trusted location here, so the claim could not be checked.")
    why = runner.sandbox_problem()
    if why:
        return res("unavailable", f"no sandbox to run {spec[0]} in ({why})")
    real = Path(repo).resolve()
    keep = []
    for f in files[:MAX_FILES]:
        p = real / f
        if f.endswith(".py") and p.is_file() and not p.is_symlink() and not f.startswith("-"):
            keep.append(f)
    if not keep:
        return res("unavailable", "no changed Python file to lint")
    scratch = Path(tempfile.mkdtemp(prefix="al", dir=runner.scratch_base())).resolve()
    try:
        env = {"PATH": trusted_path(repo), "HOME": str(scratch), "TMPDIR": str(scratch), "XDG_CACHE_HOME": str(scratch), "RUFF_CACHE_DIR": str(scratch), "BLACK_CACHE_DIR": str(scratch),
               "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1"}

        def sandboxed(argv, secs):   # the repository is read-only: only the scratch directory is writable; the whole process group dies on timeout
            return runner._run_group(runner.wrap(argv, scratch, scratch, env=env, readonly=[real]), real, env, secs)

        try:
            vout, _ = sandboxed([exe, "--version"], 30)
            version = vout.strip().splitlines()[0][:60] if vout.strip() else ""
            out, rc = sandboxed([exe, *spec[1], "--", *keep], timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            return res("error", f"{spec[0]} could not finish: {type(e).__name__}", files_=len(keep))
        lines = [x for x in out.strip().splitlines() if x.strip()]
        if rc in _OK:
            return res("clean", "", version, 0, len(keep))
        if rc in _FINDINGS:
            parsed = parse(tool, lines, set(keep))
            return res("findings", f"{spec[0]} reported findings", version, len(parsed) or 1, len(keep), parsed[:8])
        return res("error", f"{spec[0]} exited with status {rc}", version, 0, len(keep))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
