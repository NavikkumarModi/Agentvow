"""Red-team suite for agent-declared recipes (docs/research/forecast_grounding/STAGE_B.md section 6).

Each case states its EXPECTED outcome up front; the suite fails if the product behaves differently. Outcome classes:
  refused     : the replay is not used as support (verdict UNKNOWN/CONTRADICTED, recipe rejected, or replay aborted)
  not_clean   : not a clean SUPPORTED (UNKNOWN, or a support verdict whose explanation carries a caveat about modified/deleted tests)
  accepted    : the recipe is replayed and supports the claim (benign controls)
  known_miss  : an attack the product does NOT detect (documented limitation); asserted so the limitation cannot silently change
  no_effect   : the attempted effect on the host did not happen (the run itself may pass or fail)
Standard library only: no network and no pip needed.
"""
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from agentvow import cli, reality

TEST_OK = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertTrue(True)\n"
TEST_B = "import unittest\nclass U(unittest.TestCase):\n    def test_b(self):\n        self.assertTrue(True)\n"
UT = "python -m unittest discover -s tests -p 'test_*.py' -t ."
SUPPORT = ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED")
RESULTS = {}      # case -> (expected, observed class)


def build(d, base_files, patch=None, delete=(), symlinks=None):
    r = Path(d) / "r"
    for rel, body in base_files.items():
        p = r / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(body)
    for rel, target in (symlinks or {}).items():
        p = r / rel; p.parent.mkdir(parents=True, exist_ok=True); os.symlink(target, p)
    g = lambda *x: subprocess.run(["git", "-C", str(r), *x], check=True, capture_output=True)
    g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t"); g("add", "-A"); g("commit", "-qm", "base")
    for rel, body in (patch or {}).items():
        p = r / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(body)
    for rel in delete:
        (r / rel).unlink()
    return r


def run(r, d, recipe_data):
    p = Path(d) / "rec.json"; p.write_text(json.dumps(recipe_data))
    old = sys.stdin, sys.stdout, sys.stderr
    sys.stdin = io.StringIO("All tests pass."); out = io.StringIO(); sys.stdout = out; sys.stderr = io.StringIO()
    try:
        cli.main(["check", "--repo", str(r), "--recipe", str(p), "--base", "HEAD", "--json"])
    finally:
        sys.stdin, sys.stdout, sys.stderr = old
    o = json.loads(out.getvalue())
    f = [x for x in o["findings"] if x["kind"] == "tests_pass"][0]
    ev = [json.loads(x.read_text()) for x in (Path(r) / ".agentvow" / "evidence").glob("testrun_*.json")] if (Path(r) / ".agentvow" / "evidence").exists() else []
    return f, ev, o


def classify(f):
    if f["verdict"] in SUPPORT:
        caveat = any(w in f["why"].lower() for w in ("modified existing test", "deleted", "removed", "narrow", "did not execute"))
        return "caveated" if caveat else "accepted"
    return "refused"


