import io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentvow import bundle, capsule, cli, reality, runner  # noqa: E402


def repo_with_change():
    d = Path(tempfile.mkdtemp())
    g = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True).stdout.strip()
    g("init", "-q", "-b", "main"); g("config", "user.email", "a@b"); g("config", "user.name", "t")
    (d / "a.py").write_text("x = 1\n"); (d / ".gitignore").write_text("secret.txt\n"); (d / "test_a.py").write_text("from a import x\ndef test_x(): assert x in (1, 2)\n")
    g("add", "-A"); g("commit", "-qm", "base")
    (d / "a.py").write_text("x = 2\n"); (d / "new.py").write_text("y = 1\n"); (d / "secret.txt").write_text("s3cr3t")
    return d, g


def make_bundle(d, **over):
    rec = {"packages": ["six==1.16.0", "attrs==23.1.0"], "python_version": "3.13.5", "platform": "Darwin", "created_at": "t", "source": "stop", "command": "pytest", "commit": "a" * 40,
           "git_tree": reality.git_tree_hash(d), **over}
    return bundle.export(rec)


class TreeHash(unittest.TestCase):
    def test_hash_of_a_dirty_tree_equals_the_tree_of_the_commit_made_later_and_writes_nothing(self):
        d, g = repo_with_change()
        (d / ".agentvow").mkdir(); (d / ".agentvow" / "z").write_text("q")
        before = sorted(p.name for p in (d / ".git" / "objects").rglob("*") if p.is_file())
        h = reality.git_tree_hash(d)
        self.assertEqual(before, sorted(p.name for p in (d / ".git" / "objects").rglob("*") if p.is_file()))
        g("add", "-A", "--", ".", ":(exclude).agentvow"); g("commit", "-qm", "later")
        self.assertEqual(h, g("rev-parse", "HEAD^{tree}"))
        self.assertEqual(reality.git_tree_hash(d), h)   # clean now: still the same
        (d / "new.py").write_text("y = 2\n")
        self.assertNotEqual(reality.git_tree_hash(d), h)   # any later edit changes it


    def test_a_policy_file_the_commit_tracks_under_agentvow_is_content_but_untracked_state_is_not(self):
        # found by the live GitHub test: a committed .agentvow/policy.json made the receipt's hash differ from the commit's tree, so the service refused every receipt
        d, g = repo_with_change()
        g("add", "-A"); g("commit", "-qm", "all")
        (d / ".agentvow").mkdir(); (d / ".agentvow" / "policy.json").write_text("{}\n")
        g("add", "-f", ".agentvow/policy.json"); g("commit", "-qm", "policy")
        (d / ".agentvow" / "capsule.json").write_text("local state")   # untracked Agentvow state: not content
        self.assertEqual(reality.git_tree_hash(d), g("rev-parse", "HEAD^{tree}"))
        (d / ".agentvow" / "policy.json").write_text('{"x": 1}\n')    # a tracked file changed on disk: content
        self.assertNotEqual(reality.git_tree_hash(d), g("rev-parse", "HEAD^{tree}"))

    def test_works_when_agentvow_dir_is_gitignored_or_committed_state_is_clean(self):
        d, g = repo_with_change()
        (d / ".gitignore").write_text("secret.txt\n.agentvow/\n.venv/\n")
        (d / ".agentvow").mkdir(); (d / ".agentvow" / "x").write_text("1")
        h = reality.git_tree_hash(d)
        g("add", "-A"); g("commit", "-qm", "all")
        self.assertEqual(reality.git_tree_hash(d), h)
        self.assertEqual(h, g("rev-parse", "HEAD^{tree}"))


class HashPortability(unittest.TestCase):
    def test_the_same_files_hash_the_same_whatever_the_machine_and_user_git_config(self):
        d, g = repo_with_change()
        (d / "run.sh").write_text("#!/bin/sh\necho hi\n"); (d / "run.sh").chmod(0o755)
        (d / "crlf.txt").write_bytes(b"a\r\nb\r\n")
        want = reality.git_tree_hash(d)
        home = Path(tempfile.mkdtemp())
        (home / ".gitconfig").write_text("[core]\n  autocrlf = true\n  fileMode = false\n  excludesFile = " + str(home / "ign") + "\n[user]\n  name = x\n")
        (home / "ign").write_text("new.py\ncrlf.txt\n")
        (d / ".git" / "config").write_text((d / ".git" / "config").read_text() + "[core]\n  autocrlf = input\n  fileMode = false\n")
        with mock.patch.dict(os.environ, {"HOME": str(home), "XDG_CONFIG_HOME": str(home)}):
            self.assertEqual(reality.git_tree_hash(d), want)


