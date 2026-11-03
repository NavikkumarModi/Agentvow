import io
import json
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
from agentvow import ghreceipts, queue  # noqa: E402
from test_pilot_report import rcpt  # noqa: E402

REPO = "o/n"


def zip_of(r, name="receipt.json"):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr(name, json.dumps(r))
    return b.getvalue()


def fake_gh(prs, runs, artifacts, zips):
    """prs: [(number, sha)]; runs: {sha: [run ids]}; artifacts: {run id: [artifact dict]}; zips: {artifact id: bytes}."""
    def run(cmd, capture_output=True, text=True, timeout=0):
        path = cmd[2]
        def ok(o):
            return subprocess.CompletedProcess(cmd, 0, json.dumps(o) if text else o, "")
        if "/pulls?" in path:
            return ok([{"number": n, "head": {"sha": s}} for n, s in prs])
        if "/actions/runs?head_sha=" in path:
            sha = path.split("head_sha=")[1].split("&")[0]
            return ok({"workflow_runs": [{"id": i, "created_at": f"2026-11-0{i % 9 + 1}"} for i in runs.get(sha, [])]})
        if path.endswith("/artifacts"):
            return ok({"artifacts": artifacts.get(int(path.split("/")[-2]), [])})
        if path.endswith("/zip"):
            return ok(zips[int(path.split("/")[-2])])
        return subprocess.CompletedProcess(cmd, 1, "", "")
    return run


def art(i, size=100, expired=False, name=ghreceipts.ARTIFACT):
    return {"id": i, "name": name, "size_in_bytes": size, "expired": expired}


class Fetch(unittest.TestCase):
    def setUp(self):
        self.sha1, self.sha2 = f"{1:040x}", f"{2:040x}"

    def test_a_matching_receipt_is_kept_and_a_missing_one_is_listed(self):
        r = rcpt(1, "UNKNOWN"); r["repo"] = REPO
        run = fake_gh([(7, self.sha1), (8, self.sha2)], {self.sha1: [11]}, {11: [art(21)]}, {21: zip_of(r)})
        got, missing, note = ghreceipts.fetch(REPO, run=run)
        self.assertEqual([(x["commit"], x["pr"]) for x in got], [(self.sha1, 7)])
        self.assertEqual([m["pr"] for m in missing], [8])
        self.assertIn("not authenticated", note)

    def test_a_receipt_for_another_commit_or_repository_is_refused(self):
        wrong_commit = rcpt(9); wrong_commit["repo"] = REPO
        wrong_repo = rcpt(1)   # repo is o/n but we ask for x/y
        run = fake_gh([(7, self.sha1)], {self.sha1: [11]}, {11: [art(21)]}, {21: zip_of(wrong_commit)})
        self.assertEqual(ghreceipts.fetch(REPO, run=run)[0], [])
        run = fake_gh([(7, self.sha1)], {self.sha1: [11]}, {11: [art(21)]}, {21: zip_of(wrong_repo)})
        self.assertEqual(ghreceipts.fetch("x/y", run=run)[0], [])

    def test_oversized_expired_wrong_name_and_bad_zip_are_not_read(self):
        r = rcpt(1); r["repo"] = REPO
        for a, z in ((art(21, size=5_000_000), zip_of(r)), (art(21, expired=True), zip_of(r)), (art(21, name="other"), zip_of(r)), (art(21), b"not a zip"), (art(21), zip_of(r, "../receipt.json"))):
            run = fake_gh([(7, self.sha1)], {self.sha1: [11]}, {11: [a]}, {21: z})
            got, missing, _ = ghreceipts.fetch(REPO, run=run)
            self.assertEqual((got, [m["pr"] for m in missing]), ([], [7]), a)

    def test_the_repository_name_is_validated_before_any_call(self):
        for bad in ("a", "a/b/c", "../x", "a b/c", "a/..", ";x/y"):
            with self.assertRaises(ValueError):
                ghreceipts.fetch(bad, run=lambda *a, **k: self.fail("gh was called"))

    def test_gh_failure_is_an_error_not_an_empty_queue(self):
        with self.assertRaises(RuntimeError):
            ghreceipts.fetch(REPO, run=lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, "", "no"))

    def test_the_queue_names_pull_requests_without_a_receipt(self):
        text = queue.render_text([], [{"pr": 8, "why": "no gate run found for the head commit"}], "note here")
        self.assertIn("#8", text); self.assertIn("not a clean result", text)
        self.assertIn("#8", queue.render_markdown([], missing=[{"pr": 8, "why": "x"}]))


if __name__ == "__main__":
    unittest.main()