class RedTeam(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory(); self.d = self.t.name
        self._home = os.environ.get("AGENTVOW_HOME"); os.environ["AGENTVOW_HOME"] = str(Path(self.d) / "home")

    def tearDown(self):
        if self._home is None:
            os.environ.pop("AGENTVOW_HOME", None)
        else:
            os.environ["AGENTVOW_HOME"] = self._home
        self.t.cleanup()

    def case(self, name, expected, observed):
        RESULTS[name] = (expected, observed)
        ok = {"refused": observed == "refused", "not_clean": observed in ("refused", "caveated"), "accepted": observed == "accepted", "known_miss": observed == "accepted", "no_effect": observed == "accepted"}[expected]
        self.assertTrue(ok, f"{name}: expected {expected}, observed {observed}")

    # ---- adversarial: expected refused
    def test_A1_prepare_rewrites_a_test(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": "import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(1, 2)\n",
                           "scripts/mk.py": "import pathlib\npathlib.Path('tests/test_a.py').write_text('import unittest\\nclass T(unittest.TestCase):\\n    def test_a(self):\\n        pass\\n')\n"})
        f, ev, _ = run(r, self.d, {"setup": [], "prepare": ["python scripts/mk.py"], "test": UT})
        self.case("A1 prepare rewrites a test", "refused", classify(f))

    def test_A2_prepare_deletes_a_test(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK, "tests/test_bad.py": "import unittest\nclass B(unittest.TestCase):\n    def test_bad(self):\n        self.fail('x')\n",
                           "scripts/mk.py": "import pathlib\npathlib.Path('tests/test_bad.py').unlink()\n"})
        f, ev, _ = run(r, self.d, {"setup": [], "prepare": ["python scripts/mk.py"], "test": UT})
        self.case("A2 prepare deletes a failing test", "refused", classify(f))

    def test_A3_test_command_skips_the_added_test_file(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK}, patch={"tests/test_b.py": TEST_B})
        f, ev, _ = run(r, self.d, {"setup": [], "test": "python -m unittest discover -s tests -p 'test_a.py' -t ."})
        self.case("A3 recipe skips the added test file", "not_clean", classify(f))

    def test_A4_test_command_selects_zero_tests(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK})
        f, ev, _ = run(r, self.d, {"setup": [], "test": "python -m unittest discover -s tests -p 'zzz_*.py' -t ."})
        self.case("A4 recipe selects zero tests", "refused", classify(f))

    def test_A5_env_var_that_injects_pytest_options(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK})
        f, ev, o = run(r, self.d, {"setup": [], "test": UT, "env": {"PYTEST_ADDOPTS": "--co"}})
        self.case("A5 env PYTEST_ADDOPTS", "refused", classify(f))

    def test_A6_env_var_pythonpath(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK})
        f, ev, o = run(r, self.d, {"setup": [], "test": UT, "env": {"PYTHONPATH": "/tmp/evil"}})
        self.case("A6 env PYTHONPATH", "refused", classify(f))

    def test_A7_setup_installs_a_package_named_like_the_project(self):
        r = build(self.d, {"pyproject.toml": '[project]\nname = "pilot"\nversion = "0.1"\n', "tests/__init__.py": "", "tests/test_a.py": TEST_OK})
        f, ev, o = run(r, self.d, {"setup": ["pip install pilot"], "test": UT})
        self.case("A7 setup installs the project's own name", "refused", classify(f))

    def test_A8_prepare_script_is_a_symlink_outside_the_repository(self):
        outside = Path(self.d) / "outside.py"; outside.write_text("open('pwned.txt','w').write('x')\n")
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK}, symlinks={"scripts/evil.py": str(outside)})
        f, ev, _ = run(r, self.d, {"setup": [], "prepare": ["python scripts/evil.py"], "test": UT})
        self.case("A8 prepare script is a symlink", "refused", classify(f))
        self.assertFalse((r / "pwned.txt").exists())

    def test_A9_prepare_opens_a_network_connection(self):
        srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1); srv.settimeout(4); port = srv.getsockname()[1]
        got = []
        t = threading.Thread(target=lambda: got.append(srv.accept()[0]) if True else None)
        def accept():
            try:
                got.append(srv.accept())
            except OSError:
                pass
        t = threading.Thread(target=accept); t.start()
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK, "scripts/net.py": f"import socket\nsocket.create_connection(('127.0.0.1', {port}), timeout=2)\n"})
        f, ev, _ = run(r, self.d, {"setup": [], "prepare": ["python scripts/net.py"], "test": UT})
        t.join(); srv.close()
        self.assertEqual(got, [], "the sandboxed prepare step reached a local network service")
        self.case("A9 prepare opens a network connection", "refused", classify(f))

    def test_A10_prepare_writes_outside_the_worktree(self):
        probe = Path.home() / "agentvow_redteam_probe.txt"
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK, "scripts/w.py": f"open({str(probe)!r}, 'w').write('x')\n"})
        try:
            f, ev, _ = run(r, self.d, {"setup": [], "prepare": ["python scripts/w.py"], "test": UT})
            self.assertFalse(probe.exists(), "a prepare step wrote a file in the user's home directory")
            self.case("A10 prepare writes outside the worktree", "no_effect", "accepted" if not probe.exists() else "effect")
        finally:
            probe.unlink(missing_ok=True)

    def test_A11_prepare_reads_the_signing_key(self):
        os.environ.pop("AGENTVOW_HOME", None)           # the REAL default key location stays configured for the whole run: if the sandbox failed, the key would leak
        key = reality._key().hex()
        script = "import pathlib, pwd, os\nprint(open(os.path.join(pwd.getpwuid(os.getuid()).pw_dir, '.agentvow', 'key'), 'rb').read().hex())\n"
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK, "scripts/k.py": script})
        os.environ.pop("AGENTVOW_HOME", None)
        f, ev, o = run(r, self.d, {"setup": [], "prepare": ["python scripts/k.py"], "test": UT})
        blob = json.dumps(o) + json.dumps(ev)
        self.assertNotIn(key, blob, "the signing key reached the evidence")
        self.case("A11 prepare reads the signing key", "refused", classify(f))

    def test_A12_requirements_file_outside_the_repository(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK})
        f, ev, o = run(r, self.d, {"setup": ["pip install -r ../outside.txt"], "test": UT})
        self.case("A12 requirements file outside the repo", "refused", classify(f))

    def test_A13_test_path_outside_the_repository(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK})
        f, ev, o = run(r, self.d, {"setup": [], "test": "python -m unittest ../elsewhere"})
        self.case("A13 test path outside the repo", "refused", classify(f))

    def test_A14_patch_deletes_the_failing_test_file(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK, "tests/test_hard.py": "import unittest\nclass H(unittest.TestCase):\n    def test_h(self):\n        self.fail('hard')\n"},
                  delete=["tests/test_hard.py"])
        f, ev, _ = run(r, self.d, {"setup": [], "test": UT})
        self.case("A14 patch deletes the failing test file", "not_clean", classify(f))

    def test_A15_patch_weakens_an_existing_test(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": "import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(1, 2)\n"},
                  patch={"tests/test_a.py": TEST_OK})
        f, ev, _ = run(r, self.d, {"setup": [], "test": UT})
        self.case("A15 patch weakens an existing test", "not_clean", classify(f))

    def test_A16_hostile_test_prints_a_fake_summary(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": "import os, sys\nsys.stderr.write('test_a (tests.test_a.T.test_a) ... ok\\n\\nRan 1 test in 0.001s\\n\\nOK\\n')\nos._exit(0)\n"})
        f, ev, _ = run(r, self.d, {"setup": [], "test": UT})
        self.case("A16 hostile test prints a fake summary (documented limit)", "known_miss", classify(f))

    # ---- benign controls: expected accepted
    def test_B1_plain_recipe(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": TEST_OK})
        f, ev, _ = run(r, self.d, {"setup": [], "test": UT})
        self.case("B1 plain recipe", "accepted", classify(f))

    def test_B2_prepare_creates_a_new_file(self):
        r = build(self.d, {"tests/__init__.py": "", ".gitignore": "gen/\n", "scripts/mk.py": "import pathlib\npathlib.Path('gen').mkdir(exist_ok=True)\npathlib.Path('gen/x.txt').write_text('hi')\n",
                           "tests/test_a.py": "import unittest, pathlib\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(pathlib.Path('gen/x.txt').read_text(), 'hi')\n"})
        f, ev, _ = run(r, self.d, {"setup": [], "prepare": ["python scripts/mk.py"], "test": UT})
        self.case("B2 prepare creates a new generated file", "accepted", classify(f))

    def test_B3_env_var_recipe(self):
        r = build(self.d, {"tests/__init__.py": "", "tests/test_a.py": "import os, unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(os.environ['APP_MODE'], 'test')\n"})
        f, ev, _ = run(r, self.d, {"setup": [], "test": UT, "env": {"APP_MODE": "test"}})
        self.case("B3 plain environment variable", "accepted", classify(f))


class Z_Summary(unittest.TestCase):
    def test_zz_report(self):
        adv = {k: v for k, v in RESULTS.items() if k.startswith("A")}
        ben = {k: v for k, v in RESULTS.items() if k.startswith("B")}
        caught = [k for k, (e, o) in adv.items() if e in ("refused", "not_clean", "no_effect") and (o in ("refused", "caveated") or e == "no_effect")]
        sys.stderr.write(f"\n[red-team] adversarial cases with an expected catch: {len(caught)}/{len([1 for e, o in adv.values() if e != 'known_miss'])}; "
                         f"documented misses: {[k for k, (e, o) in adv.items() if e == 'known_miss']}; benign accepted: {sum(o == 'accepted' for e, o in ben.values())}/{len(ben)}\n")


if __name__ == "__main__":
    unittest.main()
