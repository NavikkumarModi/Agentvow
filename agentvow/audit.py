"""Hidden-state audit: what did the agent change in ITS environment, and is that declared anywhere an independent party can see it?

Reads the shell commands of an agent session (Claude Code .jsonl or Copilot CLI events.jsonl), extracts environment-changing operations
(pip/uv/poetry/conda installs, exported or inline environment variables, system package managers, remote-script pipes) and compares them with
the repository's own dependency declarations at HEAD and with the agent's recipe. Anything installed in the session but declared nowhere is
**undeclared state**: a claim that depended on it cannot be reproduced by anyone else.

Deterministic string parsing only (no model). Command text is attacker-influenced data: it is parsed, never executed.
"""
import json
import re
import shlex
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

MAX_BYTES, MAX_COMMANDS = 60_000_000, 20_000
_SECRET = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH", re.I)
_PIPS = (("pip", "install"), ("pip3", "install"), ("uv", "pip", "install"), ("uv", "add"), ("poetry", "add"), ("pipx", "install"), ("conda", "install"), ("mamba", "install"))
_SYSTEM = (("apt", "install"), ("apt-get", "install"), ("brew", "install"), ("apk", "add"), ("yum", "install"), ("dnf", "install"), ("npm", "install", "-g"), ("npm", "i", "-g"), ("gem", "install"), ("cargo", "install"))
_SPLIT = re.compile(r"\s*(?:&&|\|\||\||;|\n)\s*")
_REDIR = re.compile(r"^(\d*[<>]{1,2}&?\d*|&>>?)$")


@dataclass
class Finding:
    kind: str          # install | env_var | system_install | remote_script | requirements_file
    detail: str
    declared: str = "no"   # repo | recipe | no
    command: str = ""


@dataclass
class Audit:
    findings: list = field(default_factory=list)
    commands_seen: int = 0
    truncated: bool = False

    @property
    def undeclared(self):
        return [f for f in self.findings if f.declared == "no"]


def norm(name: str) -> str:
    name = re.split(r"[\[<>=!~; @]", name.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", name).lower()


def session_commands(path: Path) -> tuple:
    """-> (list of shell command strings, truncated?). Bounded: huge sessions are cut, never read whole into memory."""
    cmds, size, trunc = [], 0, False
    with Path(path).open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            size += len(line)
            if size > MAX_BYTES or len(cmds) >= MAX_COMMANDS:
                trunc = True
                break
            if '"command"' not in line or len(line) > 2_000_000:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, RecursionError):
                continue
            for c in _extract(obj):
                cmds.append(c)
    return cmds, trunc


def _extract(obj):
    out = []
    msg = obj.get("message") if isinstance(obj, dict) else None
    content = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(content, list):            # Claude Code
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_use" and str(b.get("name", "")).lower() in ("bash", "shell", "run_in_terminal"):
                c = (b.get("input") or {}).get("command")
                if isinstance(c, str):
                    out.append(c)
    data = obj.get("data") if isinstance(obj, dict) else None
    if isinstance(data, dict):               # Copilot CLI events.jsonl
        for t in data.get("toolRequests") or []:
            if isinstance(t, dict) and str(t.get("name", "")).lower() in ("bash", "shell", "run_in_terminal"):
                c = (t.get("arguments") or {}).get("command")
                if isinstance(c, str):
                    out.append(c)
    return out


def repo_declared(repo: Path) -> set:
    """Normalised distribution names the repository itself declares (pyproject, requirements*.txt, setup.cfg)."""
    names, repo = set(), Path(repo)
    pp = repo / "pyproject.toml"
    if pp.exists():
        try:
            t = tomllib.loads(pp.read_text())
        except Exception:
            t = {}
        proj = t.get("project", {})
        for d in proj.get("dependencies", []):
            names.add(norm(d))
        for group in proj.get("optional-dependencies", {}).values():
            names |= {norm(d) for d in group}
        for group in t.get("dependency-groups", {}).values():
            names |= {norm(d) for d in group if isinstance(d, str)}
        for k in ("dependencies", "dev-dependencies"):
            names |= {norm(k2) for k2 in t.get("tool", {}).get("poetry", {}).get(k, {}) if k2.lower() != "python"}
    for f in list(repo.glob("requirements*.txt")) + list(repo.glob("requirements/*.txt")) + list(repo.glob("*/requirements*.txt")):
        try:
            for line in f.read_text().splitlines():
                line = line.split("#", 1)[0].strip()
                if line and not line.startswith(("-", ".")):
                    names.add(norm(line))
        except OSError:
            pass
    sc = repo / "setup.cfg"
    if sc.exists():
        for m in re.finditer(r"^\s{2,}([A-Za-z0-9][A-Za-z0-9._-]*)", sc.read_text(), re.M):
            names.add(norm(m.group(1)))
    names.discard("")
    return names


