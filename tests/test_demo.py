import json, os, tempfile, unittest
from pathlib import Path
from agentmirror import demo, reality


class Demo(unittest.TestCase):
    def test_demo_is_sealed_and_red_and_rerunnable(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ["AGENTMIRROR_HOME"] = str(Path(d) / "home")
            p = Path(d) / "demo"
            info = demo.run_demo(p)
            self.assertEqual(info["status"], "REVIEW REQUIRED")
            self.assertTrue(reality.read_sealed_result(p))
            demo.run_demo(p)   # re-running replaces the demo
            with self.assertRaises(SystemExit):
                demo.run_demo(Path(d))   # never deletes a directory that is not a demo


if __name__ == "__main__":
    unittest.main()
