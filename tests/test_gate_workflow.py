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


def jobs():
    return yaml.safe_load(WF.read_text())["jobs"]


def steps(job="replay"):
    return {s.get("name", s.get("uses", "")): s for s in jobs()[job]["steps"]}


def online():
    try:
        socket.create_connection(("pypi.org", 443), timeout=3).close(); return True
    except OSError:
        return False


@unittest.skipIf(yaml is None, "PyYAML not installed")
class Static(unittest.TestCase):
    def test_no_job_that_runs_pull_request_code_holds_the_oidc_permission(self):
        j = jobs()
        self.assertEqual(j["replay"]["permissions"], {"contents": "read"})
        self.assertEqual(j["upload"]["permissions"], {"contents": "read", "id-token": "write"})
        self.assertEqual(j["decide"]["permissions"], {})
        # the upload job never checks out or runs pull-request code
        for st in j["upload"]["steps"]:
            self.assertNotIn("actions/checkout", st.get("uses", ""))
            self.assertNotIn("GITHUB_WORKSPACE", st.get("run", ""))
        co = next(s for k, s in steps().items() if k.startswith("actions/checkout"))
        self.assertIs(co["with"]["persist-credentials"], False)

    def test_there_is_no_way_to_install_agentvow_from_the_pull_request(self):
        d = yaml.safe_load(WF.read_text())
        self.assertNotIn("install-from-checkout", d[True]["workflow_call"]["inputs"])   # YAML reads `on` as True
        txt = WF.read_text()
        self.assertNotIn("pip install .", txt)
        self.assertIn('python -I -m pip install --quiet "agentvow==$VERSION"', txt)

    def test_every_python_runs_isolated_and_from_a_neutral_directory(self):
        import re
        txt = WF.read_text()
        for m in re.finditer(r"\bpython3? (?!-I)", txt):
            ctx = txt[max(0, m.start() - 20):m.end() + 20]
            self.assertTrue(ctx.lstrip().startswith(("python:", "#")) or "python-version" in ctx or "setup-python" in ctx, ctx)   # only the setup-python input names; every real invocation uses -I
        for name in ("Install Agentvow (from PyPI, from a directory the pull request does not control)", "Replay the tests and build the receipt (from a neutral directory, no credential in the environment)",
                     "Evaluate the policy from the base branch"):
            self.assertEqual(steps()[name]["working-directory"], "${{ runner.temp }}")

    def test_the_check_step_removes_every_credential_before_running_agentvow(self):
        run = next(s for k, s in steps().items() if k.startswith("Replay the tests"))["run"]
        for var in ("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_RUNTIME_TOKEN", "GITHUB_TOKEN"):
            self.assertIn(f"-u {var}", run)
        self.assertEqual(run.count("env -u"), 2)

    def test_policy_comes_from_the_base_branch_never_the_checkout_and_failing_to_read_it_blocks(self):
        run = steps()["Evaluate the policy from the base branch"]["run"]
        self.assertIn('show "origin/$BASE_REF:$POLICY_PATH"', run)
        self.assertNotIn("--policy .", run)
        self.assertIn("refusing to fall back to a weaker default", run)
        self.assertIn("core.hooksPath=/dev/null", run)

    def guard(self, **env):
        base = {**os.environ, "EVENT": "pull_request", "TEST_TIMEOUT": "900", "FAIL_ON": "block", "VERSION": "0.4.0", "POLICY_PATH": ".agentvow/policy.json", "SERVICE_URL": ""}
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
        for bad in ("", "1.0 --index-url http://evil", "1.0;ls", ".1", "1.", "latest"):
            self.assertEqual(self.guard(VERSION=bad).returncode, 1, repr(bad))
        for bad in ("/etc/passwd", "../x", "a b", "a;b", ""):
            self.assertEqual(self.guard(POLICY_PATH=bad).returncode, 1, repr(bad))
        for bad in ("http://evil.example", "ftp://x", "file:///etc"):
            self.assertEqual(self.guard(SERVICE_URL=bad).returncode, 1, bad)
        for ok in ("https://svc.example", "http://127.0.0.1:8000"):
            self.assertEqual(self.guard(SERVICE_URL=ok).returncode, 0, ok)

    def run_decide(self, decision, service, expected, replay="success", fail_on="block"):
        r = steps("decide")["Apply fail-on"]["run"]
        env = {**os.environ, "DECISION": decision, "SERVICE_DECISION": service, "SERVICE_EXPECTED": expected, "REPLAY_RESULT": replay, "FAIL_ON": fail_on}
        return subprocess.run(["bash", "-c", r], env=env, capture_output=True, text=True).returncode

    def test_fail_on_takes_the_stricter_and_every_missing_piece_fails_closed(self):
        self.assertEqual(self.run_decide("allow", "", "false"), 0)
        self.assertEqual(self.run_decide("allow", "block", "true"), 1)       # the service is stricter
        self.assertEqual(self.run_decide("block", "allow", "true"), 1)       # the local evaluation is stricter
        self.assertEqual(self.run_decide("needs_acknowledgement", "", "false"), 0)
        self.assertEqual(self.run_decide("needs_acknowledgement", "", "false", fail_on="needs_acknowledgement"), 1)
        self.assertEqual(self.run_decide("block", "", "false", fail_on="never"), 0)
        self.assertEqual(self.run_decide("allow", "error", "true"), 1)       # an error from the service
        self.assertEqual(self.run_decide("allow", "", "true"), 1)            # the service was expected but gave nothing (the upload job failed or was skipped)
        self.assertEqual(self.run_decide("", "allow", "true"), 1)            # the local evaluation died and the service says allow: still block
        self.assertEqual(self.run_decide("", "", "false"), 1)                # nothing at all
        self.assertEqual(self.run_decide("allow", "", "false", replay="failure"), 1)   # the replay job itself failed


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

    WF_REF = TRUSTED + "/.github/workflows/gate.yml@refs/tags/v0.4.0"

    def start_services(self, trees):
        self.app = cp.App(cp.MockAuth(SECRET), cp.Oracle(trees), trusted_workflows=(self.WF_REF,))
        self.srv = cp.serve(self.app)
        OidcMock.token = cp.make_token(SECRET, {"repository": "o/n", "job_workflow_ref": self.WF_REF, "aud": "agentvow-control-plane", "event_name": "pull_request", "run_id": 7, "run_attempt": 1, "exp": time.time() + 600})
        self.oidc = HTTPServer(("127.0.0.1", 0), OidcMock)
        threading.Thread(target=self.oidc.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.shutdown); self.addCleanup(self.oidc.shutdown)

    def run_steps(self, claim, fail_on="block", service=True, test_cmd="{py} -m unittest discover -s tests -t . -v"):
        shim = self.t / "shim"; shim.mkdir(exist_ok=True)
        (shim / "agentvow").write_text('#!/bin/sh\nexec python3 -m agentvow.cli "$@"\n'); (shim / "agentvow").chmod(0o755)
        env = {**os.environ, "PATH": f"{shim}:{os.environ['PATH']}", "PYTHONPATH": str(ROOT), "RUNNER_TEMP": str(self.rt), "GITHUB_OUTPUT": str(self.rt / "out"), "GITHUB_STEP_SUMMARY": str(self.rt / "sum"),
               "GITHUB_WORKSPACE": str(self.work), "CLAIM": claim, "BASE_SHA": self.base_sha, "TEST_TIMEOUT": "300", "TEST_COMMAND": test_cmd, "REPO_SLUG": "o/n", "BASE_REF": "main", "POLICY_PATH": ".agentvow/policy.json",
               "SERVICE_URL": f"http://127.0.0.1:{self.srv.server_address[1]}", "AUDIENCE": "agentvow-control-plane", "FAIL_ON": fail_on, "AGENTVOW_HOME": str(self.t / "home")}
        (self.rt / "out").write_text(""); (self.rt / "sum").write_text("")
        run = lambda step, extra=None: subprocess.run(["bash", "-c", step["run"]], cwd=self.rt, env={**env, **(extra or {})}, capture_output=True, text=True)   # every step runs from the neutral runner temp directory
        S, U, D = steps("replay"), steps("upload"), steps("decide"); res = {}
        res["check"] = run(S["Replay the tests and build the receipt (from a neutral directory, no credential in the environment)"], {"ACTIONS_ID_TOKEN_REQUEST_TOKEN": "runner-secret", "GITHUB_TOKEN": "gh-secret"})
        res["policy"] = run(S["Evaluate the policy from the base branch"])
        decision = self.out("decision")
        if service:
            res["upload"] = run(U["Post the receipt to the control plane"], {"ACTIONS_ID_TOKEN_REQUEST_URL": f"http://127.0.0.1:{self.oidc.server_address[1]}/token?v=1", "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "runner-secret"})
        res["apply"] = run(D["Apply fail-on"], {"DECISION": decision, "SERVICE_DECISION": self.out("service-decision"), "SERVICE_EXPECTED": "true" if service else "false", "REPLAY_RESULT": "success"})
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

    def test_a_hostile_json_py_and_pip_package_in_the_checkout_never_run(self):
        marker = self.t / "pwned"
        (self.work / "json.py").write_text(f"open({str(marker)!r}, 'w').write('x')\n")
        (self.work / "pip").mkdir(); (self.work / "pip" / "__main__.py").write_text(f"open({str(marker)!r}, 'w').write('y')\n")
        head, tree = self.commit_change("def f():\n    return 1\n\ndef g():\n    return 2\n")
        self.start_services({("o/n", head): tree})
        res = self.run_steps("I added g. All tests pass.")
        self.assertFalse(marker.exists(), "pull-request code ran in a workflow step")
        self.assertIn(self.out("service-decision"), ("allow", "needs_acknowledgement", "block"), res["upload"].stdout + res["upload"].stderr)   # the planted files may spoil the replay (inside the sandbox); they must not run in the workflow

    def test_a_receipt_for_a_state_the_service_cannot_match_is_not_allowed(self):
        head, tree = self.commit_change("def f():\n    return 1\n\ndef g():\n    return 2\n")
        self.start_services({("o/n", head): "0" * 40})   # GitHub's tree differs from the receipt's
        res = self.run_steps("I added g. All tests pass.")
        self.assertEqual(self.out("service-decision"), "error")
        self.assertEqual(res["apply"].returncode, 1)

    def test_an_unreadable_base_branch_blocks_instead_of_applying_a_weaker_default(self):
        head, tree = self.commit_change("def f():\n    return 1\n\ndef g():\n    return 2\n")
        self.start_services({("o/n", head): tree})
        self.g("remote", "set-url", "origin", str(self.t / "does-not-exist.git"))
        self.g("update-ref", "-d", "refs/remotes/origin/main")
        res = self.run_steps("I added g. All tests pass.", service=False)
        self.assertEqual(self.out("decision"), "block", res["policy"].stdout + res["policy"].stderr)
        self.assertIn("weaker default", res["policy"].stdout)
        self.assertEqual(res["apply"].returncode, 1)


if __name__ == "__main__":
    unittest.main()