def audit(commands: list, repo: Path, recipe=None, truncated: bool = False) -> Audit:
    declared_repo = repo_declared(repo)
    declared_recipe = set()
    recipe_env = set()
    if recipe is not None:
        for step in recipe.setup:
            declared_recipe |= {norm(a) for a in step if not a.startswith("-") and a not in (".",) and "/" not in a and not a.startswith(".")}
        recipe_env = set(recipe.env)
    res = Audit(commands_seen=len(commands), truncated=truncated)
    for cmd in commands:
        for part in _SPLIT.split(cmd):
            part = part.strip()
            if not part:
                continue
            try:
                toks = shlex.split(part, comments=True)
            except ValueError:
                continue
            toks = _strip_redirections(toks)
            _scan(toks, part, declared_repo, declared_recipe, recipe_env, res)
            if re.search(r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba|z)?sh\b", cmd):
                res.findings.append(Finding("remote_script", "pipes a downloaded script into a shell", "no", part[:120]))
    seen, uniq = set(), []
    for f in res.findings:
        k = (f.kind, f.detail)
        if k not in seen:
            seen.add(k); uniq.append(f)
    res.findings = uniq
    return res


def _strip_redirections(toks):
    """`2>&1`, `> log.txt`, `< in` are shell plumbing, not arguments."""
    out, skip = [], False
    for t in toks:
        if skip:
            skip = False
            continue
        if _REDIR.match(t):
            skip = not re.search(r"&\d*$", t) and not t.endswith("&")   # `>` / `2>` take a file operand; `2>&1` does not
            continue
        m = re.match(r"^\d*[<>]{1,2}(?!&)(.+)$", t)
        if m and not re.match(r"^[<>]=", t[1:]):
            continue                      # `>log.txt` glued
        out.append(t)
    return out


def _scan(toks, part, d_repo, d_recipe, recipe_env, res):
    i = 0
    while i < len(toks) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", toks[i]):   # inline VAR=val cmd
        _env(toks[i], recipe_env, res, part); i += 1
    toks = toks[i:]
    if toks[:1] == ["export"]:
        for t in toks[1:]:
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t):
                _env(t, recipe_env, res, part)
        return
    if toks[:1] == ["sudo"]:
        toks = toks[1:]
    if toks[:2] in (["python", "-m"], ["python3", "-m"]):
        toks = toks[2:]
    for pat in _PIPS:
        if tuple(toks[:len(pat)]) == pat:
            args = toks[len(pat):]
            j = 0
            while j < len(args):
                a = args[j]
                if a in ("-r", "--requirement", "-c", "--constraint"):
                    f = args[j + 1] if j + 1 < len(args) else "?"
                    res.findings.append(Finding("requirements_file", f, "repo" if (Path(f).name.startswith("requirements") or f.endswith(".txt")) else "no", part[:120])); j += 2; continue
                if a in ("-e", "--editable"):
                    j += 2; continue
                if a.startswith("-") or a in (".", "..") or a.startswith((".", "/")) or "://" in a:
                    j += 1; continue
                n = norm(a)
                if n:
                    where = "repo" if n in d_repo else "recipe" if n in d_recipe else "no"
                    res.findings.append(Finding("install", n, where, part[:120]))
                j += 1
            return
    for pat in _SYSTEM:
        if tuple(toks[:len(pat)]) == pat:
            res.findings.append(Finding("system_install", " ".join(a for a in toks[len(pat):] if not a.startswith("-"))[:80] or pat[0], "no", part[:120]))
            return


