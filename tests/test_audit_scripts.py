import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research" / "audit"))
import classify  # noqa: E402
import draw  # noqa: E402

import pandas as pd  # noqa: E402

TREE = {"pyproject.toml", "src/pkg/__init__.py", "tests/test_a.py"}
PYPROJ = '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n[project]\nname="p"\ndependencies=["requests"]\n[project.optional-dependencies]\ntest=["pytest"]\n'


class Classify(unittest.TestCase):
    def test_plain_pip(self):
        r = classify.classify(TREE, {"pyproject.toml": PYPROJ})
        self.assertEqual((r["class"], r["reasons"]), ("plain_pip", []))

    def test_each_rule_alone_makes_it_not_plain(self):
        cases = {
            "lock": (TREE | {"uv.lock"}, {"pyproject.toml": PYPROJ}),
            "node": (TREE | {"package.json"}, {"pyproject.toml": PYPROJ}),
            "compiler": (TREE, {"pyproject.toml": PYPROJ.replace('"setuptools"', '"maturin>=1"')}),
            "git dependency": (TREE, {"pyproject.toml": PYPROJ.replace('"requests"', '"x @ git+https://github.com/a/b"')}),
            "services": (TREE, {"pyproject.toml": PYPROJ.replace('"requests"', '"psycopg2"')}),
            "compose": (TREE | {"docker-compose.yml"}, {"pyproject.toml": PYPROJ}),
            "conda": (TREE | {"environment.yml"}, {"pyproject.toml": PYPROJ}),
            "no tests": ({"pyproject.toml", "src/a.py"}, {"pyproject.toml": PYPROJ.replace('["pytest"]', '[]')}),
        }
        for name, (tree, text) in cases.items():
            with self.subTest(name):
                r = classify.classify(tree, text)
                self.assertEqual(r["class"], "not_plain")
                self.assertEqual(len(r["reasons"]), 1, r["reasons"])

    def test_subproject_only_repository_is_not_plain(self):
        r = classify.classify({"api/pyproject.toml", "api/tests/test_x.py"}, {})
        self.assertEqual(r["class"], "not_plain")
        self.assertIn("api", r["facts"]["subprojects"])

    def test_empty_tree_is_unclassifiable_not_plain(self):
        self.assertEqual(classify.classify(set(), {})["class"], "unclassifiable")

    def test_reads_the_commit_not_the_working_tree(self):
        with tempfile.TemporaryDirectory() as t:
            def g(*a):
                subprocess.run(["git", "-C", t, "-c", "user.email=a@b", "-c", "user.name=n", *a], check=True, capture_output=True)
            g("init", "-q")
            (Path(t) / "pyproject.toml").write_text(PYPROJ); (Path(t) / "tests").mkdir(); (Path(t) / "tests/test_a.py").write_text("def test_a(): pass\n")
            g("add", "-A"); g("commit", "-qm", "base")
            base = subprocess.run(["git", "-C", t, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
            (Path(t) / "uv.lock").write_text("x"); g("add", "-A"); g("commit", "-qm", "later")
            self.assertEqual(classify.classify(*classify.from_git(Path(t), base))["class"], "plain_pip")
            self.assertEqual(classify.classify(*classify.from_git(Path(t), "HEAD"))["class"], "not_plain")


def frame():
    rows = []
    for agent in ("A", "B"):
        for lang in ("python", "other"):
            for i in range(12):
                repo = f"o/{agent}{lang}{i % 6}"
                rows.append({"html_url": f"https://github.com/{repo}/pull/{i}", "agent": agent, "lang": lang, "stratum": f"{agent}|{lang}", "repo": repo, "number": i, "in_scope": ["tests_pass"], "claims": ["tests_pass"]})
    return pd.DataFrame(rows).sort_values("html_url").reset_index(drop=True)


class Draw(unittest.TestCase):
    def test_deterministic_given_the_seed_and_different_for_another(self):
        d = frame()
        a, _ = draw.draw(d, 1, 16, 3, 0.6)
        b, _ = draw.draw(d, 1, 16, 3, 0.6)
        c, _ = draw.draw(d, 2, 16, 3, 0.6)
        self.assertEqual(a, b)
        self.assertNotEqual([r["pr"] for r in a], [r["pr"] for r in c])

    def test_repository_cap_and_agent_cap(self):
        rows, _ = draw.draw(frame(), 7, 40, 1, 0.5)
        repos = [r["repo"] for r in rows]
        self.assertEqual(len(repos), len(set(repos)))
        for agent in ("A", "B"):
            self.assertLessEqual(sum(r["agent"] == agent for r in rows), int(0.5 * len(rows)) + 1)

    def test_rank_is_the_replacement_order_within_a_stratum(self):
        rows, pool = draw.draw(frame(), 3, 8, 3, 0.9)
        for s in {r["stratum"] for r in rows}:
            ranks = [r["rank"] for r in rows if r["stratum"] == s]
            self.assertEqual(ranks, sorted(ranks))
            self.assertLess(max(ranks), pool[s])

    def test_the_draw_never_selects_an_excluded_pull_request(self):
        d = frame()
        ex = set(d.html_url[:20])
        rows, _ = draw.draw(d[~d.html_url.isin(ex)].reset_index(drop=True), 5, 20, 3, 0.9)
        self.assertFalse({r["pr"] for r in rows} & ex)

    def test_quotas_take_small_strata_whole_and_give_the_surplus_to_larger_ones(self):
        q = draw.quotas({"A|python": 3, "B|python": 50, "A|other": 100, "B|other": 100}, 40, 0.5)
        self.assertEqual(q["A|python"], 3)
        self.assertEqual(q["B|python"], 17)
        self.assertEqual(q["A|other"] + q["B|other"], 20)
        self.assertEqual(sum(q.values()), 40)

    def test_quotas_never_exceed_the_pool(self):
        q = draw.quotas({"A|python": 2, "A|other": 5}, 100, 0.5)
        self.assertEqual(q, {"A|python": 2, "A|other": 5})

    def test_python_share_is_honoured_in_the_draw(self):
        rows, _ = draw.draw(frame(), 3, 20, 5, 0.9, python_share=0.5)
        self.assertEqual(sum(r["stratum"].endswith("|python") for r in rows), 10)

    def test_seed_is_required(self):
        with self.assertRaises(SystemExit):
            draw.main(["--out", "/tmp/x.json"])


if __name__ == "__main__":
    unittest.main()
