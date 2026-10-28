import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "shadow"))
import faults  # noqa: E402

SRC = '''import os


def f(x, items):
    # comment x == 1
    if x == 3:
        return x
    y = items[2]
    ok = True
    return y > 4


def g():
    return 1


TOP = 5 < 6
'''


class Faults(unittest.TestCase):
    def test_every_candidate_parses_and_differs(self):
        c = faults.candidates(SRC, set(range(1, SRC.count("\n") + 2)))
        self.assertTrue(c)
        for n, t, new in c:
            out = faults.apply(SRC, (n, t, new))
            ast.parse(out)
            self.assertNotEqual(out, SRC)

    def test_comments_strings_and_imports_are_never_mutated(self):
        lines = {n for n, _, _ in faults.candidates(SRC, set(range(1, SRC.count("\n") + 2)))}
        self.assertNotIn(1, lines)
        self.assertNotIn(5, lines)

    def test_types_present(self):
        kinds = {t for _, t, _ in faults.candidates(SRC, set(range(1, SRC.count("\n") + 2)))}
        self.assertEqual(kinds, set(faults.TYPES))

    def test_scope_is_the_touched_function_not_the_whole_file(self):
        scope = faults.touched_functions(SRC, {6})
        self.assertIn(8, scope)        # same function, line the change did not touch
        self.assertNotIn(13, scope)    # another function
        self.assertNotIn(16, scope)

    def test_invalid_program_is_rejected(self):
        # negating inside a context where the result would not parse must be dropped, never emitted
        for n, t, new in faults.candidates("x = [1 < 2\n    ,3]\n", {1, 2}):
            ast.parse(faults.apply("x = [1 < 2\n    ,3]\n", (n, t, new)))

    def test_strings_and_comments_are_never_edited(self):
        src = 'def f(a):\n    s = "a == b"  # True == x\n    t = f"{a} == 1"\n    return a\n'
        for n, t, new in faults.candidates(src, {2, 3}):
            self.fail(f"mutated a string or comment line {n}: {new!r}")

    def test_operator_next_to_a_string_is_still_edited_outside_it(self):
        src = 'def f(a):\n    if a == "x == 1":\n        return 1\n'
        flips = [new for n, t, new in faults.candidates(src, {2}) if t == "flip"]
        self.assertEqual(flips, ['    if a != "x == 1":\n'])

    def test_return_none_is_not_planted_in_a_generator(self):
        src = "def g():\n    yield 1\n    return 2\n\n\ndef h():\n    return 2\n"
        got = {n for n, t, _ in faults.candidates(src, {3, 7}) if t == "return_none"}
        self.assertEqual(got, {7})

    def test_while_true_is_not_flipped(self):
        self.assertEqual([t for _, t, _ in faults.candidates("while True:\n    pass\n", {1}) if t == "constant"], [])

    def test_pick_is_deterministic_and_type_diverse(self):
        c = faults.candidates(SRC, set(range(1, SRC.count("\n") + 2)))
        a, b = faults.pick(c, "s", 3), faults.pick(c, "s", 3)
        self.assertEqual(a, b)
        self.assertEqual(len({t for _, t, _ in a}), len(a))


if __name__ == "__main__":
    unittest.main()
