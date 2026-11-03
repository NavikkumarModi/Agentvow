"""Read the gate's receipts for the open pull requests of one repository from GitHub (`gh api`, read-only), so `agentvow queue` can rank them without a hand-made receipts folder.
For each open pull request: the newest workflow run on its head commit that uploaded an `agentvow-gate` artifact; only `receipt.json` is taken out of the zip (size-bounded, never extracted to disk by name).
A receipt is kept only if it is well formed AND names this repository and this head commit. A pull request with no usable receipt is listed as "no receipt", which is no information, never a clean result.
These receipts are NOT authenticated by default: they come from artifacts of a workflow the pull request can itself edit. The control plane is the authenticated path.
Optionally (`verify`), a receipt is checked with `gh attestation verify` (GitHub's artifact attestation, reused, not reimplemented) against a pinned signer workflow AND an allowed list of signer commits: the signer path alone is not enough, because a
pull request can edit the file at that path (docs/research/RECEIPT_AUTH_DESIGN.md, section 9). A receipt that does not verify is "unverified", never a clean result."""
import io
import json
import os
import re
import subprocess
import tempfile
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


DEFAULT_SIGNER = "NavikkumarModi/Agentvow/.github/workflows/gate-attest.yml"
_SIGNER = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}/\.github/workflows/[A-Za-z0-9_.-]{1,100}\.ya?ml")


def check_verify(verify: dict) -> dict:
    """Validate the verification settings: {"signer": owner/repo/.github/workflows/x.yml, "digests": [40-hex commit shas]}. The digest list is mandatory."""
    signer = verify.get("signer") or DEFAULT_SIGNER
    digests = [d.lower() for d in verify.get("digests") or []]
    if not _SIGNER.fullmatch(signer):
        raise ValueError("signer workflow must look like owner/repo/.github/workflows/name.yml")
    if not digests or len(digests) > 20 or not all(_SHA.fullmatch(d) for d in digests):
        raise ValueError("verification needs 1 to 20 allowed signer commits (40-character shas): the signer path alone does not stop a pull request that edits the signer")
    return {"signer": signer, "digests": digests}


def verify_receipt(blob: bytes, repo: str, verify: dict, run=subprocess.run) -> tuple:
    """-> (ok, why). `gh attestation verify` checks the signature, the repository and the signer workflow; this adds the signer COMMIT check against the allowed list."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "receipt.json")
        with open(path, "wb") as f:
            f.write(blob)
        p = run(["gh", "attestation", "verify", path, "--repo", repo, "--signer-workflow", verify["signer"], "--deny-self-hosted-runners", "--format", "json"], capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        return False, "no valid attestation from the pinned signer workflow"
    res = _json(p.stdout)
    for r in res if isinstance(res, list) else []:
        cert = (((r or {}).get("verificationResult") or {}).get("signature") or {}).get("certificate") or {}
        if str(cert.get("buildSignerDigest", "")).lower() in verify["digests"] and cert.get("sourceRepositoryURI") == f"https://github.com/{repo}" and str(cert.get("subjectAlternativeName", "")).startswith(f"https://github.com/{verify['signer']}@"):
            return True, ""
    return False, "attested by the pinned signer workflow, but at a commit that is not on the allowed list"


def _receipt_from_zip(blob: bytes, raw: bool = False):
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            info = next((i for i in z.infolist() if i.filename == "receipt.json"), None)
            if info is None or info.file_size > MAX_RECEIPT:
                return None
            with z.open(info) as f:
                data = f.read(MAX_RECEIPT + 1)
    except (zipfile.BadZipFile, OSError, RuntimeError):
        return None
    if len(data) > MAX_RECEIPT:
        return None
    return (_json(data.decode("utf-8", "replace")), data) if raw else _json(data.decode("utf-8", "replace"))


def fetch(repo: str, limit: int = 30, run=subprocess.run, verify: dict | None = None, auth: dict | None = None) -> tuple:
    """-> (receipts, missing, note). `missing` is a list of {"pr", "why"} for open pull requests without a usable receipt.
    With `verify` ({"signer", "digests"}) each receipt is checked with `gh attestation verify`, and `auth` (a dict the caller passes in) is filled with {(repo, commit): (ok, why)}."""
    if not _REPO.fullmatch(repo) or ".." in repo:
        raise ValueError("repository must look like owner/name")
    if verify is not None:
        verify = check_verify(verify)
    prs = _gh([f"repos/{repo}/pulls?state=open&per_page={max(1, min(int(limit), 100))}"], run)
    if not isinstance(prs, list):
        raise RuntimeError("could not list pull requests (is `gh` installed and logged in, and may it read this repository?)")
    receipts, missing = [], []
    for pr in prs:
        n, sha = pr.get("number"), (pr.get("head") or {}).get("sha", "")
        if not isinstance(n, int) or not _SHA.fullmatch(sha or ""):
            continue
        r, why = _for_commit(repo, n, sha, run, verify, auth)
        (receipts.append(r) if r else missing.append({"pr": n, "why": why}))
    note = (("Receipts were read from workflow artifacts and checked with GitHub's artifact attestation against the pinned signer workflow and an allowed list of signer commits; a receipt that fails is shown as unverified. " if verify else
             "Receipts were read from workflow artifacts and are not authenticated: a pull request can edit its own workflow. ")
            + "A pull request listed under 'no receipt' has no information here; that is not a clean result.")
    return receipts, missing, note


def _for_commit(repo: str, n: int, sha: str, run, verify=None, auth=None) -> tuple:
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
            got = _receipt_from_zip(blob, raw=True) if blob else None
            r, raw = got if got else (None, b"")
            if r is None or policy_mod.validate_receipt(r) is not None:
                return None, "receipt not valid"
            if r["repo"] != repo or r["commit"] != sha or (r.get("pr") not in (None, n)):
                return None, "receipt does not match this pull request's repository and head commit"
            r.setdefault("pr", n)
            r["pr"] = n
            if verify is not None and auth is not None:
                auth[(r["repo"], r["commit"])] = verify_receipt(raw, repo, verify, run)
            return r, ""
    return None, "gate artifact expired or unusable" if seen else "no gate run found for the head commit"
