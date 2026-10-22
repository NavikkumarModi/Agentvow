"""Builds docs/pilot/EXAMPLE_REPORT.md from SYNTHETIC receipts (deterministic; no real team's data). Usage: python3 scripts/make_example_pilot_report.py"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agentvow import pilot_report, policy  # noqa: E402


def synthetic():
    """40 receipts over five weeks with a plausible, invented mix. Every value here is made up for the example."""
    out = []
    plan = [("SUPPORTED_BY_PRIOR_EVIDENCE", "both", (3, 4)), ("SUPPORTED_BY_PRIOR_EVIDENCE", "single", (2, 5)), ("UNKNOWN", "single", (0, 0)), ("UNKNOWN", "native_only", (1, 6)),
            ("CONTRADICTED", "captured_only", (2, 7)), ("NOT_CONTRADICTED", "both", (5, 5))]
    for i in range(40):
        verdict, repro, cov = plan[i % len(plan)]
        r = {"schema": policy.RECEIPT, "tool_version": "x", "created_at": f"2026-11-{1 + (i * 28) // 40:02d}T10:{i:02d}:00+00:00", "repo": "example-org/example-service", "commit": f"{i:040x}", "git_tree": f"{i + 1000:040x}",
             "base": "main", "pr": 100 + i, "status": "x", "claims": [{"kind": "tests_pass", "verdict": verdict, "basis": "", "capture_source": "bundle" if i % 9 == 0 else "", "dropped_pins": 0, "changed_lines": None}],
             "unexamined": 0, "reproducibility": repro, "contexts": [], "coverage": {"executed": cov[0], "executable": cov[1]} if cov[1] else None,
             "not_reproduced": ["environment variables"] + (["network use"] if i % 3 == 0 else []) + (["external programs the tests invoke"] if i % 5 == 0 else [])}
        out.append(r)
    return out


def main():
    d = Path(tempfile.mkdtemp())
    for i, r in enumerate(synthetic()):
        (d / f"r{i:03d}.json").write_text(json.dumps(r))
    rcpts, bad = pilot_report.load(d)
    s = pilot_report.summarize(rcpts, {"schema": policy.POLICY, "acknowledgers": ["alice"], "min_changed_line_coverage": 0.5})
    text = pilot_report.render_markdown(s, "Agent pull request evidence report: example-org/example-service", example=True)
    (ROOT / "docs" / "pilot" / "EXAMPLE_REPORT.md").write_text(text, encoding="utf-8")
    print("written", len(text), "characters")


if __name__ == "__main__":
    main()
