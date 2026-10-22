"""GitHub as the oracle and the actuator: what GitHub says about a commit, a pull request and a repository file, and the check run the service sets. The service authenticates as a GitHub App
(an app JWT signed with the App's private key, exchanged for a short-lived installation token). All HTTP goes through one injectable function so tests never touch the network."""
import base64
import json
import re
import time
import urllib.error
import urllib.request

from urllib.parse import quote

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

API = "https://api.github.com"
REPO_RE = re.compile(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}")
SHA_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


class GitHubError(Exception):
    def __init__(self, msg, status=0):
        super().__init__(msg)
        self.status = status


def _b64(x: bytes) -> str:
    return base64.urlsafe_b64encode(x).rstrip(b"=").decode()


def http(method: str, url: str, headers: dict, body: bytes | None = None) -> tuple:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:   # noqa: S310 (https GitHub API)
            return r.status, r.read(2_000_000)
    except urllib.error.HTTPError as e:
        return e.code, e.read(200_000)
    except (urllib.error.URLError, TimeoutError) as e:
        raise GitHubError(f"network error: {type(e).__name__}")


class GitHub:
    def __init__(self, app_id: str, private_key_pem: bytes, transport=http, api: str = API, now=time.time):
        self.app_id, self.api, self.t, self.now = str(app_id), api, transport, now
        self.key = serialization.load_pem_private_key(private_key_pem, password=None)
        self._tokens: dict = {}

    def _app_jwt(self) -> str:
        h = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        n = int(self.now())
        p = _b64(json.dumps({"iat": n - 30, "exp": n + 540, "iss": self.app_id}).encode())
        return f"{h}.{p}.{_b64(self.key.sign(f'{h}.{p}'.encode(), padding.PKCS1v15(), hashes.SHA256()))}"

    def _call(self, method, path, token, body=None, auth="token"):
        hdr = {"Accept": "application/vnd.github+json", "Authorization": f"{'Bearer' if auth == 'bearer' else 'token'} {token}", "User-Agent": "agentvow-control-plane", "X-GitHub-Api-Version": "2022-11-28"}
        data = json.dumps(body).encode() if body is not None else None
        status, raw = self.t(method, self.api + path, hdr, data)
        try:
            obj = json.loads(raw) if raw else {}
        except ValueError:
            obj = {}
        return status, obj

    def _install_token(self, repo: str) -> str:
        cached = self._tokens.get(repo)
        if cached and cached[1] > self.now() + 60:
            return cached[0]
        st, inst = self._call("GET", f"/repos/{repo}/installation", self._app_jwt(), auth="bearer")
        if st != 200 or "id" not in inst:
            raise GitHubError("the App is not installed on this repository", st)
        st, tok = self._call("POST", f"/app/installations/{inst['id']}/access_tokens", self._app_jwt(), {}, auth="bearer")
        if st != 201 or "token" not in tok:
            raise GitHubError("could not get an installation token", st)
        self._tokens[repo] = (tok["token"], self.now() + 3000)
        return tok["token"]

    def _repo_call(self, method, repo, path, body=None):
        if not REPO_RE.fullmatch(str(repo)) or ".." in repo:
            raise GitHubError("not a valid repository name")
        return self._call(method, f"/repos/{repo}{path}", self._install_token(repo), body)

    # ---- what GitHub says
    def commit_tree(self, repo: str, sha: str):
        if not SHA_RE.fullmatch(str(sha)):
            return None
        st, o = self._repo_call("GET", repo, f"/git/commits/{sha}")
        return o.get("tree", {}).get("sha") if st == 200 else None

    def repo_info(self, repo: str) -> dict:
        st, o = self._repo_call("GET", repo, "")
        if st != 200:
            raise GitHubError("repository not readable", st)
        return {"private": bool(o.get("private")), "default_branch": str(o.get("default_branch") or "main")}

    def pr_info(self, repo: str, number: int):
        st, o = self._repo_call("GET", repo, f"/pulls/{int(number)}")
        if st != 200:
            return None
        return {"head_sha": o.get("head", {}).get("sha"), "base_ref": o.get("base", {}).get("ref"), "state": o.get("state"), "user": str((o.get("user") or {}).get("login") or "")}

    def branch_sha(self, repo: str, branch: str) -> str:
        """The commit a branch points to right now. A missing branch is an ERROR, never 'no policy' (a 404 on the policy file must mean only that the file does not exist)."""
        st, o = self._repo_call("GET", repo, f"/git/ref/heads/{quote(branch, safe='')}")
        sha = (o.get("object") or {}).get("sha") if st == 200 and isinstance(o, dict) else None
        if not sha or not SHA_RE.fullmatch(str(sha)):
            raise GitHubError("the branch could not be resolved", st)
        return sha

    def file_at(self, repo: str, path: str, ref: str):
        """The text of `path` at `ref` ("" is not a file), or None when it does not exist. Raises GitHubError on any other failure so a caller can fail closed."""
        st, o = self._repo_call("GET", repo, f"/contents/{quote(path)}?ref={quote(ref, safe='')}")
        if st == 404:
            return None
        if st != 200 or not isinstance(o, dict) or o.get("type") != "file" or o.get("encoding") != "base64":
            raise GitHubError("file not readable", st)
        return base64.b64decode(o.get("content", "")).decode("utf-8", "replace")

    def permission(self, repo: str, login: str) -> str:
        st, o = self._repo_call("GET", repo, f"/collaborators/{quote(login)}/permission")
        return str(o.get("permission", "none")) if st == 200 else "none"

    # ---- what the service does on GitHub
    def set_check(self, repo: str, sha: str, name: str, status: str, conclusion: str | None, title: str, summary: str, check_id: int | None = None) -> int:
        body = {"name": name, "head_sha": sha, "status": status, "output": {"title": title[:200], "summary": summary[:60000]}}
        if conclusion:
            body["conclusion"] = conclusion
        if check_id:
            st, o = self._repo_call("PATCH", repo, f"/check-runs/{int(check_id)}", body)
        else:
            st, o = self._repo_call("POST", repo, "/check-runs", body)
        if st not in (200, 201) or "id" not in o:
            raise GitHubError("could not set the check run", st)
        return int(o["id"])

    def comment(self, repo: str, number: int, text: str) -> None:
        self._repo_call("POST", repo, f"/issues/{int(number)}/comments", {"body": text[:60000]})
