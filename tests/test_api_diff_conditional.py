import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import api_diff  # noqa: E402


class ConditionalDefinitions(unittest.TestCase):
    def test_a_name_moved_into_a_version_branch_is_not_reported_removed(self):
        old = "from typing import TypeAlias\nExecutorTypes: TypeAlias = int\n"
        new = "import sys\nfrom typing import TypeAlias\nif sys.version_info >= (3, 14):\n    ExecutorTypes: TypeAlias = float\nelse:\n    ExecutorTypes: TypeAlias = int\n"
        self.assertEqual(api_diff.breaking(api_diff.public_api(old), api_diff.public_api(new)), [])

    def test_a_name_defined_under_try_except_or_with_is_public(self):
        src = "try:\n    def f(a): pass\nexcept ImportError:\n    pass\nwith open('x') as h:\n    def g(): pass\n"
        self.assertEqual(set(api_diff.public_api(src)), {"f", "g"})

    def test_a_removed_name_is_still_reported(self):
        old = "def f(): pass\nif True:\n    def g(): pass\n"
        new = "def f(): pass\n"
        self.assertEqual(api_diff.breaking(api_diff.public_api(old), api_diff.public_api(new)), ["removed: g"])

    def test_function_and_class_bodies_are_not_entered(self):
        src = "def f():\n    if True:\n        def inner(): pass\nclass C:\n    if True:\n        x: int = 1\n"
        self.assertEqual(set(api_diff.public_api(src)), {"f", "C"})


if __name__ == "__main__":
    unittest.main()


class FutureImport(unittest.TestCase):
    def test_a_future_import_in_a_package_init_is_not_a_public_name(self):   # found by the griffe bake-off: removing it was reported as a removed name
        old = "from __future__ import annotations\nfrom .core import run\n"
        new = "from .core import run\n"
        self.assertEqual(api_diff.breaking(api_diff.public_api(old, True), api_diff.public_api(new, True)), [])
        self.assertIn("run", api_diff.public_api(old, True))


class WildcardAndGriffe(unittest.TestCase):
    def _repo(self, old, new, name="pkg/__init__.py"):
        import subprocess
        import tempfile
        d = Path(tempfile.mkdtemp())
        g = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True)
        g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
        (d / name).parent.mkdir(parents=True, exist_ok=True); (d / name).write_text(old)
        g("add", "-A"); g("commit", "-qm", "base")
        (d / name).write_text(new)
        return d, name

    def test_a_changed_wildcard_reexport_is_a_gap_not_silence(self):   # found by the griffe bake-off: the built-in check ignored `import *` silently
        d, name = self._repo("from .a import *\nfrom .b import *\n", "from .a import *\n")
        found, gaps = api_diff.diff(d, "HEAD", [name])
        self.assertTrue(any("wildcard" in g for g in gaps))

    def test_an_unchanged_wildcard_is_not_a_gap(self):
        d, name = self._repo("from .a import *\n", "from .a import *\nx = 1\n")
        self.assertEqual(api_diff.diff(d, "HEAD", [name]), ([], []))

    @unittest.skipUnless("griffe" in api_diff.engine_info(), "griffe not installed")
    def test_griffe_adds_a_removed_dataclass_field_the_builtin_check_misses(self):   # bake-off: halmos, GameSentenceMiner
        old = "from dataclasses import dataclass\n@dataclass\nclass V:\n    a: int = 1\n    backup: str = 'x'\n"
        new = "from dataclasses import dataclass\n@dataclass\nclass V:\n    a: int = 1\n"
        d, name = self._repo(old, new, "m.py")
        found, gaps = api_diff.diff(d, "HEAD", [name])
        self.assertTrue(any(x.startswith("m.py: griffe") and "backup" in x for x in found), found)

    def test_without_griffe_the_builtin_result_stands(self):
        from unittest import mock
        d, name = self._repo("def f(a): pass\n", "def f(a, b): pass\n", "m.py")
        with mock.patch.dict(sys.modules, {"griffe": None}):
            found, _ = api_diff.diff(d, "HEAD", [name])
        self.assertEqual(found, ["m.py: f: new required parameter(s): b"])