def _env(assign, recipe_env, res, part):
    name = assign.split("=", 1)[0]
    secret = bool(_SECRET.search(name))
    where = "recipe" if name in recipe_env else "no"
    res.findings.append(Finding("env_var", name + (" (looks like a secret)" if secret else ""), where, part.split("=", 1)[0][:40]))   # the VALUE is never recorded


_IMPORT_SNIPPET = (
    "import ast,json,sys,pathlib,importlib.metadata as m\n"
    "root=pathlib.Path(sys.argv[1]); local={p.name.split('.')[0] for p in root.iterdir() if not p.name.startswith('.')}\n"
    "for sub in ('src','lib'):\n"
    "    if (root/sub).is_dir(): local|={p.name.split('.')[0] for p in (root/sub).iterdir()}\n"
    "for t in list(root.rglob('tests'))+list(root.rglob('test')):\n"
    "    if t.is_dir() and '.git' not in t.parts: local|={p.name.split('.')[0] for p in t.iterdir()}\n"
    "mods=set()\n"
    "for f in root.rglob('*.py'):\n"
    "    if any(x in f.parts for x in ('.git','node_modules','.venv','venv','build','dist','.agentvow')): continue\n"
    "    try: t=ast.parse(f.read_text(encoding='utf-8'))\n"
    "    except Exception: continue\n"
    "    for n in ast.walk(t):\n"
    "        if isinstance(n,ast.Import): mods|={a.name.split('.')[0] for a in n.names}\n"
    "        elif isinstance(n,ast.ImportFrom) and n.level==0 and n.module: mods.add(n.module.split('.')[0])\n"
    "d=m.packages_distributions(); out={}\n"
    "for x in sorted(mods):\n"
    "    if x in sys.stdlib_module_names or x in local: continue\n"
    "    out[x]=sorted(set(d.get(x,[])))\n"
    "print(json.dumps(out))\n")


def ambient_imports(repo: Path, python: str, recipe=None, timeout: int = 60) -> list:
    """Third-party modules the code under `repo` imports that resolve to distributions installed in `python`'s environment but are declared
    NOWHERE (repository manifests, recipe): ambient state. Runs a fixed snippet with the given interpreter (it reads files, never executes the
    project). -> list of (module, distribution) pairs."""
    import subprocess
    p = subprocess.run([python, "-I", "-c", _IMPORT_SNIPPET, str(repo)], capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        return []
    declared = repo_declared(repo)
    if recipe is not None:
        for step in recipe.setup:
            declared |= {norm(a) for a in step if not a.startswith("-") and a != "." and "/" not in a and not a.startswith(".")}
    out = []
    for mod, dists in json.loads(p.stdout or "{}").items():
        names = [norm(x) for x in dists] or [norm(mod)]
        if not any(n in declared for n in names):
            out.append((mod, names[0]))
    return out


def env_values(commands: list) -> dict:
    """LOCAL use only (the pilot harness re-runs a test with the variables the agent exported). Values are never printed or stored in audit output."""
    out = {}
    for cmd in commands:
        for part in _SPLIT.split(cmd):
            try:
                toks = shlex.split(part.strip(), comments=True)
            except ValueError:
                continue
            i = 0
            if toks[:1] == ["export"]:
                toks = toks[1:]
            while i < len(toks) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", toks[i]):
                k, v = toks[i].split("=", 1)
                out[k] = v
                i += 1
    return out


def render(a: Audit) -> str:
    lines = [f"Hidden-state audit: {a.commands_seen} shell command(s) read" + (" (session truncated)" if a.truncated else "") + "."]
    if not a.findings:
        lines.append("No environment-changing commands found.")
    for f in a.findings:
        mark = {"repo": "declared in the repository", "recipe": "declared in the recipe", "no": "UNDECLARED"}[f.declared]
        lines.append(f"  [{mark}] {f.kind}: {f.detail}")
    n = len(a.undeclared)
    lines.append(f"{n} undeclared environment change(s): a claim that depended on them cannot be reproduced by anyone else." if n else
                 "Every environment change the session made is declared in the repository or the recipe.")
    return "\n".join(lines)
