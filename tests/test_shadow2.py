import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "shadow2"))
try:
    import policy
    import analyze
except ImportError:   # research tools need pandas for some imports; skip without it
    policy = analyze = None


@unittest.skipIf(policy is None, "research tools unavailable")
class Policy(unittest.TestCase):
    def f(self, kind, verdict, attention=False):
        return {"kind": kind, "verdict": verdict, "attention": attention}

    def test_unknown_on_tests_is_review_only_under_strict(self):
        fs = [self.f("tests_pass", "UNKNOWN")]
        self.assertEqual((policy.decide(fs, "strict"), policy.decide(fs, "lenient")), ("review", "proceed"))

    def test_contradicted_and_attention_are_review_under_both(self):
        for fs in ([self.f("lint_clean", "CONTRADICTED")], [self.f("files_scope", "UNKNOWN", True)]):
            self.assertEqual((policy.decide(fs, "strict"), policy.decide(fs, "lenient")), ("review", "review"))

    def test_no_checkable_claim_is_review_under_strict_proceed_under_lenient(self):
        self.assertEqual((policy.decide([], "strict"), policy.decide([self.f("none", "UNKNOWN")], "lenient")), ("review", "proceed"))

    def test_all_clear_findings_proceed(self):
        fs = [self.f("tests_pass", "NOT_CONTRADICTED"), self.f("files_scope", "NOT_CONTRADICTED")]
        self.assertEqual((policy.decide(fs, "strict"), policy.decide(fs, "lenient")), ("proceed", "proceed"))


@unittest.skipIf(analyze is None, "research tools unavailable")
class Estimators(unittest.TestCase):
    def test_classify(self):
        L = lambda s, l: {"step_a": s, "label": l}
        self.assertEqual(analyze.classify([L("CLAIM", "TRUE"), L("CLAIM", "FALSE")]), "positive")
        self.assertEqual(analyze.classify([L("CLAIM", "TRUE")]), "negative")
        self.assertEqual(analyze.classify([L("CLAIM", "CANNOT_TELL"), L("NOT_A_CLAIM", None)]), "unscorable")
        self.assertEqual(analyze.classify([L("CLAIM", "CANNOT_TELL")], "pessimistic"), "positive")
        self.assertEqual(analyze.classify([L("CLAIM", "CANNOT_TELL")], "optimistic"), "negative")

    def test_weighted_recall_uses_inverse_probability_weights(self):
        w = {"a": 1.0, "b": 10.0}
        self.assertAlmostEqual(analyze.weighted_recall(["a", "b"], {"a"}, w), 1 / 11)
        self.assertIsNone(analyze.weighted_recall([], {"a"}, w))

    def test_top_set_is_the_budget_share_with_deterministic_ties(self):
        ids = [str(i) for i in range(10)]
        score = {i: 0 for i in ids}
        score["3"] = 5
        a = analyze.top_set(ids, score, 1, "t", 0.2)
        self.assertEqual(len(a), 2)
        self.assertIn("3", a)
        self.assertEqual(a, analyze.top_set(ids, score, 1, "t", 0.2))


if __name__ == "__main__":
    unittest.main()
