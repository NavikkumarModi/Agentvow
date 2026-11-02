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


@NEEDS
class NamedReachability(unittest.TestCase):
    PKG = json.dumps({"name": "lib", "main": "dist/index.js"})

    def test_only_the_names_the_entry_reexports_are_public(self):   # file-level reachability over-flagged internals of a partly exported module
        files = {"package.json": self.PKG, "src/index.ts": "export { pub } from './a';\n", "src/a.ts": "export function pub() {}\nexport function internal() {}\n"}
        d = make(files, {"src/a.ts": "export function pub() {}\n"})
        found, _, skipped = ts_api.check(d, "HEAD", ["src/a.ts"])
        self.assertEqual(found, [])
        self.assertTrue(any("do not re-export" in x or "does not re-export" in x for x in skipped), skipped)

    def test_removing_a_name_the_entry_does_reexport_is_found(self):
        files = {"package.json": self.PKG, "src/index.ts": "export { pub } from './a';\n", "src/a.ts": "export function pub() {}\nexport function internal() {}\n"}
        d = make(files, {"src/a.ts": "export function internal() {}\n"})
        found, _, _ = ts_api.check(d, "HEAD", ["src/a.ts"])
        self.assertEqual(found, ["src/a.ts: removed: pub"])

    def test_star_reexport_through_a_named_one_passes_the_names_on(self):
        files = {"package.json": self.PKG, "src/index.ts": "export { pub } from './mid';\n", "src/mid.ts": "export * from './leaf';\n", "src/leaf.ts": "export const pub = 1;\nexport const hidden = 2;\n"}
        d = make(files, {"src/leaf.ts": "export const hidden = 2;\n"})
        found, _, _ = ts_api.check(d, "HEAD", ["src/leaf.ts"])
        self.assertEqual(found, ["src/leaf.ts: removed: pub"])

    def test_a_name_imported_then_exported_counts(self):
        files = {"package.json": self.PKG, "src/index.ts": "import { f } from './a';\nexport { f };\n", "src/a.ts": "export function f() {}\n"}
        d = make(files, {"src/a.ts": "export function g() {}\n"})
        found, _, _ = ts_api.check(d, "HEAD", ["src/a.ts"])
        self.assertEqual(found, ["src/a.ts: removed: f"])

    def test_every_exports_subpath_is_an_entry(self):   # only the root entry used to count
        pkg = json.dumps({"name": "lib", "exports": {".": "./dist/index.js", "./extra": {"types": "./dist/extra.d.ts", "default": "./dist/extra.js"}, "./package.json": "./package.json"}})
        files = {"package.json": pkg, "src/index.ts": "export const a = 1;\n", "src/extra.ts": "export const b = 1;\n"}
        d = make(files, {"src/extra.ts": "export const c = 1;\n"})
        found, _, _ = ts_api.check(d, "HEAD", ["src/extra.ts"])
        self.assertEqual(found, ["src/extra.ts: removed: b"])

    def test_a_wildcard_reexport_is_a_gap_only_when_it_changed(self):
        files = {"package.json": self.PKG, "src/index.ts": "export * from './a';\nexport const x = 1;\n", "src/a.ts": "export const k = 1;\n"}
        d = make(files, {"src/index.ts": "export * from './a';\nexport const x = 2;\n"})
        found, gaps, _ = ts_api.check(d, "HEAD", ["src/index.ts"])
        self.assertEqual((found, gaps), ([], []))
        d2 = make(files, {"src/index.ts": "export const x = 1;\n"})
        _, gaps2, _ = ts_api.check(d2, "HEAD", ["src/index.ts"])
        self.assertTrue(any("wildcard" in g for g in gaps2), gaps2)


@NEEDS
class JavaScriptFiles(unittest.TestCase):
    def test_a_removed_export_of_a_plain_javascript_library_is_found(self):   # 40 of the 360 non-Python backward-compatibility claims are JavaScript-only changes
        files = {"package.json": json.dumps({"name": "lib", "main": "lib/index.js"}), "lib/index.js": "export { run } from './run.js';\n", "lib/run.js": "export function run(a, b) {}\nexport function helper() {}\n"}
        d = make(files, {"lib/run.js": "export function helper() {}\n"})
        found, _, _ = ts_api.check(d, "HEAD", ["lib/run.js"])
        self.assertEqual(found, ["lib/run.js: removed: run"])

    def test_a_new_required_parameter_in_javascript_is_found(self):
        files = {"package.json": json.dumps({"name": "lib", "main": "index.js"}), "index.js": "export function f(a) {}\n"}
        d = make(files, {"index.js": "export function f(a, b) {}\n"})
        found, _, _ = ts_api.check(d, "HEAD", ["index.js"])
        self.assertEqual(found, ["index.js: f: new required parameter(s): b"])

    def test_commonjs_exports_are_a_gap_not_a_pass(self):
        files = {"package.json": json.dumps({"name": "lib", "main": "index.js"}), "index.js": "module.exports = { f() {} };\n"}
        d = make(files, {"index.js": "module.exports = { g() {} };\n"})
        found, gaps, _ = ts_api.check(d, "HEAD", ["index.js"])
        self.assertEqual(found, [])
        self.assertTrue(any("CommonJS" in g for g in gaps), gaps)

    def test_a_main_that_points_at_a_build_folder_maps_to_the_source_when_it_exists(self):
        files = {"package.json": json.dumps({"name": "lib", "main": "dist/index.js"}), "src/index.js": "export const a = 1;\nexport const b = 2;\n"}
        d = make(files, {"src/index.js": "export const a = 1;\n"})
        found, _, _ = ts_api.check(d, "HEAD", ["src/index.js"])
        self.assertEqual(found, ["src/index.js: removed: b"])


class WithoutEngine(unittest.TestCase):
    def test_typescript_files_are_candidates_but_tests_and_declarations_are_not(self):
        self.assertTrue(all(ts_api.is_candidate(f) for f in ("src/a.ts", "ui/b.tsx", "lib/c.js", "lib/d.mjs", "src/e.jsx")))
        self.assertFalse(any(ts_api.is_candidate(f) for f in ("src/a.test.ts", "tests/x.ts", "types/x.d.ts", "dist/a.js", "build/b.js", "app.min.js", "webpack.config.js", ".eslintrc.js", "node_modules/x/i.js", "src/a.py")))


if __name__ == "__main__":
    unittest.main()
