"""Aggregate-only survey of Claude Code session transcripts.

Prints COUNTS ONLY: per project, how many sessions have a final assistant message and how many
claims of each kind Agentvow's rule-based extractor finds in it. It never prints message text,
file contents, paths inside sessions, or tool output.

Usage: python3 scripts/survey_sessions.py <project_dir> [<project_dir> ...]
  e.g. python3 scripts/survey_sessions.py ~/.claude/projects/-Users-me-Documents-myrepo
Top-level session files only (subagent transcripts are skipped).
"""
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agentvow import claims  # noqa: E402


def final_text(path: Path):
    last = None
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get("type") != "assistant":
                continue
            content = (o.get("message") or {}).get("content")
            if isinstance(content, list):
                text = "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
                if text.strip():
                    last = text
    return last


def main(dirs):
    for d in dirs:
        d = Path(d).expanduser()
        sessions = sorted(d.glob("*.jsonl"))
        n_final, with_claims = 0, 0
        kinds = collections.Counter()
        for s in sessions:
            text = final_text(s)
            if text is None:
                continue
            n_final += 1
            found = claims.extract(text)
            if found:
                with_claims += 1
            kinds.update(c.kind for c in found)
        label = d.name[-24:]  # trailing part of the directory name only
        print(f"project …{label}: sessions={len(sessions)} with_final_message={n_final} "
              f"with_any_claim={with_claims} claims={dict(kinds)}")


if __name__ == "__main__":
    main(sys.argv[1:])