class Bundle(unittest.TestCase):
    def test_export_has_no_signature_no_env_values_and_validates(self):
        d, g = repo_with_change()
        b = make_bundle(d)
        self.assertIsNone(bundle.validate(b))
        self.assertNotIn("sig", b)
        self.assertIs(b["env_values_recorded"], False)
        with mock.patch.dict(os.environ, {"MY_SECRET_TOKEN": "hunter2-token"}):
            self.assertNotIn("hunter2-token", json.dumps(make_bundle(d)))

    def test_validation_is_strict(self):
        d, g = repo_with_change()
        b = make_bundle(d)
        for mutate, frag in ((lambda x: x.update(extra=1), "unexpected keys"), (lambda x: x["packages"].append("evil @ https://x/e.whl"), "plain"),
                             (lambda x: x["packages"].append("a==1; rm -rf /"), "plain"), (lambda x: x.update(git_tree="zz"), "git object"),
                             (lambda x: x["packages"].append("six==1.*"), "plain"), (lambda x: x.update(env_values_recorded=True), "environment values"), (lambda x: x.update(packages_sha256="0" * 64), "hash"),
                             (lambda x: x.update(python_version="3.x; ls"), "python_version"), (lambda x: x.update(schema="agentvow-capture/9"), "schema")):
            c = json.loads(json.dumps(b)); mutate(c)
            self.assertIn(frag, bundle.validate(c) or "", frag)
        self.assertIsNotNone(bundle.validate([1, 2]))

    def test_load_refuses_symlinks_oversize_and_garbage(self):
        d, g = repo_with_change()
        f = Path(tempfile.mkdtemp()) / "b.json"
        f.write_text(json.dumps(make_bundle(d)))
        self.assertEqual(bundle.load(f)[1], "")
        link = f.with_name("link.json"); link.symlink_to(f)
        self.assertIsNone(bundle.load(link)[0])
        f.write_text("not json")
        self.assertIsNone(bundle.load(f)[0])

    def test_bind_accepts_the_exact_state_and_refuses_every_stale_or_foreign_bundle(self):
        d, g = repo_with_change()
        b = make_bundle(d)
        cap, why = bundle.bind(d, b)
        self.assertEqual(why, "")
        self.assertIs(cap["authenticated"], False)
        self.assertEqual(cap["capture_source"], "bundle")
        # (1) a file edited after the capture
        (d / "new.py").write_text("y = 99\n")
        self.assertIn("different files", bundle.bind(d, b)[1])
        (d / "new.py").write_text("y = 1\n")
        self.assertEqual(bundle.bind(d, b)[1], "")
        # (2) a different commit
        g("add", "-A", "--", ".", ":(exclude).agentvow"); g("commit", "-qm", "two")
        (d / "a.py").write_text("x = 3\n"); g("commit", "-qam", "three")
        self.assertIn("different files", bundle.bind(d, b)[1])
        # (3) a bundle made for another repository
        other, _ = repo_with_change()
        (other / "unrelated.py").write_text("z = 1\n")
        self.assertIn("different files", bundle.bind(other, b)[1])
        # (4) an untracked file added after
        d2, _ = repo_with_change()
        b2 = make_bundle(d2)
        (d2 / "late.py").write_text("q = 1\n")
        self.assertIn("different files", bundle.bind(d2, b2)[1])

    def test_ignored_files_and_agentvow_dir_do_not_change_the_binding(self):
        d, g = repo_with_change()
        b = make_bundle(d)
        (d / "secret.txt").write_text("changed secret")
        (d / ".agentvow").mkdir(); (d / ".agentvow" / "x").write_text("1")
        self.assertEqual(bundle.bind(d, b)[1], "")


@unittest.skipIf(runner.sandbox_problem(), "no working sandbox on this machine")
class EndToEnd(unittest.TestCase):
    def run_check(self, d, bundle_path, base):
        os.environ["AGENTVOW_HOME"] = tempfile.mkdtemp(prefix="bh_")
        old = sys.stdin, sys.stdout, sys.stderr
        sys.stdin, out, sys.stderr = io.StringIO("All tests pass."), io.StringIO(), io.StringIO()
        sys.stdout = out
        try:
            code = cli.main(["check", "--repo", str(d), "--base", base, "--run-tests", "--from-capture", str(bundle_path), "--json"])
        finally:
            sys.stdin, sys.stdout, sys.stderr = old
        return code, json.loads(out.getvalue())

    def test_a_mismatched_bundle_is_refused_without_replay_and_never_supported(self):
        d, g = repo_with_change()
        f = Path(tempfile.mkdtemp()) / "b.json"
        f.write_text(json.dumps(make_bundle(d)))
        (d / "new.py").write_text("y = 5\n")   # changed after the capture
        code, o = self.run_check(d, f, "HEAD")
        t = next(x for x in o["findings"] if x["kind"] == "tests_pass")
        self.assertNotIn(t["verdict"], ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED"))
        self.assertIn("capture bundle was not used", o["scope"])
        self.assertIn("different files", o["scope"])

    def test_a_garbage_bundle_is_refused(self):
        d, g = repo_with_change()
        f = Path(tempfile.mkdtemp()) / "b.json"
        f.write_text("{}")
        code, o = self.run_check(d, f, "HEAD")
        t = next(x for x in o["findings"] if x["kind"] == "tests_pass")
        self.assertEqual(t["verdict"], "UNKNOWN")
        self.assertIn("not a capture bundle", o["scope"])


if __name__ == "__main__":
    unittest.main()
