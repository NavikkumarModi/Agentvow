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
    return f"{shlex.quote(sys.executable)} -m agentvow"


def entries(prefix: str) -> dict:
    return {
        "PostToolUse": {"matcher": "Bash", "hooks": [{"type": "command", "command": f"{prefix} {' '.join(POST)}", "timeout": POST_TIMEOUT}]},
        "Stop": {"hooks": [{"type": "command", "command": f"{prefix} {' '.join(STOP)}", "timeout": STOP_TIMEOUT}]},
    }


def _ours(cmd: str, event: str) -> bool:
    if "agentvow" not in cmd:
        return False
    tail = POST if event == "PostToolUse" else STOP_OWNED
    return all(t in cmd for t in tail)


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


def merge(settings: dict, prefix: str):
    """-> (new settings, changes list). Idempotent; replaces only our own entries."""
    new = json.loads(json.dumps(settings))
    hooks = new.setdefault("hooks", {})
    changes = []
    for event, entry in entries(prefix).items():
        lst = hooks.setdefault(event, [])
        mine = [(i, g) for i, g in enumerate(lst) if isinstance(g, dict) and any(_ours(str(h.get("command", "")), event) for h in g.get("hooks", []) if isinstance(h, dict))]
        if mine and all(g == entry for _, g in mine) and len(mine) == 1:
            changes.append(f"{event}: already set (unchanged)")
            continue
        for i, _ in reversed(mine):
            del lst[i]
        lst.append(entry)
        changes.append(f"{event}: {'updated' if mine else 'added'} `{entry['hooks'][0]['command']}`")
    return new, changes


def unmerge(settings: dict):
    """-> (new settings, changes list): remove only our entries; drop empty containers we emptied."""
    new = json.loads(json.dumps(settings))
    hooks = new.get("hooks", {})
    changes = []
    for event in ("PostToolUse", "Stop"):
        lst = hooks.get(event, [])
        keep = [g for g in lst if not (isinstance(g, dict) and any(_ours(str(h.get("command", "")), event) for h in g.get("hooks", []) if isinstance(h, dict)))]
        if len(keep) != len(lst):
            changes.append(f"{event}: removed")
        if keep:
            hooks[event] = keep
        else:
            hooks.pop(event, None)
    if "hooks" in new and not new["hooks"]:
        del new["hooks"]
    return new, changes


def has_python_env(repo: Path) -> bool:
    return bool(os.environ.get("VIRTUAL_ENV")) or any((Path(repo) / d / "bin" / "python").exists() for d in (".venv", "venv", "env"))


def exclude_line_needed(repo: Path):
    """-> path of the repository's local exclude file when `.agentvow/` is not yet ignored there or in .gitignore, else None. (.git/info/exclude is local; no tracked file is edited.)"""
    repo = Path(repo)
    g = repo / ".git"
    if not g.is_dir():
        return None
    for f in (repo / ".gitignore", g / "info" / "exclude"):
        try:
            if any(ln.strip().rstrip("/") in (".agentvow", "/.agentvow") for ln in f.read_text().splitlines()):
                return None
        except OSError:
            pass
    return g / "info" / "exclude"


def backup(path: Path):
    if not path.exists():
        return None
    b = path.with_name(path.name + f".agentvow-backup-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(path, b)
    return b


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".agentvow-tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
