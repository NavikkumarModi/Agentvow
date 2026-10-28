"""Shared helpers for the shadow experiment (docs/research/SHADOW_EXPERIMENT_PREREG.md): cached, throttled GitHub API reads; pool items from the AIDev tables. No repository code is run here."""
import json
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data" / "shadow2"
API = DATA / "api"


TRANSIENT = ("error connecting", "timeout", "timed out", "rate limit", "HTTP 5", "temporarily", "EOF", "reset by peer")


def gh(path, paginate=False, pause=0.25, tries=4):
    """Cached, throttled GitHub read. Only definitive answers are cached (success, or a 404/410 for something that is gone); a transient failure (network, rate limit, 5xx) is retried with back-off and never cached
    (amendment A1 of the pre-registration: the first run cached 711 connection errors as if the pull requests were unobservable)."""
    API.mkdir(parents=True, exist_ok=True)
    key = API / (path.replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "-") + ".json")
    if key.exists():
        cached = json.loads(key.read_text())
        if not (isinstance(cached, dict) and "error" in cached and any(t in cached["error"] for t in TRANSIENT)):
            return cached
    for attempt in range(tries):
        time.sleep(pause * (2 ** attempt))
        try:
            p = subprocess.run(["gh", "api", *(["--paginate"] if paginate else []), path], capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            continue
        if p.returncode == 0:
            try:
                out = json.loads(p.stdout.replace("][", ",") if paginate else p.stdout)
            except ValueError:
                continue
            key.write_text(json.dumps(out))
            return out
        err = p.stderr[:200]
        if "404" in err or "410" in err or "451" in err:
            out = {"error": err}
            key.write_text(json.dumps(out))
            return out
        if not any(t in err for t in TRANSIENT) and "HTTP" in err:   # another definitive HTTP answer (403 for a private or blocked repository)
            out = {"error": err}
            key.write_text(json.dumps(out))
            return out
    return {"error": "transient failure after retries (not cached)"}


def bodies():
    d = pd.read_parquet(ROOT / "data" / "aidev" / "pull_request.parquet", columns=["body", "html_url", "agent", "number"])
    return {r.html_url: {"body": r.body, "agent": r.agent, "number": int(r.number)} for r in d.itertuples() if isinstance(r.body, str)}
