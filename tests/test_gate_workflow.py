"""The reusable gate workflow (.github/workflows/gate.yml): static checks of its guards, and an end-to-end simulation that runs ITS OWN shell steps locally, in order, against the mock control plane and
a mock OIDC endpoint, in a repository with a bare `origin` (so the base-branch policy is read exactly as on a runner). The end-to-end part needs network (the replay installs the test runner)."""
import json, os, socket, subprocess, sys, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentvow import policy, runner  # noqa: E402
from controlplane import mock_server as cp  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None
WF = ROOT / ".github" / "workflows" / "gate.yml"
SECRET = b"sim-secret"
TRUSTED = "trusted-owner/gate"


def steps():
    return {s.get("name", s.get("uses", "")): s for s in yaml.safe_load(WF.read_text())["jobs"]["gate"]["steps"]}


def online():
    try:
        socket.create_connection(("pypi.org", 443), timeout=3).close(); return True
    except OSError:
        return False


@unittest.skipIf(yaml is None, "PyYAML not installed")
class Static(unittest.TestCase):
    def test_permissions_and_credentials(self):
        d = yaml.safe_load(WF.read_text())
        self.assertEqual(d["jobs"]["gate"]["permissions"], {"contents": "read", "id-token": "write"})
        co = next(s for k, s in steps().items() if k.startswith("actions/checkout"))
        self.assertIs(co["with"]["persist-credentials"], False)

    def test_the_check_step_removes_every_credential_before_running_agentvow(self):
        run = next(s for k, s in steps().items() if k.startswith("Replay the tests"))["run"]
        for var in ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_RUNTIME_TOKEN", "GITHUB_TOKEN"):
            self.assertIn(f"-u {var}", run)
        self.assertEqual(run.count("env -u"), 2)   # both agentvow invocations

    def test_policy_comes_from_the_base_branch_never_the_checkout(self):
        run = steps()["Evaluate the policy from the base branch"]["run"]
        self.assertIn('git show "origin/$BASE_REF:$POLICY_PATH"', run)
        self.assertNotIn("--policy .", run)

    def guard(self, **env):
        base = {**os.environ, "EVENT": "pull_request", "IS_FORK": "false", "TEST_TIMEOUT": "900", "FAIL_ON": "block"}
        return subprocess.run(["bash", "-c", next(iter(steps().values()))["run"]], env={**base, **env}, capture_output=True, text=True)

    def test_guard(self):
        self.assertEqual(self.guard().returncode, 0)
        for ev in ("pull_request_target", "workflow_run", "issue_comment"):
            self.assertEqual(self.guard(EVENT=ev).returncode, 1, ev)
        for bad in ("", "9 0", "1.5", "-1", "9;ls"):
            self.assertEqual(self.guard(TEST_TIMEOUT=bad).returncode, 1, repr(bad))
        self.assertEqual(self.guard(FAIL_ON="always").returncode, 1)
        for ok in ("block", "needs_acknowledgement", "never"):
            self.assertEqual(self.guard(FAIL_ON=ok).returncode, 0, ok)

    def run_apply(self, decision, service, fail_on):
        r = steps()["Apply fail-on"]["run"]
        return subprocess.run(["bash", "-c", r], env={**os.environ, "DECISION": decision, "SERVICE_DECISION": service, "FAIL_ON": fail_on}, capture_output=True, text=True).returncode

    def test_fail_on_uses_the_stricter_of_local_and_service(self):
        self.assertEqual(self.run_apply("allow", "", "block"), 0)
        self.assertEqual(self.run_apply("allow", "block", "block"), 1)    # the service is stricter
        self.assertEqual(self.run_apply("block", "allow", "block"), 1)    # the local evaluation is stricter
        self.assertEqual(self.run_apply("needs_acknowledgement", "", "block"), 0)
        self.assertEqual(self.run_apply("needs_acknowledgement", "", "needs_acknowledgement"), 1)
        self.assertEqual(self.run_apply("block", "", "never"), 0)
        self.assertEqual(self.run_apply("allow", "error", "block"), 1)    # an error from the service fails closed
        self.assertEqual(self.run_apply("", "", "block"), 1)              # nothing at all fails closed


