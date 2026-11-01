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
