"""Coverage of the statements agents make in their final messages: what share can be confirmed, contradicted or only left as 'not checked' with the checkers that exist today?
Runs the deterministic file checks for statements that carry one. Usage: python3 research/autonomy/claim_coverage.py"""
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import b6_statements as B  # noqa: E402
import label_b6 as L  # noqa: E402


def file_check(files, how, paths):
    def hit(p):
        return any(f == p or (p.endswith("/") and f.startswith(p)) or (f.endswith("/") and p.startswith(f)) for f in files)
    changed = [hit(p) for p in paths]
    return all(changed) if how == "changed" else not any(changed)


def main():
    V = L.valid_runs()
    S = B.STATEMENTS
    by = collections.Counter(c for _, c, _, _ in S)
    levels = collections.Counter(B.CLASSES[c][1] for _, c, _, _ in S)
    n = len(S)
    print(f"{n} statements in {len({r for r, *_ in S})} messages ({n / len(V):.1f} per message)\n")
    print("| class | what | statements | checker |\n|---|---|---|---|")
    for c, (what, lvl) in B.CLASSES.items():
        print(f"| {c} | {what} | {by[c]} | {lvl} |")
    print("\n| checker level | statements | share |\n|---|---|---|")
    for lvl in ("today", "partial", "feasible", "hard", "unverifiable"):
        print(f"| {lvl} | {levels[lvl]} | {levels[lvl] / n:.0%} |")
    checks = [(r, t, ck) for r, _, t, ck in S if ck]
    ok = bad = 0
    for r, t, (how, paths) in checks:
        res = file_check(V[r]["files_changed"], how, paths)
        ok += res; bad += not res
        if not res:
            print(f"FILE CHECK FAILED  run {r}: {t} ({how} {paths}); changed files: {V[r]['files_changed']}")
    print(f"\nfile checks run: {len(checks)}; consistent with the changed-file list: {ok}; contradicted: {bad}")


if __name__ == "__main__":
    main()
