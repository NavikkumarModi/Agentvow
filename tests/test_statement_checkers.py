import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os
from unittest import mock

from agentvow import claims, decision, lint, policy, runner, statements  # noqa: E402


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

    def test_the_verb_must_open_the_clause_so_a_description_of_behaviour_is_not_a_claim(self):   # found on real pull-request descriptions
        for text in ("Dockerfile's env merging logic always created `.env` from `.env.default`", "The old helper wrote `out/result.json` on every call.", "Previously the script modified `conf/app.yaml` in place."):
            self.assertEqual([k for k, _ in kinds(text) if k == statements.FILES_SCOPE], [], text)
        for text in ("- Updated `CLAUDE.md` with patterns", "- [x] **Session Fix**: Modified `a/cookie.go` to create a guest", "I've added it in `doc/api/`.", "* **Docs**: Created `site/new.md`"):
            self.assertEqual(len([k for k, _ in kinds(text) if k == statements.FILES_SCOPE]), 1, text)

    def test_something_written_into_another_file_is_not_a_changed_file(self):   # found on held-out real descriptions
        for text in ("- **.gitignore**: Added `.venv/` for uv's virtual environments", "Added `node_modules/` to `.gitignore` to keep dependencies out", "- **.gitignore**: Added `.ansible/` directory to prevent temporary files",
                     "- Added `USAGE_EXISTING_REDIS.md` documentation reference", "Added `.js` extension to all imports", "- Added references to `NOTES.md` for detail", "Added `docs/api.md` link to the index", "- **Added `repomix-output.xml`** to `.gitignore` for cleaner repository", "Added `x/y.json` entry to the manifest"):
            self.assertEqual([k for k, _ in kinds(text) if k == statements.FILES_SCOPE], [], text)
        self.assertEqual(len([k for k, _ in kinds("Added `docs/api.md` with the new endpoints.") if k == statements.FILES_SCOPE]), 1)

    def test_the_thing_added_to_a_file_is_not_a_file_but_the_file_it_went_into_is(self):
        got = kinds("- Added `sys/types.h` include to `bsd.h` for type definitions")
        self.assertEqual([(c["path"], c["expect"]) for k, d in got for c in d["checks"]], [("bsd.h", "changed")])

    def test_removing_something_from_a_file_is_not_removing_the_file(self):
        self.assertEqual(kinds("- Removed `cli/tests/test_cli.rs` temporal test case"), [])
        self.assertEqual(kinds("Removed `old/dead.py` entirely."), [(statements.FILES_SCOPE, {"checks": [{"path": "old/dead.py", "expect": "absent"}]})])
        self.assertEqual(kinds("Deleted `old/dead.py`."), [(statements.FILES_SCOPE, {"checks": [{"path": "old/dead.py", "expect": "absent"}]})])

    def test_template_checkboxes_and_conditional_wording_are_not_statements(self):   # 25 of 37 documentation contradictions on real pull requests were these
        for text in ("- [ ] Updated documentation if needed", "- [ ] I have updated the documentation", "- [x] Updated documentation if needed", "- [x] I have added documentation (if applicable)",
                     "- [ ] `ruff check` passes", "Have you updated the documentation?", "- [x] No documentation change needed (N/A)"):
            self.assertEqual(kinds(text), [], text)
        self.assertEqual(kinds("- [x] I have updated the documentation"), [(statements.DOCS_UPDATED, {"target": "any"})])

    def test_a_document_that_is_only_a_link_target_was_not_edited(self):
        self.assertEqual(kinds("Updated the Table of Contents with an entry linking to the README.md file."), [])
        self.assertEqual(len(kinds("Updated the README to describe the flag.")), 1)

    def test_documentation_inside_code_is_not_a_documentation_file_claim(self):
        for text in ("Added XML documentation to the MSBuild task methods.", "Added documentation comments explaining the upgrade.", "Created a multi-stage Dockerfile for the documentation site:",
                     "Added JSDoc to the helpers.", "Created workflow for version management with changelog generation"):
            self.assertEqual([k for k, _ in kinds(text) if k == statements.DOCS_UPDATED], [], text)

    def test_lint_claims_need_a_real_clean_statement_not_a_word_that_happens_to_appear(self):
        for text in ("- clean ruff lint issues", "Fix formatting and clean up syslog tests", "mvn -B clean license:format formatter:format test", "guard bigint JSON formatting so builds without Boost succeed",
                     "Generated SDKs compile successfully with new formatter version"):
            self.assertEqual(kinds(text), [], text)
        self.assertEqual([d["tool"] for k, d in kinds("Linting and formatting checks pass.")], ["lint"])
        self.assertEqual([d["tool"] for k, d in kinds("The linter is clean.")], ["lint"])

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


