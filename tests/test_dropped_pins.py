import subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import advice, capsule, envsetup, pack, recipe  # noqa: E402

PIP_ERR = "ERROR: Could not find a version that satisfies the requirement pymsalruntime==0.20.6 (from versions: none)\nERROR: No matching distribution found for pymsalruntime==0.20.6"


def build(rec, files, pip_results):
    repo = Path(tempfile.mkdtemp()); (repo / "a.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    calls = []

    def fake_pip(venv, proj, home, args, timeout, max_venv, min_free):
        calls.append(list(args))
        if "-r" in args:
            return pip_results.pop(0) if pip_results else (0, "")
        return 0, ""
    with mock.patch.object(envsetup, "_pip", fake_pip):
        py, notes, aborted = recipe.build_env(repo, rec, Path(tempfile.mkdtemp()) / "v", Path(tempfile.mkdtemp()) / "h", extra_files=files)
    return calls, notes, aborted


class Dropped(unittest.TestCase):
    def cap_recipe(self, pkgs):
        cap = {"commit": "c", "tree": "t", "packages": pkgs, "python_version": "3.13"}
        return capsule.to_recipe(cap, ["-m", "pytest", "-q"])

    def test_pip_messages_are_parsed(self):
        self.assertEqual(recipe._unavailable_pin(PIP_ERR), "pymsalruntime")
        self.assertEqual(recipe._unavailable_pin("ERROR: No matching distribution found for Foo_Bar==1"), "Foo_Bar")
        self.assertIsNone(recipe._unavailable_pin("ERROR: some other failure"))

    def test_captured_environment_leaves_out_the_unavailable_pin_and_says_so(self):
        rec, files = self.cap_recipe(["six==1.16.0", "pymsalruntime==0.20.6", "attrs==23.1.0"])
        calls, notes, aborted = build(rec, files, [(1, PIP_ERR), (0, "")])
        self.assertTrue(rec.drop_unavailable)
        self.assertEqual(rec.dropped_pins, ["pymsalruntime==0.20.6"])
        self.assertEqual(sum("-r" in c for c in calls), 2)   # first attempt, then the retry without the pin
        self.assertTrue(any("left out because pip could not install it" in n for n in notes))
        self.assertFalse(any("failed" in n for n in notes))

    def test_a_recipe_the_agent_wrote_is_never_trimmed(self):
        rec = recipe.parse({"schema": recipe.SCHEMA, "setup": ["pip install -r reqs.txt"], "test": "pytest -q"})
        self.assertFalse(rec.drop_unavailable)
        calls, notes, aborted = build(rec, {"reqs.txt": "x==1\n"}, [(1, PIP_ERR)])
        self.assertEqual(rec.dropped_pins, [])
        self.assertTrue(any("failed" in n for n in notes))

    def test_retries_are_bounded(self):
        rec, files = self.cap_recipe([f"p{i}==1" for i in range(20)])
        errs = [(1, f"ERROR: No matching distribution found for p{i}") for i in range(20)]
        calls, notes, aborted = build(rec, files, errs)
        self.assertLessEqual(len(rec.dropped_pins), 8)
        self.assertTrue(any("failed" in n for n in notes))   # still failing after the allowed retries: reported, not hidden

    def test_advice_and_pack_name_the_left_out_pin(self):
        ctx = {"name": "captured environment", "result": "fail", "summary": "exit 4; usage", "counts": {}, "dropped_pins": ["pymsalruntime==0.20.6"]}
        n = advice.step(ctx)
        self.assertEqual(n["kind"], "uninstallable_pin")
        self.assertIn("pymsalruntime==0.20.6", n["text"])
        self.assertIn("replay on the platform the capture came from", n["text"])
        c = dict(ctx, result="pass", counts={"passed": 1, "failed": 0})
        p = {"version": 1, "manifest": None, "timing": None, "receipt": {"commit": "a", "dirty": False, "base": "b", "command": "c", "replay_python": "3", "created": "t", "valid_for": "v"},
             "contexts": [c], "reproducibility": {"code": "single", "text": "r", "next_steps": []}, "coverage": {"available": False, "reason": "n/a"}, "limits": "l"}
        self.assertIn("could not be installed on this platform and were left out: pymsalruntime==0.20.6", "\n".join(pack.render_text(p)))


if __name__ == "__main__":
    unittest.main()
