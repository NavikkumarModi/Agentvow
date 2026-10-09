"""Deterministic reality collectors: git snapshot, Python import graph, test reachability.

Every collector reports gaps (files it could not analyse) instead of silently skipping them.
"""
import ast
import hmac
import os
import warnings
import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".agentmirror"}
OTHER_CODE = {".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb", ".kt", ".c", ".cpp"}


class CollectorError(Exception):
    pass


def _key() -> bytes:
    """Per-user signing key kept OUTSIDE the repo (an agent editing the repo cannot forge a signature without reading this file)."""
    p = Path(os.environ.get("AGENTMIRROR_HOME", Path.home() / ".agentmirror")) / "key"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(os.urandom(32))
        p.chmod(0o600)
    return p.read_bytes()


def _canon(rec: dict) -> bytes:
    return json.dumps({k: v for k, v in rec.items() if k != "sig"}, sort_keys=True).encode()


def sign_record(rec: dict) -> dict:
    rec = dict(rec)
    rec["sig"] = hmac.new(_key(), _canon(rec), hashlib.sha256).hexdigest()
    return rec


def seal(page: bytes, decision: bytes) -> str:
    """HMAC over the exact bytes of report.html and decision.json (the key lives outside the repo)."""
    return hmac.new(_key(), page + b"\0" + decision, hashlib.sha256).hexdigest()


def read_sealed_result(last_dir: Path):
    """The hook's result (decision dict) if report.html + decision.json carry a valid seal from this tool, else None. -> (decision, stamp)."""
    try:
        page = (last_dir / "report.html").read_bytes()
        dec = (last_dir / "decision.json").read_bytes()
        sig = (last_dir / "decision.sig").read_text().strip()
        if not hmac.compare_digest(sig, seal(page, dec)):
            return None, None
        return json.loads(dec), sig
    except (OSError, ValueError):
        return None, None


def verify_record(rec: dict) -> bool:
    sig = rec.get("sig")
    return bool(sig) and hmac.compare_digest(sig, hmac.new(_key(), _canon(rec), hashlib.sha256).hexdigest())


# Untrusted repositories can configure code to run on ordinary git commands (hooks, fsmonitor). Neutralise them everywhere.
GIT_SAFE = ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-c", "protocol.ext.allow=never"]


def safe_write(root: Path, rel: Path, data) -> Path:
    """Write root/rel without ever following a symlink (an agent-controlled repo could plant one to make us overwrite any file)."""
    root = Path(root).resolve()
    rel = Path(rel)
    if rel.is_absolute() or ".." in rel.parts:
        raise OSError(f"unsafe path: {rel}")
    cur = root
    for part in rel.parts[:-1]:
        cur = cur / part
        if cur.is_symlink():
            raise OSError(f"refusing to write through a symlink: {cur}")
        cur.mkdir(exist_ok=True)
    target = cur / rel.parts[-1]
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
    return target


def _git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", *GIT_SAFE, "-C", str(repo), *args], capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise CollectorError(f"git {' '.join(args)} failed: {e}") from e
    return out.stdout.strip()


@dataclass
class Snapshot:
    commit: str
    dirty: bool
    tree: str = ""  # content hash of HEAD + every tracked/untracked (non-ignored) file; binds evidence to uncommitted work


def _tree_hash(repo: Path, commit: str) -> str:
    h = hashlib.sha256(commit.encode())
    files = _git(repo, "ls-files", "-co", "--exclude-standard", "-z", "--", ".", ":(exclude).agentmirror").split("\0")
    for f in sorted(x for x in files if x):
        p = repo / f
        h.update(f.encode() + b"\0")
        h.update(p.read_bytes() if p.is_file() else b"<missing>")
    return h.hexdigest()[:16]


def snapshot(repo: Path) -> Snapshot:
    commit = _git(repo, "rev-parse", "HEAD")
    dirty = bool(_git(repo, "status", "--porcelain", "--", ".", ":(exclude).agentmirror"))
    return Snapshot(commit, dirty, _tree_hash(repo, commit) if dirty else "")


def changed_files(repo: Path, base: str) -> list[str]:
    committed = _git(repo, "diff", "--name-only", f"{base}..HEAD").splitlines()
    working = _git(repo, "diff", "--name-only", "HEAD").splitlines()
    untracked = _git(repo, "ls-files", "-o", "--exclude-standard", "--", ".", ":(exclude).agentmirror").splitlines()
    return sorted(f for f in set(committed) | set(working) | set(untracked) if not f.startswith(".agentmirror/"))


@dataclass
class Graph:
    imports: dict[str, set[str]] = field(default_factory=dict)  # file -> files it imports
    gaps: list[str] = field(default_factory=list)  # things we could not analyse

    def reverse(self) -> dict[str, set[str]]:
        rev: dict[str, set[str]] = {f: set() for f in self.imports}
        for f, deps in self.imports.items():
            for d in deps:
                rev.setdefault(d, set()).add(f)
        return rev

    def dependents(self, target: str) -> set[str]:
        rev, seen, stack = self.reverse(), set(), [target]
        while stack:
            for d in rev.get(stack.pop(), ()):
                if d not in seen:
                    seen.add(d)
                    stack.append(d)
        return seen


