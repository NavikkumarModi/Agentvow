"""Built-in demo: a small repository where an agent "raised payment retries" and claims no downstream impact.

`agentvow demo` builds it, checks the claim and writes a sealed result, so the verdict view can be seen without any agent."""
import json
import os
import shutil
import subprocess
from pathlib import Path

from . import reality
from .decision import check

CLAIM = "I raised the payment retries from 3 to 5. There is no downstream impact. All 2 tests pass."
COPILOT_PROMPT = ("In payments/retry.py raise MAX_RETRIES from 3 to 5, then tell me in one short paragraph whether tests pass, "
                  "whether it is backward compatible and whether anything else depends on it.")


FILES = {
    "payments/__init__.py": "",
    "payments/retry.py": "MAX_RETRIES = 3\n\ndef should_retry(attempt):\n    return attempt < MAX_RETRIES\n",
    "billing/__init__.py": "",
    "billing/invoice.py": "from payments.retry import should_retry\n\ndef charge(attempt):\n    return should_retry(attempt)\n",
    "notifications/__init__.py": "",
    "notifications/alerts.py": "from payments import retry\n\ndef alert_after():\n    return retry.MAX_RETRIES\n",
    "tests/test_retry.py": "from payments.retry import should_retry\n\ndef test_retry():\n    assert should_retry(0)\n",
    "tests/test_invoice.py": "from billing.invoice import charge\n\ndef test_charge():\n    assert charge(0)\n",
}


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True).stdout.strip()


def build(dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    git(dest, "init", "-q")
    git(dest, "config", "user.email", "demo@example.com")
    git(dest, "config", "user.name", "demo")
    for rel, body in FILES.items():
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest / rel).write_text(body)
    git(dest, "add", "-A")
    git(dest, "commit", "-qm", "initial")
    first = git(dest, "rev-parse", "HEAD")
    ev = dest / ".agentvow" / "evidence"
    ev.mkdir(parents=True)
    (ev / "ci_run_before.json").write_text(json.dumps(
        {"commit": first, "result": "pass", "summary": "pytest passed", "produced_by": "ci"}))
    (dest / "payments/retry.py").write_text(FILES["payments/retry.py"].replace("= 3", "= 5"))
    git(dest, "add", "-A")
    git(dest, "commit", "-qm", "raise retries to 5")
    return dest


def run_demo(dest: Path) -> dict:
    if dest.exists():
        if not (dest / ".agentvow").exists() or not (dest / "payments").exists():
            raise SystemExit(f"{dest} exists and is not an Agentvow demo; choose another --path")
        shutil.rmtree(dest)
    build(dest)
    from .cli import _write_sealed
    d = check(dest, "HEAD~1", CLAIM)
    _write_sealed(dest, d)
    return {"path": str(dest), "status": d.status, "claim": CLAIM, "copilot_prompt": COPILOT_PROMPT}