class OidcMock(BaseHTTPRequestHandler):
    token = ""

    def do_GET(self):
        b = json.dumps({"value": OidcMock.token}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass


@unittest.skipUnless(yaml is not None and online() and not runner.sandbox_problem(), "needs PyYAML, network and a working sandbox")
class Simulation(unittest.TestCase):
    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix="gate_"))
        self.origin, self.work, self.rt = self.t / "origin.git", self.t / "work", self.t / "rt"
        self.rt.mkdir()
        g = self.g = lambda *a, cwd=None: subprocess.run(["git", "-C", str(cwd or self.work), *a], check=True, capture_output=True, text=True).stdout.strip()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], check=True)
        self.work.mkdir()
        g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t"); g("remote", "add", "origin", str(self.origin))
        (self.work / "lib.py").write_text("def f():\n    return 1\n")
        (self.work / "tests").mkdir(); (self.work / "tests" / "__init__.py").write_text("")
        (self.work / "tests" / "test_lib.py").write_text("import unittest\nfrom lib import f\nclass T(unittest.TestCase):\n    def test_f(self):\n        self.assertEqual(f(), 1)\n")
        (self.work / ".gitignore").write_text(".agentvow/\n")
        g("add", "-A"); g("commit", "-qm", "base")
        self.base_sha = g("rev-parse", "HEAD")

    def start_services(self, trees):
        self.app = cp.App(cp.MockAuth(SECRET), cp.Oracle(trees), trusted_workflows=(TRUSTED,))
        self.srv = cp.serve(self.app)
        OidcMock.token = cp.make_token(SECRET, {"repository": "o/n", "job_workflow_ref": TRUSTED + "/.github/workflows/gate.yml@refs/tags/v1", "exp": time.time() + 600})
        self.oidc = HTTPServer(("127.0.0.1", 0), OidcMock)
        threading.Thread(target=self.oidc.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.shutdown); self.addCleanup(self.oidc.shutdown)

    def run_steps(self, claim, fail_on="block", service=True, test_cmd="{py} -m unittest discover -s tests -t . -v"):
        shim = self.t / "shim"; shim.mkdir()
        (shim / "agentvow").write_text('#!/bin/sh\nexec python3 -m agentvow.cli "$@"\n'); (shim / "agentvow").chmod(0o755)
        env = {**os.environ, "PATH": f"{shim}:{os.environ['PATH']}", "PYTHONPATH": str(ROOT), "RUNNER_TEMP": str(self.rt), "GITHUB_OUTPUT": str(self.rt / "out"), "GITHUB_STEP_SUMMARY": str(self.rt / "sum"),
               "CLAIM": claim, "BASE_SHA": self.base_sha, "TEST_TIMEOUT": "300", "TEST_COMMAND": test_cmd, "REPO_SLUG": "o/n", "BASE_REF": "main", "POLICY_PATH": ".agentvow/policy.json",
               "SERVICE_URL": f"http://127.0.0.1:{self.srv.server_address[1]}", "AUDIENCE": "agentvow-control-plane", "FAIL_ON": fail_on,
               "ACTIONS_ID_TOKEN_REQUEST_URL": f"http://127.0.0.1:{self.oidc.server_address[1]}/token?v=1", "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "runner-secret", "GITHUB_TOKEN": "gh-secret", "AGENTVOW_HOME": str(self.t / "home")}
        (self.rt / "out").write_text(""); (self.rt / "sum").write_text("")
        S = steps(); res = {}
        for key, name in (("check", "Replay the tests and build the receipt (no token of any kind is passed to this step)"), ("policy", "Evaluate the policy from the base branch")):
            res[key] = subprocess.run(["bash", "-c", S[name]["run"]], cwd=self.work, env=env, capture_output=True, text=True)
        if service:
            res["upload"] = subprocess.run(["bash", "-c", S["Post the receipt to the control plane (only when service-url is set)"]["run"]], cwd=self.work, env=env, capture_output=True, text=True)
        res["apply"] = subprocess.run(["bash", "-c", S["Apply fail-on"]["run"]], cwd=self.work, env={**env, "DECISION": self.out("decision"), "SERVICE_DECISION": self.out("service-decision")}, capture_output=True, text=True)
        return res

    def out(self, key):
        for ln in (self.rt / "out").read_text().splitlines():
            if ln.startswith(key + "="):
                return ln.split("=", 1)[1]
        return ""

    def commit_change(self, body):
        (self.work / "lib.py").write_text(body)
        self.g("add", "-A"); self.g("commit", "-qm", "change")
        head = self.g("rev-parse", "HEAD")
        self.g("push", "-q", "origin", f"{self.base_sha}:refs/heads/main")   # origin's main is the BASE
        return head, self.g("rev-parse", "HEAD^{tree}")

    def test_a_clean_change_flows_through_check_receipt_policy_service_and_passes(self):
        head, tree = self.commit_change("def f():\n    return 1\n\ndef g():\n    return 2\n")
        self.start_services({("o/n", head): tree})
        res = self.run_steps("I added g. All tests pass.")
        self.assertEqual(self.out("decision"), "allow", res["policy"].stdout + res["policy"].stderr)
        self.assertEqual(self.out("service-decision"), "allow", res["upload"].stdout + res["upload"].stderr)
        self.assertEqual(res["apply"].returncode, 0)
        self.assertEqual(self.app.handle("GET", f"/v1/check?repo=o/n&commit={head}", {})[1]["conclusion"], "success")
        receipt = (self.rt / "gate" / "receipt.json").read_text()
        for leak in ("runner-secret", "gh-secret", str(self.t)):
            self.assertNotIn(leak, receipt)

    def test_the_policy_in_the_pull_request_is_ignored_the_base_branch_policy_wins(self):
        # base branch (origin/main) has a strict policy; the pull request adds a permissive one
        (self.work / ".agentvow").mkdir(exist_ok=True)
        (self.work / ".agentvow" / "policy.json").write_text(json.dumps({"schema": policy.POLICY, "unknown": "block"}))
        self.g("add", "-f", ".agentvow/policy.json"); self.g("commit", "-qm", "policy on base"); self.base_sha = self.g("rev-parse", "HEAD")
        (self.work / ".agentvow" / "policy.json").write_text(json.dumps({"schema": policy.POLICY, "unknown": "allow"}))
        head, tree = self.commit_change("def f():\n    return 1\n\ndef g():\n    return 2\n")
        self.g("push", "-q", "-f", "origin", f"{self.base_sha}:refs/heads/main")
        self.start_services({("o/n", head): tree})
        res = self.run_steps("I added g. All 9 tests pass.", service=False)   # a wrong count makes the claim UNKNOWN
        self.assertEqual(self.out("decision"), "block", res["policy"].stdout + res["policy"].stderr)
        self.assertEqual(res["apply"].returncode, 1)

    def test_a_receipt_for_a_state_the_service_cannot_match_is_not_allowed(self):
        head, tree = self.commit_change("def f():\n    return 1\n\ndef g():\n    return 2\n")
        self.start_services({("o/n", head): "0" * 40})   # GitHub's tree differs from the receipt's
        res = self.run_steps("I added g. All tests pass.")
        self.assertEqual(self.out("service-decision"), "error")
        self.assertEqual(res["apply"].returncode, 1)


if __name__ == "__main__":
    unittest.main()
