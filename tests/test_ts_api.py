import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import ts_api  # noqa: E402

NEEDS = unittest.skipUnless(ts_api.available(), "Node with the typescript package not available (set AGENTVOW_TYPESCRIPT to a node_modules directory)")


def make(files_old, files_new):
    d = Path(tempfile.mkdtemp())
    g = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True)
    g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
    for p, c in files_old.items():
        (d / p).parent.mkdir(parents=True, exist_ok=True); (d / p).write_text(c)
    g("add", "-A"); g("commit", "-qm", "base")
    for p, c in files_new.items():
        if c is None:
            (d / p).unlink()
        else:
            (d / p).parent.mkdir(parents=True, exist_ok=True); (d / p).write_text(c)
    return d


LIB = {"package.json": json.dumps({"name": "lib", "main": "dist/index.js"}), "src/index.ts": "export * from './a';\n", "src/a.ts": "export function f(x: number, y?: string): void {}\nexport const k = 1;\n", "src/internal.ts": "export function g() {}\n"}


@NEEDS
class TypeScriptPublicApi(unittest.TestCase):
    def test_a_removed_export_of_a_public_module_is_found(self):
        d = make(LIB, {"src/a.ts": "export function f(x: number, y?: string): void {}\n"})
        found, gaps, skipped = ts_api.check(d, "HEAD", ["src/a.ts"])
        self.assertEqual(found, ["src/a.ts: removed: k"])

    def test_a_new_required_parameter_is_found(self):
        d = make(LIB, {"src/a.ts": "export function f(x: number, y: string): void {}\nexport const k = 1;\n"})
        found, _, _ = ts_api.check(d, "HEAD", ["src/a.ts"])
        self.assertEqual(found, ["src/a.ts: f: parameter y made required"])

    def test_a_module_not_reexported_from_the_entry_is_not_public_api(self):
        d = make(LIB, {"src/internal.ts": "export function h() {}\n"})
        found, gaps, skipped = ts_api.check(d, "HEAD", ["src/internal.ts"])
        self.assertEqual((found, gaps), ([], []))
        self.assertTrue(skipped and "not re-exported" in skipped[0])

    def test_a_private_package_has_no_public_api(self):
        files = {**LIB, "package.json": json.dumps({"name": "app", "private": True, "main": "dist/index.js"})}
        d = make(files, {"src/a.ts": "export const other = 1;\n"})
        found, gaps, skipped = ts_api.check(d, "HEAD", ["src/a.ts"])
        self.assertEqual((found, gaps), ([], []))
        self.assertIn("private package", skipped[0])

    def test_a_file_that_does_not_parse_is_a_gap_not_a_finding(self):   # found on mastra #6084: a half-parsed file produced 26 bogus removals
        d = make(LIB, {"src/a.ts": "export function f( {{{{ ;;; }}}\n"})
        found, gaps, _ = ts_api.check(d, "HEAD", ["src/a.ts"])
        self.assertEqual(found, [])
        self.assertTrue(any("parse errors" in g for g in gaps))

    def test_a_member_moved_to_a_base_interface_is_not_a_removal(self):   # found on dot-ai #50
        old = {**LIB, "src/a.ts": "export interface B { limit?: number }\nexport interface P { limit?: number; k: string }\n"}
        d = make(old, {"src/a.ts": "export interface B { limit?: number }\nexport interface P extends B { k: string }\n"})
        found, _, _ = ts_api.check(d, "HEAD", ["src/a.ts"])
        self.assertEqual(found, [])

    def test_the_repositorys_own_node_modules_is_never_used(self):
        d = make(LIB, {"src/a.ts": "export const k = 1;\n"})
        evil = d / "node_modules" / "typescript"
        evil.mkdir(parents=True); (evil / "index.js").write_text("require('fs').writeFileSync(require('os').tmpdir() + '/agentvow_ts_pwned', 'x');\nmodule.exports = {};\n")
        marker = Path(tempfile.gettempdir()) / "agentvow_ts_pwned"
        marker.unlink(missing_ok=True)
        ts_api.check(d, "HEAD", ["src/a.ts"])
        self.assertFalse(marker.exists())


class WithoutEngine(unittest.TestCase):
    def test_typescript_files_are_candidates_but_tests_and_declarations_are_not(self):
        self.assertTrue(ts_api.is_candidate("src/a.ts") and ts_api.is_candidate("ui/b.tsx"))
        self.assertFalse(any(ts_api.is_candidate(f) for f in ("src/a.test.ts", "tests/x.ts", "types/x.d.ts", "a.js")))


if __name__ == "__main__":
    unittest.main()
