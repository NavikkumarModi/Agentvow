"""`agentvow init`: add Agentvow's two Claude Code hooks to a settings file, with a preview, a confirmation and a backup. It never edits anything silently.

What is written (the shape verified on real Claude Code runs, docs/LIVE_TESTING.md):
  PostToolUse (matcher Bash): `agentvow post-test-hook`          records the agent's Python packages right after it runs a test command
  Stop:                       `agentvow check --hook --evidence-pack`   checks the turn when the agent stops; never blocks
Default target is the project's `.claude/settings.local.json` (personal, normally not committed). `--shared` writes `.claude/settings.json` (committed settings would run the
hooks for every teammate), `--user` writes `~/.claude/settings.json`. Only entries this command owns (a command containing `agentvow` with one of the two subcommands) are
added, replaced or removed; every other setting and hook is kept. An unreadable settings file is never overwritten."""
import json
import os
import shlex
import shutil
import sys
import time
from pathlib import Path

POST = ("post-test-hook",)
STOP = ("check", "--hook", "--evidence-pack")
STOP_OWNED = ("check", "--hook")   # an older Agentvow Stop hook (without --evidence-pack) is also ours: replaced, so the check does not run twice
POST_TIMEOUT, STOP_TIMEOUT = 30, 60


def command_prefix() -> str:
    """How Claude Code should start Agentvow: the `agentvow` script beside the interpreter running this, else on PATH, else `python -m agentvow` (quoted for a shell)."""
    beside = Path(sys.executable).parent / "agentvow"
    if beside.is_file() and os.access(beside, os.X_OK):
        return shlex.quote(str(beside))
    found = shutil.which("agentvow")
    if found:
        return shlex.quote(found)
    return f"{shlex.quote(sys.executable)} -I -m agentvow"   # -I: the repository directory is not put on the import path (a hostile repo could ship its own `agentvow`)


def entries(prefix: str) -> dict:
    return {
        "PostToolUse": {"matcher": "Bash", "hooks": [{"type": "command", "command": f"{prefix} {' '.join(POST)}", "timeout": POST_TIMEOUT}]},
        "Stop": {"hooks": [{"type": "command", "command": f"{prefix} {' '.join(STOP)}", "timeout": STOP_TIMEOUT}]},
    }


def _tokens(cmd: str) -> list:
    try:
        return shlex.split(cmd)
    except ValueError:
        return []


def _ours(cmd: str, event: str) -> bool:
    """True only for an Agentvow command: the program is `agentvow` (any path) or `python [-I] -m agentvow`, followed by the subcommand tokens."""
    t = _tokens(cmd)
    if not t:
        return False
    if os.path.basename(t[0]) == "agentvow":
        rest = t[1:]
    elif len(t) >= 3 and os.path.basename(t[0]).startswith("python") and "-m" in t and t[t.index("-m") + 1:t.index("-m") + 2] == ["agentvow"]:
        rest = t[t.index("-m") + 2:]
    else:
        return False
    if event == "PostToolUse":
        return rest[:1] == list(POST)
    return rest[:1] == ["check"] and "--hook" in rest


def target_path(repo: Path, shared: bool, user: bool) -> Path:
    if user:
        return Path.home() / ".claude" / "settings.json"
    return Path(repo).resolve() / ".claude" / ("settings.json" if shared else "settings.local.json")


def load(path: Path):
    """-> (settings dict, error). A missing file is an empty dict; an unreadable or non-object file is an error (never overwritten)."""
    if not path.exists():
        return {}, None
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"{path} could not be read as JSON ({type(e).__name__}); not touched"
    if not isinstance(d, dict):
        return None, f"{path} is not a JSON object; not touched"
    hooks = d.get("hooks", {})
    if not isinstance(hooks, dict) or any(not isinstance(v, list) for v in hooks.values()):
        return None, f"{path} has an unexpected `hooks` shape; not touched"
    return d, None


def _owned(group, event) -> list:
    return [h for h in (group.get("hooks", []) if isinstance(group, dict) else []) if isinstance(h, dict) and _ours(str(h.get("command", "")), event)]


