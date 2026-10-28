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


def gh(path, paginate=False, pause=0.25):
    API.mkdir(parents=True, exist_ok=True)
    key = API / (path.replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "-") + ".json")
    if key.exists():
        return json.loads(key.read_text())
    time.sleep(pause)
    p = subprocess.run(["gh", "api", *(["--paginate"] if paginate else []), path], capture_output=True, text=True, timeout=240)
    if p.returncode:
        out = {"error": p.stderr[:200]}
    else:
        try:
            out = json.loads(p.stdout.replace("][", ",") if paginate else p.stdout)
        except ValueError:
            out = {"error": "bad json"}
    key.write_text(json.dumps(out))
    return out


def bodies():
    d = pd.read_parquet(ROOT / "data" / "aidev" / "pull_request.parquet", columns=["body", "html_url", "agent", "number"])
    return {r.html_url: {"body": r.body, "agent": r.agent, "number": int(r.number)} for r in d.itertuples() if isinstance(r.body, str)}