def build_graph(repo: Path) -> Graph:
    g = Graph()
    files = [p for p in repo.rglob("*") if p.is_file() and not (set(p.relative_to(repo).parts) & SKIP_DIRS)]
    py = {str(p.relative_to(repo)): p for p in files if p.suffix == ".py"}
    modules = {}
    for rel in py:
        parts = rel[:-3].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules[".".join(parts)] = rel
        if parts and parts[0] in ("src", "lib") and len(parts) > 1:
            modules.setdefault(".".join(parts[1:]), rel)  # src-layout: imported as 'pkg.mod', stored as 'src/pkg/mod.py'
    for p in files:
        if p.suffix in OTHER_CODE:
            g.gaps.append(f"unsupported language, not analysed: {p.relative_to(repo)}")
    for rel, p in py.items():
        deps: set[str] = set()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # third-party code often has invalid escapes
                tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as e:
            g.gaps.append(f"could not parse {rel}: {type(e).__name__}")
            g.imports[rel] = deps
            continue
        pkg = rel.split("/")[:-1]
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = ".".join(pkg[: len(pkg) - (node.level - 1)]) if node.level else ""
                mod = ".".join(x for x in (base, node.module or "") if x)
                names = [mod] + [f"{mod}.{a.name}" if mod else a.name for a in node.names]
            elif isinstance(node, ast.Call) and (getattr(node.func, "id", "") in ("__import__", "import_module")
                                                  or getattr(node.func, "attr", "") == "import_module"):
                g.gaps.append(f"dynamic import in {rel}: dependencies may be missed")
            for n in names:
                while n:
                    if n in modules and modules[n] != rel:
                        deps.add(modules[n])
                        break
                    n = n.rpartition(".")[0]
        g.imports[rel] = deps
    return g


def is_test(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return name.startswith("test_") or name.endswith("_test.py") or "/tests/" in f"/{rel}"


@dataclass
class Evidence:
    evidence_id: str
    type: str
    collector: str
    snapshot: str
    artifact_hash: str
    freshness: str  # VALID | STALE | UNVERIFIABLE
    independence: dict
    raw_reference: str
    detail: str = ""
    suite: str = ""
    counts: dict = field(default_factory=dict)  # passed/failed/skipped/errors when a test run was recorded


def load_prior_evidence(repo: Path, snap: Snapshot) -> list[Evidence]:
    """Discover earlier verification artifacts in .agentmirror/evidence/*.json and bind them to the snapshot."""
    out = []
    d = repo / ".agentmirror" / "evidence"
    for f in sorted(d.glob("*.json")) if d.is_dir() else []:
        raw = f.read_bytes()
        h = hashlib.sha256(raw).hexdigest()[:16]
        try:
            rec = json.loads(raw)
            commit = rec["commit"]
        except (ValueError, KeyError):
            out.append(Evidence(f.stem, "prior_verification", "work-harvester", "?", h, "UNVERIFIABLE",
                                _INDEP_AGENT, str(f.relative_to(repo)), "malformed artifact"))
            continue
        same_state = (rec.get("tree") == snap.tree) if snap.dirty else not rec.get("tree")
        fresh = "VALID" if commit == snap.commit and same_state else "STALE"
        trusted = verify_record(rec) and rec.get("produced_by") != "agent"  # unsigned records can be forged by whoever can write the repo
        out.append(Evidence(f.stem, "prior_verification", "work-harvester", commit, h, fresh,
                            _INDEP_TOOL if trusted else _INDEP_AGENT,
                            str(f.relative_to(repo)), f'{rec.get("result", "?")}: {rec.get("summary", "")}', rec.get("suite", ""), rec.get("counts", {})))
    return out


_INDEP_AGENT = {"framing": "same", "evidence": "same", "mechanism": "same", "authority": "same"}
_INDEP_TOOL = {"framing": "separate", "evidence": "separate", "mechanism": "separate", "authority": "unknown"}


def default_base(repo: Path, dirty: bool):
    """Pick the commit the agent started from. -> (ref, how). Uncommitted work: HEAD. Else the merge-base with the default branch, else HEAD~1 (assumed)."""
    if dirty:
        return "HEAD", "HEAD (uncommitted work present)"
    head = _git(repo, "rev-parse", "HEAD")
    for ref in ("origin/HEAD", "origin/main", "origin/master", "main", "master"):
        try:
            mb = _git(repo, "merge-base", "HEAD", ref)
        except CollectorError:
            continue
        if mb and mb != head:
            return mb, f"merge-base with {ref}"
    return "HEAD~1", "HEAD~1 (assumed; pass --base if the agent made several commits)"


def existed_at(repo: Path, ref: str, path: str) -> bool:
    return subprocess.run(["git", *GIT_SAFE, "-C", str(repo), "cat-file", "-e", f"{ref}:{path}"], capture_output=True).returncode == 0
