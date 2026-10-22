"""Portable capture bundle (`agentvow-capture/1`): the agent's Python package state, bound to the exact files it was made for by a CONTENT hash that anyone can recompute (no key, no signature).

Why unsigned: the local capsule is signed with a key that lives in the user's Agentvow home and must never leave it. A separate verifier (a CI runner, a service) cannot check that signature, and
sharing the key would defeat it. What a verifier needs instead is (1) that the bundle was made for THIS state: it recomputes the git tree hash of its own checkout and refuses to replay on any
difference; (2) to replay it itself, in its own sandbox: the verifier's result is the evidence, and the report says the bundle was supplied, not authenticated. What a bundle author CAN
do: choose which PyPI packages the verifier installs for this tree (any name, exact versions): installs run code in the sandbox, and a hostile test plugin could change test results. So the
verifier's result is as trustworthy as whoever made the bundle, which is why it is labelled "not authenticated" and why the default policy asks a person to acknowledge it. What it cannot do:
make a result "supported" for files it was not made for (the content hash is recomputed here)."""
import hashlib
import json
import re
from pathlib import Path

from . import reality

SCHEMA = "agentvow-capture/1"
KEYS = {"schema", "created_at", "source", "command", "python_version", "platform", "packages", "packages_sha256", "git_tree", "commit", "env_values_recorded"}
_PIN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?==[A-Za-z0-9._+!-]+")   # an exact version: no wildcard
_HEX = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
MAX_PACKAGES, MAX_BYTES = 3000, 1_000_000


def packages_sha256(pkgs: list) -> str:
    return hashlib.sha256("\n".join(pkgs).encode()).hexdigest()


def export(rec: dict) -> dict:
    """A bundle from a capsule record made by `capture` (which now records `git_tree`). Nothing is copied that could hold a secret: no environment values, no paths, no file hashes."""
    if not rec.get("git_tree"):
        raise ValueError("the capsule has no content binding (git_tree); capture again")
    pk = list(rec["packages"])
    return {"schema": SCHEMA, "created_at": rec.get("created_at", ""), "source": rec.get("source", ""), "command": str(rec.get("command", ""))[:200], "python_version": rec.get("python_version", ""),
            "platform": rec.get("platform", ""), "packages": pk, "packages_sha256": packages_sha256(pk), "git_tree": rec["git_tree"], "commit": rec.get("commit", ""), "env_values_recorded": False}


def validate(b) -> str | None:
    """None when the bundle is well formed, else why not. Strict: exact keys, plain pins only, bounded sizes."""
    if not isinstance(b, dict) or set(b) != KEYS:
        return "not a capture bundle (unexpected keys)"
    if b["schema"] != SCHEMA:
        return f"unsupported schema {b['schema']!r}"
    pk = b["packages"]
    if not isinstance(pk, list) or len(pk) > MAX_PACKAGES or not all(isinstance(x, str) and _PIN.fullmatch(x) for x in pk):
        return "packages must be a list of plain `name==version` pins"
    if b["packages_sha256"] != packages_sha256(pk):
        return "the package list does not match its recorded hash"
    if not isinstance(b["git_tree"], str) or not _HEX.fullmatch(b["git_tree"]):
        return "git_tree is not a git object hash"
    if b["commit"] and not (isinstance(b["commit"], str) and _HEX.fullmatch(b["commit"])):
        return "commit is not a git object hash"
    if not re.fullmatch(r"\d+(\.\d+){1,3}[A-Za-z0-9.+-]*", str(b["python_version"])):
        return "python_version looks wrong"
    if b["env_values_recorded"] is not False:
        return "a bundle must not record environment values"
    for k in ("created_at", "source", "command", "platform"):
        if not isinstance(b[k], str) or len(b[k]) > 300:
            return f"{k} must be a short string"
    return None


def load(path) -> tuple:
    """-> (bundle or None, reason)."""
    p = Path(path)
    try:
        if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_BYTES:
            return None, "the capture file is missing, a symbolic link, or too large"
        b = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"the capture file could not be read ({type(e).__name__})"
    why = validate(b)
    return (None, why) if why else (b, "")


def bind(repo: Path, b: dict) -> tuple:
    """-> (cap dict for replay or None, reason). Refuses unless the bundle was made for exactly the files in `repo` (content hash recomputed here)."""
    try:
        here = reality.git_tree_hash(repo)
    except reality.CollectorError as e:
        return None, f"could not compute this checkout's content hash ({str(e)[:80]})"
    if here != b["git_tree"]:
        return None, ("this capture was made for different files than the ones checked out here (its content hash is "
                      f"{b['git_tree'][:12]}, this checkout's is {here[:12]}): something changed after the capture, or it belongs to another change; nothing was replayed")
    snap = reality.snapshot(Path(repo))
    return {"schema": "bundle", "commit": snap.commit, "tree": snap.tree, "packages": list(b["packages"]), "python_version": b["python_version"], "platform": b["platform"],
            "authenticated": False, "capture_source": "bundle"}, ""
