"""What to do about a replay that did not reproduce or could not run. Pure text from what the replay already recorded (a result and its summary line); no model, no guessing about the
code: each message names the thing that was missing, which context lacked it, and a next step a person can take. A pass produces nothing."""
import os
import re

_MISSING = re.compile(r"missing dependency in Agentvow's environment: ([\w.,\- ]+?)(?: \(|$)")
_CRED = re.compile(r"\b([A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)[A-Z0-9_]*)\b")
_CRED_WORDS = re.compile(r"not set|missing|required|skipped|unset|not found|no .*credential", re.I)


def _limit_mb() -> int:
    from . import envsetup
    return int(envsetup.MAX_VENV / 1024**2)


def classify(ctx: dict) -> tuple:
    """-> (kind, detail) for one non-passing context dict {name, result, summary, counts}."""
    res, s = str(ctx.get("result", "")), str(ctx.get("summary", ""))
    counts = ctx.get("counts") or {}
    if res == "not built" or "could not be built" in s:
        for key, kind in (("too heavy", "too_heavy"), ("disk low", "disk_low"), ("timeout", "build_timeout"), ("shadowing", "shadowing"), ("too large", "project_too_large")):
            if key in s:
                return kind, ""
        return "not_built", ""
    m = _MISSING.search(s)
    if m:
        return "missing_dependency", ", ".join(x.strip() for x in m.group(1).split(",") if x.strip())
    c = _CRED.search(s)
    if c and _CRED_WORDS.search(s):
        return "credential", c.group(1)
    if s.startswith("timeout after"):
        return "test_timeout", s
    if res == "fail":
        return "test_failure", ""
    if not any(counts.get(k) for k in ("passed", "failed", "errors")) and re.search(r"no tests ran|collected 0|no tests collected|exit 5", s):
        return "no_tests", ""
    if "isolation failure" in s or "declared prepare" in s:
        return "refused", s
    return "other", s


def step(ctx: dict, own: str = "", other: dict | None = None, ignored: list | None = None) -> dict | None:
    """One plain-language next step for a non-passing context, or None when it passed."""
    if str(ctx.get("result")) == "pass":
        return None
    name = ctx.get("name", "a context")
    if ctx.get("dropped_pins"):
        pins = ", ".join(ctx["dropped_pins"][:3])
        return {"context": name, "kind": "uninstallable_pin", "text": (f"A pinned package could not be installed on this platform ({pins}: pip found no distribution for this operating system or Python), so the replay ran without it. "
                                                                          "If the tests need it, the failure is that gap and not the change: replay on the platform the capture came from, or check whether the tests really need it.")}
    kind, detail = classify(ctx)
    captured = "captured" in name
    recipe = "recipe" in name
    if kind == "missing_dependency":
        pkgs = detail
        mods = [x for x in (p.strip() for p in pkgs.split(",")) if x]
        if own and any(m.replace("_", "-").lower() == own.replace("_", "-").lower() for m in mods):
            t = (f"`{own}` is this project's own package. The replay could not import it from the repository (for example the package is not at the repository root or under src/). "
                 "Capture removes the project's own distribution on purpose, so check the project layout rather than installing it.")
        elif captured:
            t = (f"The captured packages do not include {pkgs}. The agent's environment may have had it from a place a pip freeze does not list (an editable or direct install, a system package, "
                 "another interpreter). Run `agentvow capture --python <the interpreter the agent used>` right after the agent's tests, or check which Python the agent ran.")
        elif recipe:
            t = f"The environment built from the agent's declared recipe did not provide {pkgs}: the recipe does not install it, or a step failed. The agent's success may have depended on something it did not declare."
        else:
            t = (f"The environment built from the repository's own files (setup files, the CI workflow's install steps, Dockerfiles, requirements files) did not provide {pkgs}: "
                 "either none of those files installs it, or an install step failed (see the notes). If the project needs it, declare it "
                 "(a requirements file or the CI install step); until then a fresh checkout may not reproduce this result.")
            if ctx.get("setup_notes"):
                t += " An install step did fail here: " + "; ".join(ctx["setup_notes"][:2]) + "."
        if other is not None and str(other.get("result")) == "pass":
            t += " The other context reproduced the result, so the missing package is a likely difference between the two (versions and install order can differ too)."
        return {"context": name, "kind": kind, "text": t}
    if kind == "credential":
        return {"context": name, "kind": kind, "text": (f"The tests need {detail}, which no replay supplies (Agentvow never passes secrets). This result cannot be reproduced here: "
                                                       "run those tests yourself with the credential, or ask the agent which tests it ran without it.")}
    if kind in ("too_heavy", "disk_low", "build_timeout", "shadowing", "project_too_large", "not_built"):
        why = {"too_heavy": f"the install grew past the size limit ({_limit_mb()} MB). Raise it with AGENTVOW_MAX_ENV_MB (for example 3072) if the project legitimately needs that much",
               "disk_low": "free disk space was below the safety floor. Free space and run it again",
               "build_timeout": "the install did not finish within the time limit. Run it again, or build the environment by hand and pass --python",
               "shadowing": "a setup step would install a package with the project's own name, which could replace the code under test, so it was refused",
               "project_too_large": "the project is too large to copy into the replay's private area",
               "not_built": "the install failed; see the summary above for the package pip stopped on"}[kind]
        return {"context": name, "kind": kind, "text": f"No tests ran in this context: {why}. This says nothing about the agent's claim."}
    if kind == "test_timeout":
        return {"context": name, "kind": kind, "text": f"The tests did not finish in time ({detail}). Raise --test-timeout, or run a narrower command (the claimed test files)."}
    if kind == "no_tests":
        return {"context": name, "kind": kind, "text": "The command ran no tests. Check that it points at test files the project's test runner collects (the pack's receipt shows the command)."}
    if kind == "test_failure":
        c = ctx.get("counts") or {}
        n = c.get("failed", 0) + c.get("errors", 0)
        t = (f"The tests ran and {str(n) + ' failed or errored' if n else 'did not pass'}. That is a test result, but a replay can also fail for lack of files or settings it does not have "
             "(see the not-reproduced list in item 4): compare it with what the agent claimed, and with the other context.")
        if ignored:
            t += (f" One caution: git-ignored files exist in the agent's working tree ({', '.join(ignored[:3])}{', ...' if len(ignored) > 3 else ''}) and are not part of the replay; "
                  "if a failing test reads one of them (a generated fixture, a local data file), the failure is the replay lacking it.")
        return {"context": name, "kind": kind, "text": t}
    if kind == "refused":
        return {"context": name, "kind": kind, "text": f"The replay refused to run this ({detail[:120]}); the tool fails closed rather than guess."}
    return {"context": name, "kind": kind, "text": f"Not reproduced ({str(ctx.get('result'))}): {detail[:140] or 'no detail recorded'}."}


def next_steps(contexts: list, own: str = "", ignored: list | None = None) -> list:
    out = []
    for i, c in enumerate(contexts):
        other = contexts[1 - i] if len(contexts) == 2 else None
        s = step(c, own, other, ignored)
        if s:
            out.append(s)
    return out