def mismatch(test, f):
    """A disagreement with git's change list is a mismatch for a person (UNKNOWN with attention), never CONTRADICTED: see decision._text_vs_changes."""
    test.assertEqual(f.verdict, "UNKNOWN", f.why)
    test.assertTrue(f.attention)
    test.assertTrue(f.meta.get("mismatch"))


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
        mismatch(self, f)
        self.assertIn("left alone, but it was changed", f.why)

    def test_a_file_said_to_be_changed_but_not_is_contradicted(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        mismatch(self, self.verdict(d, "Updated `docs/guide.md`."))

    def test_a_new_untracked_file_counts_as_changed_and_a_directory_matches_by_prefix(self):
        d = repo_with_change(**{"pkg/new_mod.py": "z = 1\n"})
        self.assertEqual(self.verdict(d, "Added `pkg/new_mod.py`.").verdict, "NOT_CONTRADICTED")
        self.assertEqual(self.verdict(d, "Added `pkg/new_mod.py` under `pkg/`.").verdict, "NOT_CONTRADICTED")
        mismatch(self, self.verdict(d, "No files under `pkg/` were touched."))

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

    def test_a_removed_bare_name_that_exists_elsewhere_is_unknown(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        self.assertEqual(self.verdict(d, "Removed `README.md` from the old directory.").verdict, "UNKNOWN")

    def test_removed_means_absent(self):
        d = repo_with_change(**{"cfg.json": None})
        self.assertEqual(self.verdict(d, "Removed `cfg.json`.").verdict, "NOT_CONTRADICTED")
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        mismatch(self, self.verdict(d, "Deleted `a/util.py`."))

    def test_each_sentence_is_judged_on_its_own(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        r = decision.check(d, "HEAD", "Updated `a/util.py`. Fixed `docs/guide.md`.")
        self.assertEqual([f.verdict for f in find(r, statements.FILES_SCOPE)], ["NOT_CONTRADICTED", "UNKNOWN"])
        mismatch(self, find(r, statements.FILES_SCOPE)[1])
        self.assertEqual(r.status, decision.REVIEW)   # attention makes the overall status REVIEW REQUIRED


class DirectoriesAndDocs(unittest.TestCase):
    def test_a_directory_the_agent_names_without_its_parent_still_matches(self):
        d = repo_with_change(**{"docusaurus/versioned/v2/a.md": "x\n"})
        f = find(decision.check(d, "HEAD", "Created `versioned/v2/` with a snapshot."), statements.FILES_SCOPE)[0]
        self.assertEqual(f.verdict, "NOT_CONTRADICTED", f.why)

    def test_a_changelog_claim_is_unknown_when_no_file_is_named_like_one_and_other_language_sources_count_as_possible_docs(self):
        d = repo_with_change(**{"cfg.json": "{\"a\": 1}\n"})
        self.assertEqual(find(decision.check(d, "HEAD", "Added a changelog entry."), statements.DOCS_UPDATED)[0].verdict, "UNKNOWN")
        d = repo_with_change(**{"main.go": "package main\n"})
        self.assertEqual(find(decision.check(d, "HEAD", "Updated the documentation."), statements.DOCS_UPDATED)[0].verdict, "UNKNOWN")


class Docs(unittest.TestCase):
    def verdict(self, d, text):
        return find(decision.check(d, "HEAD", text), statements.DOCS_UPDATED)[0]

    def test_a_changed_documentation_file_agrees(self):
        d = repo_with_change(**{"docs/guide.md": "g2\n"})
        self.assertEqual(self.verdict(d, "Updated the documentation.").verdict, "NOT_CONTRADICTED")

    def test_readme_means_a_readme(self):
        d = repo_with_change(**{"docs/guide.md": "g2\n"})
        mismatch(self, self.verdict(d, "I updated the README."))
        d = repo_with_change(**{"README.md": "# r2\n"})
        self.assertEqual(self.verdict(d, "I updated the README.").verdict, "NOT_CONTRADICTED")

    def test_only_source_changed_is_unknown_because_docstrings_exist(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        self.assertEqual(self.verdict(d, "Updated the documentation.").verdict, "UNKNOWN")

    def test_nothing_documentation_like_changed_is_contradicted(self):
        d = repo_with_change(**{"cfg.json": "{\"a\": 1}\n"})
        mismatch(self, self.verdict(d, "Updated the documentation."))


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


class ReviewFindings(unittest.TestCase):
    """Each test is one finding of the adversarial review of 2026-10-27 (docs/research/CHECKERS_FILES_DOCS_LINT.md)."""

    def test_flake8_is_not_run_when_the_repository_configures_local_plugins(self):   # high: a plugin is Python from the repository; the sandbox can still read files outside it
        for name in ("setup.cfg", "tox.ini", ".flake8"):
            d = repo_with_change(**{name: "[flake8:local-plugins]\nextension =\n    X = plug:P\n", "a/util.py": "x = 2\n"})
            self.assertIn("local plugins", lint.runs_repository_code(d, "flake8"))
            res = lint.run(d, "flake8", ["a/util.py"])
            self.assertEqual(res["status"], "unavailable")
            self.assertIn("was not run", res["summary"])
        d = repo_with_change(**{"setup.cfg": "[flake8]\nmax-line-length = 100\n", "a/util.py": "x = 2\n"})
        self.assertIsNone(lint.runs_repository_code(d, "flake8"))
        self.assertIsNone(lint.runs_repository_code(repo_with_change(**{"setup.cfg": "[flake8:local-plugins]\n"}), "ruff check"))

    def test_only_parsed_path_and_code_pairs_are_reported_never_the_tools_free_text(self):   # high: a plugin or a crafted file name can put file contents or tokens in the output
        out = ["a/util.py:1:1: X001 token=FAKETOKEN123", "other/secret.py:2:2: F401 not a file we gave", "free text with FAKETOKEN123", "a/util.py:3:4 E501 line too long: SECRET",
               "a/util.py:9:9: lowercase01 nope"]
        got = lint.parse("flake8", out, {"a/util.py"})
        self.assertEqual(got, ["a/util.py X001", "a/util.py E501"])
        self.assertNotIn("FAKETOKEN123", " ".join(got)); self.assertNotIn("SECRET", " ".join(got))
        self.assertEqual(lint.parse("ruff format", ["would reformat a/util.py", "would reformat /etc/passwd", "garbage"], {"a/util.py"}), ["a/util.py would be reformatted"])

    def test_the_tool_is_found_only_in_absolute_path_entries_outside_the_repository(self):   # low: a '.' or empty entry would pick the repository's own ruff
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        inside = str(d / "bin"); (d / "bin").mkdir()
        with mock.patch.dict(os.environ, {"PATH": os.pathsep.join(["", ".", "bin", inside, "/usr/bin", "/bin"])}):
            got = lint.trusted_path(d).split(os.pathsep)
        self.assertEqual([x for x in got if x], [x for x in ("/usr/bin", "/bin") if os.path.isdir(x)] or got)
        self.assertNotIn(inside, got); self.assertNotIn("", got); self.assertNotIn(".", got); self.assertNotIn("bin", got)

    def test_a_clean_lint_result_is_not_trusted_when_the_change_edits_lint_configuration_or_suppresses_a_file(self):   # medium
        clean = {"status": "clean", "version": "v", "files": 1, "findings": 0, "summary": "", "lines": []}
        for edits in ({"a/util.py": "x = 2\n", ".flake8": "[flake8]\nexclude = a/util.py\n"}, {"a/util.py": "# flake8: noqa\nimport os\n"}, {"a/util.py": "# ruff: noqa\nimport os\n"},
                      {"a/util.py": "x = 2\n", "pyproject.toml": "[tool.ruff]\nignore = ['ALL']\n"}):
            d = repo_with_change(**edits)
            f = find(decision.check(d, "HEAD", "`ruff check` passes with no issues.", lint_runner=lambda *a: clean), statements.LINT_CLEAN)[0]
            self.assertEqual(f.verdict, "UNKNOWN", edits); self.assertTrue(f.attention); self.assertIn("lint configuration or adds a file-level suppression", f.why)
        d = repo_with_change(**{"a/util.py": "x = 2  # noqa: E501\n"})   # a line-level noqa is ordinary
        f = find(decision.check(d, "HEAD", "`ruff check` passes with no issues.", lint_runner=lambda *a: clean), statements.LINT_CLEAN)[0]
        self.assertEqual(f.verdict, "NOT_CONTRADICTED")
        self.assertIn("files its configuration excludes are skipped", f.why)

    def test_findings_stay_contradicted_even_when_the_config_changed(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n", ".flake8": "[flake8]\n"})
        bad = {"status": "findings", "version": "v", "files": 1, "findings": 1, "summary": "", "lines": ["a/util.py F401"]}
        f = find(decision.check(d, "HEAD", "`ruff check` passes with no issues.", lint_runner=lambda *a: bad), statements.LINT_CLEAN)[0]
        self.assertEqual(f.verdict, "CONTRADICTED")

    def test_paths_with_dot_segments_or_parent_references_are_never_claims_and_the_disk_outside_is_not_probed(self):   # medium
        for text in ("I did not touch `d/./f.py`.", "Removed `d/../../outside.conf`.", "Removed `../x.py`.", "I did not touch `bad.py/`.", "Updated `a/../b.py`."):
            self.assertEqual([k for k, _ in kinds(text) if k == statements.FILES_SCOPE], [], text)
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        outside = Path(tempfile.mkdtemp()); (outside / "secret.conf").write_text("x")
        (d / "link").symlink_to(outside)
        self.assertFalse(statements._exists(d, "link/secret.conf"))   # a symlink out of the repository counts as not existing
        self.assertFalse(statements._exists(d, "../" + outside.name))
        self.assertTrue(statements._exists(d, "a/util.py")); self.assertTrue(statements._exists(d, "a/"))

    def test_an_inner_directory_match_is_ambiguous_for_a_left_alone_claim_but_fine_for_a_changed_claim(self):   # low
        d = repo_with_change(**{"vendor/tests/x.py": "y = 1\n"})
        f = find(decision.check(d, "HEAD", "I did not touch `tests/`."), statements.FILES_SCOPE)[0]
        self.assertEqual(f.verdict, "UNKNOWN"); self.assertFalse(f.attention)
        f = find(decision.check(d, "HEAD", "Added `tests/x.py`."), statements.FILES_SCOPE)[0]
        self.assertEqual(f.verdict, "NOT_CONTRADICTED")

    def test_statements_about_files_alone_never_amount_to_an_allow(self):   # high: "Added `x.py`." used to turn no_claims into an automatic allow
        d = repo_with_change(**{"b/new.py": "z = 1\n"})
        r = decision.check(d, "HEAD", "Added `b/new.py`.")
        self.assertNotEqual(r.status, decision.NO_CONTRA)
        self.assertIn("none", [f.kind for f in r.findings])
        rec = policy.build_receipt(json.loads(json.dumps(__import__("agentvow.report", fromlist=["to_dict"]).to_dict(r))), "o/r", "b" * 40)
        rec["commit"] = "a" * 40
        res = policy.evaluate(rec)
        self.assertEqual(res["decision"], "needs_acknowledgement")
        # but with a tests claim beside it the statement is just one more finding
        weak_only = {"kind": "files_scope", "verdict": "NOT_CONTRADICTED"}
        self.assertTrue(all(c["kind"] in decision.WEAK_KINDS for c in rec["claims"] if c["kind"] != "none"))
        text = " ".join(x["text"] for x in policy.evaluate({**rec, "claims": [{**weak_only, "mismatch": False}]})["reasons"])
        self.assertNotIn("replay", text)   # not described as supported by the replay

    def test_a_mismatch_reaches_the_receipt_and_the_policy_as_its_own_rule(self):   # medium
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        r = decision.check(d, "HEAD", "Updated `docs/guide.md`.")
        rec = policy.build_receipt(__import__("agentvow.report", fromlist=["to_dict"]).to_dict(r), "o/r", "b" * 40)
        rec["commit"] = "a" * 40
        self.assertTrue(any(c.get("mismatch") for c in rec["claims"]))
        self.assertIsNone(policy.validate_receipt(rec))
        res = policy.evaluate(rec)
        self.assertIn("description_mismatch", [x["rule"] for x in res["reasons"]])
        self.assertNotIn("unknown", [x["rule"] for x in res["reasons"] if x["rule"] == "unknown" and "docs" in x["text"]])
        self.assertEqual(policy.evaluate(rec, {"description_mismatch": "allow", "unknown": "allow", "no_claims": "allow"})["decision"], "allow")   # a policy may choose
        bad = json.loads(json.dumps(rec)); bad["claims"][0]["mismatch"] = "yes"
        self.assertIn("mismatch", policy.validate_receipt(bad))
        from agentvow import explain
        self.assertIn("description_mismatch", explain.RULES)

    def test_on_linux_a_repository_under_a_hidden_location_is_bound_read_only_for_the_linter_and_never_writable(self):
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        scratch = Path(tempfile.mkdtemp())
        real = str(d.resolve())
        cmd = runner._bwrap_prefix([scratch], False, ["ruff"], {"PATH": ""}, readonly=[d])
        triples = list(zip(cmd, cmd[1:], cmd[2:]))
        self.assertIn(("--ro-bind", real, real), triples)
        self.assertNotIn(("--bind", real, real), triples)
        cmd = runner._bwrap_prefix([scratch], False, ["ruff"], {"PATH": ""})
        self.assertNotIn(("--ro-bind", real, real), list(zip(cmd, cmd[1:], cmd[2:])))

    def test_a_timeout_goes_through_the_process_group_killer(self):   # low: subprocess.run(timeout) leaves a plugin's children running
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        with mock.patch.object(lint.shutil, "which", return_value="/bin/echo"), mock.patch.object(runner, "sandbox_problem", return_value=None), \
                mock.patch.object(runner, "_run_group", side_effect=subprocess.TimeoutExpired("x", 1)) as g:
            res = lint.run(d, "ruff check", ["a/util.py"])
        self.assertEqual(res["status"], "error"); self.assertTrue(g.called)

    @unittest.skipIf(runner.sandbox_problem(), "needs a working sandbox")
    def test_the_sandbox_with_a_read_only_repository_really_refuses_a_write_into_it(self):   # the old test of this was vacuous (ruff --no-cache never writes)
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        scratch = Path(tempfile.mkdtemp(prefix="al", dir=runner.scratch_base())).resolve()
        code = "import sys\nfor p in sys.argv[1:]:\n    try:\n        open(p, 'w').write('x'); print('wrote', p)\n    except OSError as e:\n        print('refused', p)\n"
        argv = runner.wrap([sys.executable, "-I", "-c", code, str(d.resolve() / "pwned.txt"), str(scratch / "ok.txt")], scratch, scratch, env={"PATH": os.environ.get("PATH", "")}, readonly=[d.resolve()])
        out = subprocess.run(argv, capture_output=True, text=True, cwd=d, timeout=60).stdout
        self.assertIn("refused", out.splitlines()[0]); self.assertIn("wrote", out.splitlines()[1])
        self.assertFalse((d / "pwned.txt").exists())


class Feedback(unittest.TestCase):
    def test_the_feedback_to_the_agent_has_a_fixed_reason_for_the_new_kinds_and_no_repository_strings(self):
        from agentvow import cli
        d = repo_with_change(**{"a/util.py": "x = 2\n"})
        r = decision.check(d, "HEAD", "`ruff check` passes with no issues.", lint_runner=lambda repo, tool, files: {"status": "findings", "version": "v", "files": 1, "findings": 1, "summary": "x", "lines": ["a/util.py:1:1: F401 secret-path"]})
        text = cli.agent_feedback(r)
        self.assertIn("the linter reports findings", text)
        self.assertNotIn("secret-path", text)   # the linter's lines are repository-controlled and never go back to the agent

    def test_a_mismatch_needing_a_person_does_not_go_back_to_the_agent_as_contradicted(self):
        from agentvow import cli
        d = repo_with_change(**{"tests/test_a.py": "x\n"})
        self.assertIsNone(cli.agent_feedback(decision.check(d, "HEAD", "I did not touch `tests/test_a.py`.")))


if __name__ == "__main__":
    unittest.main()
