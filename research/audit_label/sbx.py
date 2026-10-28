"""Run one command inside Agentvow's sandbox for the audit labellers (docs/research/AUDIT_STUDY_PREREG.md, amendment A1, point 4): macOS sandbox-exec / Linux bubblewrap, via the product's own runner.
The directory is a throwaway checkout of a public repository and is the only writable place (plus a scratch HOME/TMPDIR); the network is denied unless --network (for installs). Never run repository code any other way.
Usage: python3 research/audit_label/sbx.py --dir CHECKOUT [--network] [--timeout 600] -- COMMAND ARGS...   (exit status = the command's; output is printed, cut to 20000 characters)"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from agentvow import runner  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--network", action="store_true")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        print("no command", file=sys.stderr); return 2
    why = runner.sandbox_problem()
    if why:
        print(f"refused: no working sandbox ({why})", file=sys.stderr); return 3
    d = Path(a.dir).resolve()
    if not d.is_dir() or d == Path.home() or str(d) in ("/", str(ROOT)):
        print("refused: --dir must be a throwaway checkout", file=sys.stderr); return 3
    scratch = Path(tempfile.mkdtemp(prefix="lab", dir=runner.scratch_base())).resolve()
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(scratch), "TMPDIR": str(scratch), "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1", "CI": "1"}
    try:
        p = subprocess.run(runner.wrap(cmd, d, scratch, network=a.network, writable=[d, scratch], env=env), cwd=d, env=env, capture_output=True, text=True, timeout=a.timeout)
        out = (p.stdout + p.stderr)
        print(out[:20000] + ("\n...[cut]" if len(out) > 20000 else ""))
        return p.returncode
    except subprocess.TimeoutExpired:
        print(f"timeout after {a.timeout}s", file=sys.stderr); return 124
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