def merge(settings: dict, prefix: str, force: bool = False):
    """-> (new settings, changes list). Idempotent. An Agentvow hook that is already set is left alone (it may carry your own flags) unless `force`; then only that one hook
    command is replaced and every other hook, even in the same group, is kept."""
    new = json.loads(json.dumps(settings))
    hooks = new.setdefault("hooks", {})
    changes = []
    for event, entry in entries(prefix).items():
        lst = hooks.setdefault(event, [])
        have = [(g, h) for g in lst for h in _owned(g, event)]
        want = entry["hooks"][0]
        if have and not force:
            same = all(h.get("command") == want["command"] for _, h in have)
            changes.append(f"{event}: already set" + ("" if same else f" with a different command (`{have[0][1].get('command')}`); left unchanged (use --force to replace it)"))
            continue
        for g in list(lst):
            if isinstance(g, dict) and _owned(g, event):
                g["hooks"] = [h for h in g["hooks"] if not (isinstance(h, dict) and _ours(str(h.get("command", "")), event))]
                if not g["hooks"]:
                    lst.remove(g)
        lst.append(entry)
        changes.append(f"{event}: " + (f"replaced `{have[0][1].get('command')}` with" if have else "added") + f" `{want['command']}` (other {event} hooks are kept)")
    return new, changes


def unmerge(settings: dict):
    """-> (new settings, changes list): remove only our hook commands (other hooks in the same group stay); drop containers we emptied."""
    new = json.loads(json.dumps(settings))
    hooks = new.get("hooks", {})
    changes = []
    for event in ("PostToolUse", "Stop"):
        lst = hooks.get(event, [])
        removed = 0
        for g in list(lst):
            if isinstance(g, dict) and _owned(g, event):
                before = len(g["hooks"])
                g["hooks"] = [h for h in g["hooks"] if not (isinstance(h, dict) and _ours(str(h.get("command", "")), event))]
                removed += before - len(g["hooks"])
                if not g["hooks"]:
                    lst.remove(g)
        if removed:
            changes.append(f"{event}: removed {removed} Agentvow hook(s) (other hooks are kept)")
        if lst:
            hooks[event] = lst
        else:
            hooks.pop(event, None)
    if "hooks" in new and not new["hooks"]:
        del new["hooks"]
    return new, changes


def has_python_env(repo: Path) -> bool:
    return bool(os.environ.get("VIRTUAL_ENV")) or any((Path(repo) / d / "bin" / "python").exists() for d in (".venv", "venv", "env"))


def symlink_problem(path: Path, repo: Path | None = None):
    """-> a message when the settings file, its folder or a folder above it inside the repository is a symbolic link (writing through it could land outside the intended place)."""
    p = Path(path)
    stop = Path(repo).resolve() if repo else None
    for q in [p, *p.parents]:
        if q.is_symlink():
            return f"{q} is a symbolic link; refusing to write through it"
        if stop is not None and q == stop:
            break
    return None


def exclude_line_needed(repo: Path):
    """-> path of the repository's local exclude file when `.agentvow/` is not yet ignored there or in .gitignore, else None. The path comes from git itself (`rev-parse --git-path`), so
    worktrees and submodules (where .git is a file) work; a symlinked exclude file is never written."""
    import subprocess
    repo = Path(repo)
    try:
        r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-path", "info/exclude"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    ex = Path(r.stdout.strip())
    ex = ex if ex.is_absolute() else repo / ex
    if ex.is_symlink() or ex.parent.is_symlink():
        return None
    for f in (repo / ".gitignore", ex):
        try:
            if any(ln.strip().rstrip("/") in (".agentvow", "/.agentvow") for ln in f.read_text(encoding="utf-8", errors="replace").splitlines()):
                return None
        except OSError:
            pass
    return ex


def backup(path: Path):
    if not path.exists():
        return None
    b = path.with_name(path.name + f".agentvow-backup-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, b)
    return b


def write_json(path: Path, data: dict) -> None:
    """Write through a fresh, exclusively created temporary file in the same folder (never a predictable name that could be a planted link), keep the original file's permissions."""
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".agentvow-tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
