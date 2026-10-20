import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "preconditions"))
import strong_baseline as sbl  # noqa: E402

DF = """FROM python:3.11
RUN apt-get update && pip install --no-cache-dir numpy==1.26.4 \\
    scipy && pip install pytest-xdist
RUN pip install $EXTRA
RUN pip install --upgrade pip setuptools
COPY . /app
"""
WF = """name: ci
on: [push]
jobs:
  t:
    runs-on: ubuntu-latest
    steps:
      - run: pip install pytest-asyncio httpx
      - run: pytest -q
"""


class StrongBaseline(unittest.TestCase):
    def mk(self, files):
        d = Path(tempfile.mkdtemp()); 
        for n, t in files.items():
            p = d / n; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t)
        return d

    def test_dockerfile_pip_lines(self):
        got = sbl.dockerfile_setup(DF)
        self.assertEqual(got, ["pip install --no-cache-dir numpy==1.26.4 scipy", "pip install pytest-xdist"])   # expansion and pip/setuptools-only lines skipped

    def test_other_requirements_and_exclusions(self):
        d = self.mk({"requirements.txt": "a", "requirements-extra.txt": "b", "requirements-docs.txt": "c", "requirements/ci.txt": "d", "tests/requirements.txt": "e"})
        self.assertEqual(sbl.other_requirements(d), ["requirements-extra.txt", "requirements/ci.txt"])

    def test_full_recipe_order_and_validation(self):
        d = self.mk({"pyproject.toml": "[project]\nname='x'\n[project.optional-dependencies]\ndev=['q']\n", "requirements.txt": "z", ".github/workflows/ci.yml": WF, "Dockerfile": DF, "requirements-extra.txt": "y"})
        rec, notes = sbl.derive_strong(d, ["tests/test_a.py"])
        self.assertEqual(rec["setup"][:2], ["pip install .[dev]", "pip install -r requirements.txt"])
        self.assertIn("pip install pytest-asyncio httpx", rec["setup"])
        self.assertIn("pip install --no-cache-dir numpy==1.26.4 scipy", rec["setup"])
        self.assertEqual(rec["setup"][-1], "pip install -r requirements-extra.txt")
        self.assertEqual(rec["test"], "pytest -q tests/test_a.py")

    def test_no_files_gives_only_the_test_command(self):
        rec, notes = sbl.derive_strong(self.mk({"README.md": "x"}), ["t.py"])
        self.assertEqual(rec["setup"], [])


if __name__ == "__main__":
    unittest.main()
