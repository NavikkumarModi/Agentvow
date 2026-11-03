"""Read the gate's receipts for the open pull requests of one repository from GitHub (`gh api`, read-only), so `agentvow queue` can rank them without a hand-made receipts folder.
For each open pull request: the newest workflow run on its head commit that uploaded an `agentvow-gate` artifact; only `receipt.json` is taken out of the zip (size-bounded, never extracted to disk by name).
A receipt is kept only if it is well formed AND names this repository and this head commit. A pull request with no usable receipt is listed as "no receipt", which is no information, never a clean result.
These receipts are NOT authenticated: they come from artifacts of a workflow the pull request can itself edit. The control plane is the authenticated path."""
import io
import json
import re
import subprocess
import zipfile

from . import policy as policy_mod

ARTIFACT = "agentvow-gate"
MAX_ZIP = 1_000_000
MAX_RECEIPT = 120_000
_REPO = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}")
_SHA = re.compile(r"[0-9a-f]{40}")


def _gh(args: list, run, binary: bool = False):
    p = run(["gh", "api", *args], capture_output=True, text=not binary, timeout=120)
    if p.returncode != 0:
        return None
    return p.stdout if binary else _json(p.stdout)


def _json(s):
    try:
        return json.loads(s)
    except ValueError:
        return None


def _receipt_from_zip(blob: bytes):
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            info = next((i for i in z.infolist() if i.filename == "receipt.json"), None)
            if info is None or info.file_size > MAX_RECEIPT:
                return None
            with z.open(info) as f:
                data = f.read(MAX_RECEIPT + 1)
    except (zipfile.BadZipFile, OSError, RuntimeError):
        return None
    return _json(data.decode("utf-8", "replace")) if len(data) <= MAX_RECEIPT else None


def fetch(repo: str, limit: int = 30, run=subprocess.run) -> tuple:
    """-> (receipts, missing, note). `missing` is a list of {"pr", "why"} for open pull requests without a usable receipt."""
    if not _REPO.fullmatch(repo) or ".." in repo:
        raise ValueError("repository must look like owner/name")
    prs = _gh([f"repos/{repo}/pulls?state=open&per_page={max(1, min(int(limit), 100))}"], run)
    if not isinstance(prs, list):
        raise RuntimeError("could not list pull requests (is `gh` installed and logged in, and may it read this repository?)")
    receipts, missing = [], []
    for pr in prs:
        n, sha = pr.get("number"), (pr.get("head") or {}).get("sha", "")
        if not isinstance(n, int) or not _SHA.fullmatch(sha or ""):
            continue
        r, why = _for_commit(repo, n, sha, run)
        (receipts.append(r) if r else missing.append({"pr": n, "why": why}))
    note = ("Receipts were read from workflow artifacts and are not authenticated: a pull request can edit its own workflow. "
            "A pull request listed under 'no receipt' has no information here; that is not a clean result.")
    return receipts, missing, note


def _for_commit(repo: str, n: int, sha: str, run) -> tuple:
    runs = _gh([f"repos/{repo}/actions/runs?head_sha={sha}&per_page=20"], run)
    if not isinstance(runs, dict):
        return None, "workflow runs unreadable"
    seen = False
    for wr in sorted(runs.get("workflow_runs") or [], key=lambda x: str(x.get("created_at", "")), reverse=True):
        arts = _gh([f"repos/{repo}/actions/runs/{wr.get('id')}/artifacts"], run)
        for a in (arts or {}).get("artifacts", []) if isinstance(arts, dict) else []:
            if a.get("name") != ARTIFACT:
                continue
            seen = True
            if a.get("expired") or not isinstance(a.get("size_in_bytes"), int) or a["size_in_bytes"] > MAX_ZIP:
                continue
            blob = _gh([f"repos/{repo}/actions/artifacts/{a.get('id')}/zip"], run, binary=True)
            r = _receipt_from_zip(blob) if blob else None
            if r is None or policy_mod.validate_receipt(r) is not None:
                return None, "receipt not valid"
            if r["repo"] != repo or r["commit"] != sha or (r.get("pr") not in (None, n)):
                return None, "receipt does not match this pull request's repository and head commit"
            r.setdefault("pr", n)
            r["pr"] = n
            return r, ""
    return None, "gate artifact expired or unusable" if seen else "no gate run found for the head commit"
