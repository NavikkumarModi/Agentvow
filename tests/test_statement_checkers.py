import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import claims, decision, lint, runner, statements  # noqa: E402


def repo_with_change(**edits):
    """A repository with a base commit and an uncommitted working-tree change. edits: {path: content}; a None value deletes the file."""
    d = Path(tempfile.mkdtemp())
    g = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True).stdout.strip()
    g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
    for p, c in {"a/util.py": "x = 1\n", "b/util.py": "y = 1\n", "README.md": "# r\n", "docs/guide.md": "g\n", "tests/test_a.py": "def test_a(): pass\n", ".gitignore": "secret.env\n", "cfg.json": "{}\n"}.items():
        (d / p).parent.mkdir(parents=True, exist_ok=True); (d / p).write_text(c)
    g("add", "-A"); g("commit", "-qm", "base")
    for p, c in edits.items():
        f = d / p
        if c is None:
            f.unlink()
        else:
            f.parent.mkdir(parents=True, exist_ok=True); f.write_text(c)
    return d


def kinds(text):
    return [(c.kind, c.detail) for c in claims.extract(text) if c.kind in (statements.FILES_SCOPE, statements.DOCS_UPDATED, statements.LINT_CLEAN)]


def find(d, kind):
    return [f for f in d.findings if f.kind == kind]


class Extraction(unittest.TestCase):
    def test_a_verb_that_governs_a_backticked_path_is_a_file_claim(self):
        for text, want in (("Added `skip_keys` support to `x/provider.py`.", ("x/provider.py", "changed")), ("I fixed `src/a.py`.", ("src/a.py", "changed")),
                           ("Wrote `docs/new.md`.", ("docs/new.md", "changed")), ("Removed `old/dead.py`.", ("old/dead.py", "absent")),
                           ("I did not touch `tests/test_a.py`.", ("tests/test_a.py", "unchanged")), ("`conf.py` was left alone.", None),
                           ("I left `conf.py` alone.", ("conf.py", "unchanged")), ("No files under `tests/` were touched.", ("tests/", "unchanged")),
                           ("`b.py` is unchanged.", ("b.py", "unchanged"))):
            got = kinds(text)
            if want is None:
                continue
            self.assertEqual([(c["path"], c["expect"]) for k, d in got if k == statements.FILES_SCOPE for c in d["checks"]], [want], text)

    def test_a_path_that_is_only_mentioned_is_not_a_claim(self):
        for text in ("It is modeled on the existing `omni/alpha_discovery_stub.py`.", "Linking to the existing `docs/pipe_input.md` reference.", "`sshpilot/config.py` imports `is_flatpak` from `platform_utils`.",
                     "The tests in `tests/test_a.py` pass.", "Fixed it by reading `settings/prod.yaml`.", "Added `x` support that copies `src.sample` to `config.env`.",
                     "Start the server at `/restore` and see `http://localhost/index.html`.", "Used `feature/branch-name` as the branch.", "Wrote `.agentvow-recipe.json`.",
                     "Updated `Class.method` in `thing`."):
            self.assertEqual([k for k, _ in kinds(text) if k == statements.FILES_SCOPE], [], text)

    def test_a_negation_the_extractor_does_not_understand_says_nothing(self):
        self.assertEqual(kinds("I could not add `x.py` because the sandbox forbids it."), [])
        self.assertEqual(kinds("Not sure whether `x.py` should be changed."), [])

    def test_docs_and_lint_statements(self):
        self.assertEqual(kinds("I updated the README to mention the helper."), [(statements.DOCS_UPDATED, {"target": "readme"})])
        self.assertEqual(kinds("Updated the documentation."), [(statements.DOCS_UPDATED, {"target": "any"})])
        self.assertEqual(kinds("Added a changelog entry for the fix."), [(statements.DOCS_UPDATED, {"target": "changelog"})])
        self.assertEqual(kinds("Added docstrings to the helpers."), [])   # docstrings live in source files: not a documentation-file claim
        self.assertEqual([d["tool"] for k, d in kinds("`ruff check` also passes with no issues.")], ["ruff check"])
        self.assertEqual([d["tool"] for k, d in kinds("Ruff lint and format checks pass.")], ["ruff check", "ruff format"])
        self.assertEqual([d["tool"] for k, d in kinds("black and flake8 are clean.")], ["black", "flake8"])
        self.assertEqual(kinds("ruff check reported 3 errors."), [])
        self.assertEqual(kinds("I could not get ruff to run, so lint is not confirmed."), [])
        self.assertEqual(kinds("The ruff config is in pyproject.toml."), [])
        self.assertEqual(kinds("Ruff checks on the touched files pass (pre-commit couldn't run in this sandbox)."), [])   # a contraction is a negation too

    def test_a_doc_path_claim_is_not_also_a_docs_claim(self):
        got = kinds("Updated `README.md` with the new section.")
        self.assertEqual([k for k, _ in got], [statements.FILES_SCOPE])

    def test_a_negated_file_claim_is_not_also_reported_as_an_unchecked_statement(self):
        self.assertEqual([c.kind for c in claims.extract("I did not touch `tests/test_a.py`.")], [statements.FILES_SCOPE])
        self.assertEqual([c.kind for c in claims.extract("I did not touch `tests/test_a.py` and could not run the suite.")], [statements.FILES_SCOPE])
        self.assertEqual([c.kind for c in claims.extract("I could not run the suite, so nothing is confirmed.")], ["unchecked"])

    def test_the_old_kinds_are_still_extracted_beside_the_new_ones(self):
        got = [c.kind for c in claims.extract("All tests pass. I left `conf.py` alone.")]
        self.assertEqual(sorted(got), sorted([claims.TESTS_PASS, statements.FILES_SCOPE]))


