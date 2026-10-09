"""Build a small realistic repo for the 'No downstream impact' demo.

Usage: python examples/make_demo.py /tmp/payments_demo
Scenario: an agent raises payment retries from 3 to 5 and claims there is no downstream impact.
  - billing.invoice and notifications.alerts both import payments.retry
  - alerts has no test; invoice is tested
  - an earlier verification artifact belongs to the previous commit (stale)
"""
import json
import subprocess
import sys
from pathlib import Path

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


if __name__ == "__main__":
    print(build(Path(sys.argv[1])))