class Files(unittest.TestCase):
    def verdict(self, d, text):
        r = decision.check(d, "HEAD", text)
        return find(r, statements.FILES_SCOPE)[0]

    def test_changed_and_left_alone_agree_with_git(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        f = self.verdict(d, "Fixed `a/util.py`.")
        self.assertEqual(f.verdict, "NOT_CONTRADICTED")
        f = self.verdict(d, "I did not touch `tests/test_a.py`.")
        self.assertEqual(f.verdict, "NOT_CONTRADICTED")

    def test_a_file_said_to_be_left_alone_but_changed_is_contradicted(self):
        d = repo_with_change(**{"tests/test_a.py": "def test_a(): assert 1\n"})
        f = self.verdict(d, "I did not touch `tests/test_a.py`.")
        self.assertEqual(f.verdict, "CONTRADICTED")
        self.assertIn("left alone, but it was changed", f.why)

    def test_a_file_said_to_be_changed_but_not_is_contradicted(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        self.assertEqual(self.verdict(d, "Updated `docs/guide.md`.").verdict, "CONTRADICTED")

    def test_a_new_untracked_file_counts_as_changed_and_a_directory_matches_by_prefix(self):
        d = repo_with_change(**{"pkg/new_mod.py": "z = 1\n"})
        self.assertEqual(self.verdict(d, "Added `pkg/new_mod.py`.").verdict, "NOT_CONTRADICTED")
        self.assertEqual(self.verdict(d, "Added `pkg/new_mod.py` under `pkg/`.").verdict, "NOT_CONTRADICTED")
        self.assertEqual(self.verdict(d, "No files under `pkg/` were touched.").verdict, "CONTRADICTED")

    def test_a_bare_name_that_several_files_share_is_unknown_never_contradicted(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        f = self.verdict(d, "I did not touch `util.py`.")
        self.assertEqual(f.verdict, "UNKNOWN")
        f = self.verdict(d, "Updated `util.py`.")
        self.assertEqual(f.verdict, "UNKNOWN")

    def test_a_bare_name_that_is_unique_is_resolved(self):
        d = repo_with_change(**{"a/only_here.py": "x = 2\n"})
        self.assertEqual(self.verdict(d, "Added `only_here.py`.").verdict, "NOT_CONTRADICTED")

    def test_a_file_git_ignores_is_unknown_not_contradicted(self):
        d = repo_with_change(**{"secret.env": "K=1\n"})
        self.assertEqual(self.verdict(d, "Wrote `secret.env`.").verdict, "UNKNOWN")

    def test_removed_means_absent(self):
        d = repo_with_change(**{"cfg.json": None})
        self.assertEqual(self.verdict(d, "Removed `cfg.json`.").verdict, "NOT_CONTRADICTED")
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        self.assertEqual(self.verdict(d, "Deleted `cfg.json`.").verdict, "CONTRADICTED")

    def test_each_sentence_is_judged_on_its_own(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        r = decision.check(d, "HEAD", "Updated `a/util.py`. Fixed `docs/guide.md`.")
        self.assertEqual([f.verdict for f in find(r, statements.FILES_SCOPE)], ["NOT_CONTRADICTED", "CONTRADICTED"])
        self.assertEqual(r.status, decision.REVIEW)


class Docs(unittest.TestCase):
    def verdict(self, d, text):
        return find(decision.check(d, "HEAD", text), statements.DOCS_UPDATED)[0]

    def test_a_changed_documentation_file_agrees(self):
        d = repo_with_change(**{"docs/guide.md": "g2\n"})
        self.assertEqual(self.verdict(d, "Updated the documentation.").verdict, "NOT_CONTRADICTED")

    def test_readme_means_a_readme(self):
        d = repo_with_change(**{"docs/guide.md": "g2\n"})
        self.assertEqual(self.verdict(d, "I updated the README.").verdict, "CONTRADICTED")
        d = repo_with_change(**{"README.md": "# r2\n"})
        self.assertEqual(self.verdict(d, "I updated the README.").verdict, "NOT_CONTRADICTED")

    def test_only_source_changed_is_unknown_because_docstrings_exist(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        self.assertEqual(self.verdict(d, "Updated the documentation.").verdict, "UNKNOWN")

    def test_nothing_documentation_like_changed_is_contradicted(self):
        d = repo_with_change(**{"cfg.json": "{\"a\": 1}\n"})
        self.assertEqual(self.verdict(d, "Updated the documentation.").verdict, "CONTRADICTED")


class Lint(unittest.TestCase):
    def fake(self, result):
        calls = []

        def run(repo, tool, files):
            calls.append((tool, list(files)))
            return result
        return run, calls

    def verdict(self, text, result, **edits):
        d = repo_with_change(**(edits or {"a/util.py": "x = 2\n"}))
        run, calls = self.fake(result)
        r = decision.check(d, "HEAD", text, lint_runner=run)
        return find(r, statements.LINT_CLEAN), calls

    def test_clean_findings_and_unavailable_map_to_three_different_verdicts(self):
        f, calls = self.verdict("ruff check is clean.", {"status": "clean", "version": "ruff 0.9", "files": 1, "findings": 0, "summary": ""})
        self.assertEqual(f[0].verdict, "NOT_CONTRADICTED"); self.assertIn("ruff 0.9", f[0].why); self.assertEqual(calls, [("ruff check", ["a/util.py"])])
        f, _ = self.verdict("ruff check is clean.", {"status": "findings", "version": "ruff 0.9", "files": 1, "findings": 2, "summary": "x", "lines": ["a/util.py:1:1: F401"]})
        self.assertEqual(f[0].verdict, "CONTRADICTED"); self.assertIn("2 finding", f[0].why); self.assertIn("different version", f[0].why)
        for status in ("unavailable", "error"):
            f, _ = self.verdict("ruff check is clean.", {"status": status, "version": "", "files": 0, "findings": 0, "summary": "ruff is not installed here"})
            self.assertEqual(f[0].verdict, "UNKNOWN")

    def test_an_unsupported_tool_is_unknown_and_never_run(self):
        f, calls = self.verdict("mypy passes.", {"status": "clean", "version": "", "files": 1, "findings": 0, "summary": ""})
        self.assertEqual(f[0].verdict, "UNKNOWN"); self.assertEqual(calls, [])
        f, calls = self.verdict("The linter is clean.", {"status": "clean", "version": "", "files": 1, "findings": 0, "summary": ""})
        self.assertEqual(f[0].verdict, "UNKNOWN"); self.assertEqual(calls, [])

    def test_only_the_files_the_agent_names_are_linted_when_it_names_some(self):
        f, calls = self.verdict("`ruff check a/util.py` is clean.", {"status": "clean", "version": "v", "files": 1, "findings": 0, "summary": ""}, **{"a/util.py": "x = 2\n", "b/util.py": "y = 2\n"})
        self.assertEqual(calls, [("ruff check", ["a/util.py"])])
        f, calls = self.verdict("ruff check is clean.", {"status": "clean", "version": "v", "files": 2, "findings": 0, "summary": ""}, **{"a/util.py": "x = 2\n", "b/util.py": "y = 2\n"})
        self.assertEqual(calls, [("ruff check", ["a/util.py", "b/util.py"])])

    def test_no_changed_python_file_is_unknown(self):
        d = repo_with_change(**{"cfg.json": "{\"a\": 1}\n"})
        r = decision.check(d, "HEAD", "ruff check is clean.")
        self.assertEqual(find(r, statements.LINT_CLEAN)[0].verdict, "UNKNOWN")


@unittest.skipIf(runner.sandbox_problem() or not (__import__("shutil").which("ruff")), "needs a working sandbox and ruff on PATH")
class RealRuff(unittest.TestCase):
    def test_ruff_is_run_in_the_sandbox_on_the_changed_file_and_its_verdict_follows(self):
        d = repo_with_change(**{"a/util.py": "import os\nx = 2\n"})   # F401: unused import
        r = decision.check(d, "HEAD", "`ruff check` passes with no issues.")
        f = find(r, statements.LINT_CLEAN)[0]
        self.assertEqual(f.verdict, "CONTRADICTED", f.why)
        self.assertIn("F401", " ".join(f.evidence))
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        f = find(decision.check(d, "HEAD", "`ruff check` passes with no issues."), statements.LINT_CLEAN)[0]
        self.assertEqual(f.verdict, "NOT_CONTRADICTED", f.why)

    def test_the_repository_stays_unchanged_and_option_like_file_names_are_not_passed_as_options(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n", "-bad.py": "y = 1\n"})
        before = subprocess.run(["git", "-C", str(d), "status", "--porcelain", "--ignored"], capture_output=True, text=True).stdout
        res = lint.run(d, "ruff check", ["a/util.py", "-bad.py"])
        self.assertEqual(res["files"], 1)
        self.assertEqual(before, subprocess.run(["git", "-C", str(d), "status", "--porcelain", "--ignored"], capture_output=True, text=True).stdout)

    def test_a_missing_tool_is_unavailable_not_clean(self):
        from unittest import mock
        with mock.patch("shutil.which", return_value=None):
            self.assertEqual(lint.run(repo_with_change(**{"a/util.py": "x = 2\n"}), "ruff check", ["a/util.py"])["status"], "unavailable")


class Feedback(unittest.TestCase):
    def test_the_feedback_to_the_agent_has_a_fixed_reason_for_the_new_kinds_and_no_repository_strings(self):
        from agentvow import cli
        d = repo_with_change(**{"tests/test_a.py": "x\n"})
        r = decision.check(d, "HEAD", "I did not touch `tests/test_a.py`.")
        text = cli.agent_feedback(r)
        self.assertIn("git's change list disagrees", text)


if __name__ == "__main__":
    unittest.main()
