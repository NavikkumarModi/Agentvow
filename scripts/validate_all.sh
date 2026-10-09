#!/usr/bin/env bash
# One-command validation of AgentMirror: tests, consistency, secret scan, wheel + clean-room install, extension package, leaks.
# Usage: scripts/validate_all.sh        Exit code 0 only if every check passes. Builds release artifacts into dist/.
cd "$(dirname "$0")/.." || exit 2
ROOT="$PWD"; FAIL=0; N=0
TMP="$(mktemp -d /tmp/am_validate.XXXXXX)"; export AGENTMIRROR_HOME="$TMP/home"; mkdir -p "$AGENTMIRROR_HOME"
pass() { N=$((N+1)); echo "  PASS $*"; }
fail() { N=$((N+1)); FAIL=$((FAIL+1)); echo "  FAIL $*"; }
check() { local name="$1"; shift; if "$@" >"$TMP/out" 2>&1; then pass "$name"; else fail "$name"; tail -6 "$TMP/out" | sed 's/^/         /'; fi; }
section() { echo; echo "== $*"; }

section "1. Python tests"
python3 -m unittest discover -s tests >"$TMP/py.out" 2>&1; PYRC=$?
PYN=$(grep -E '^Ran [0-9]+ tests' "$TMP/py.out" | awk '{print $2}')
[ $PYRC -eq 0 ] && pass "python tests ($PYN)" || { fail "python tests"; tail -15 "$TMP/py.out" | sed 's/^/         /'; }

section "2. Node tests (helpers + the real extension.js against a stubbed VS Code)"
node --test vscode/test/extension.test.js vscode/test/helpers.test.js >"$TMP/node.out" 2>&1; NRC=$?
NODEN=$(grep -E '^ℹ tests ' "$TMP/node.out" | awk '{print $3}')
[ $NRC -eq 0 ] && pass "node tests ($NODEN)" || { fail "node tests"; grep -E '✖|Error' "$TMP/node.out" | head -8 | sed 's/^/         /'; }

section "3. Static validity"
check "all python compiles" python3 -m compileall -q agentmirror scripts examples tests
check "extension javascript parses" bash -c 'node --check vscode/extension.js && node --check vscode/helpers.js'
check "yaml files parse (action + workflow)" python3 -c "import yaml;[yaml.safe_load(open(f)) for f in ('action.yml','examples/workflows/agentmirror.yml')]"
check "json files parse (hooks examples, extension manifest)" python3 -c "import json,glob;[json.load(open(f)) for f in glob.glob('examples/hooks/*.json')+['vscode/package.json']]"
check "shipped hook examples never block and Stop is present" python3 - <<'EOF'
import json,glob
for f in glob.glob('examples/hooks/*.json'):
    h=json.load(open(f))['hooks']
    assert 'Stop' in h and 'check --hook' in h['Stop'][0]['command'], f
    assert 'decision' not in json.dumps(h), f
d=json.load(open('examples/hooks/agentmirror.json'))['hooks']; assert 'UserPromptSubmit' not in d, 'experimental chat hook must be off by default'
EOF

section "4. Version and documentation consistency"
V1=$(python3 -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
V2=$(python3 -c "import re;print(re.search(r'__version__ = \"(.*?)\"',open('agentmirror/__init__.py').read()).group(1))")
V3=$(python3 -c "import json;print(json.load(open('vscode/package.json'))['version'])")
[ "$V1" = "$V2" ] && [ "$V2" = "$V3" ] && pass "versions agree ($V1)" || fail "version mismatch: pyproject=$V1 __init__=$V2 extension=$V3"
grep -q "$PYN Python tests" README.md && grep -q "$NODEN node tests" README.md && pass "README test counts match reality ($PYN Python, $NODEN node)" || fail "README test counts are stale (actual: $PYN Python, $NODEN node)"
grep -q "agentmirror-$V1.vsix" README.md && pass "README names the current extension package" || fail "README does not mention agentmirror-$V1.vsix"
for f in LICENSE README.md docs/SECURITY_MODEL.md docs/LIVE_TESTING.md CLAUDE.md; do [ -s "$f" ] && pass "$f exists" || fail "$f missing or empty"; done

section "5. Secret scan (source, docs, examples; not data/)"
if grep -rIEn --exclude-dir=data --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=out --exclude='*.vsix' \
    -e 'gh[pousr]_[A-Za-z0-9]{30,}' -e 'github_pat_[A-Za-z0-9_]{30,}' -e 'sk-[A-Za-z0-9]{32,}' -e 'AKIA[0-9A-Z]{16}' \
    -e '-----BEGIN (RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----' . >"$TMP/secrets" 2>&1; then fail "possible secrets found"; head -5 "$TMP/secrets" | sed 's/^/         /'; else pass "no secret-looking strings"; fi

section "6. Wheel build and CLEAN-ROOM install (nothing imported from the source tree)"
mkdir -p dist
rm -f dist/agentmirror-*.whl
python3 -m pip wheel . --no-deps -q -w dist >"$TMP/wheel.out" 2>&1 && pass "wheel builds" || { fail "wheel build"; tail -6 "$TMP/wheel.out" | sed 's/^/         /'; }
WHL=$(ls dist/agentmirror-*.whl 2>/dev/null | head -1)
if [ -n "$WHL" ]; then
  LISTING=$(python3 -c "import zipfile,sys;print('\n'.join(zipfile.ZipFile(sys.argv[1]).namelist()))" "$WHL")
  echo "$LISTING" | grep -q "^agentmirror/cli.py" && pass "wheel contains the package" || fail "wheel is missing agentmirror/cli.py"
  echo "$LISTING" | grep -E "^(tests|data|docs|scripts|examples|vscode)/" >/dev/null && fail "wheel contains non-package files" || pass "wheel contains only the package"
  python3 -m venv "$TMP/venv" && "$TMP/venv/bin/pip" install -q "$WHL" >"$TMP/install.out" 2>&1 && pass "wheel installs into a fresh venv" || { fail "wheel install"; tail -5 "$TMP/install.out" | sed 's/^/         /'; }
  AM="$TMP/venv/bin/agentmirror"
  cd "$TMP" || exit 2
  "$AM" --version | grep -q "agentmirror $V1" && pass "installed CLI reports $V1" || fail "installed CLI version"
  python3 "$ROOT/examples/make_demo.py" "$TMP/repo" >/dev/null
  echo 'I raised retries. There is no downstream impact. All 3 tests pass.' | "$AM" check --repo "$TMP/repo" >"$TMP/c1.txt" 2>&1; RC=$?
  [ $RC -eq 1 ] && grep -q CONTRADICTED "$TMP/c1.txt" && pass "installed CLI: contradiction detected (exit 1)" || fail "installed CLI check (rc=$RC)"
  echo 'Refactored things in the code.' | "$AM" check --repo "$TMP/repo" >/dev/null 2>&1; [ $? -eq 2 ] && pass "no checkable claim -> insufficient evidence (exit 2)" || fail "exit code for insufficient evidence"
  echo 'No downstream impact.' | "$AM" check --repo "$TMP/repo" --html "$TMP/r.html" --markdown "$TMP/r.md" >/dev/null 2>&1
  grep -qE '<script|https?://|src=' "$TMP/r.html" && fail "html report is not self-contained" || pass "html report is self-contained"
  grep -q "agentmirror-report" "$TMP/r.md" && pass "markdown summary written" || fail "markdown summary"
  echo '{"sessionId":"s","cwd":"'"$TMP/repo"'","last_assistant_message":"There is no downstream impact."}' | "$AM" check --hook >"$TMP/h.json" 2>&1
  python3 -c "import json;o=json.load(open('$TMP/h.json'));assert 'REVIEW REQUIRED' in o['systemMessage'] and 'decision' not in o" && pass "hook informs and never blocks" || fail "hook output"
  echo '{"cwd":"'"$TMP/repo"'"}' | "$AM" prompt-hook | python3 -c "import sys,json;o=json.load(sys.stdin);assert 'additionalContext' in o" && pass "prompt-hook delivers the sealed verdict" || fail "prompt-hook"
  echo '{"cwd":"'"$TMP/repo"'"}' | "$AM" prompt-hook | grep -q '^{}$' && pass "prompt-hook delivers once" || fail "prompt-hook repeated a delivery"
  "$AM" agent-instructions --write "$TMP/repo/.github/copilot-instructions.md" >/dev/null && grep -q "agentmirror:begin" "$TMP/repo/.github/copilot-instructions.md" && pass "agent-instructions writes its block" || fail "agent-instructions"
  "$AM" demo --path "$TMP/demo" | grep -q "REVIEW REQUIRED" && pass "installed CLI: demo produces the red verdict" || fail "demo"
  "$AM" doctor --repo "$TMP/repo" >"$TMP/doctor.txt" 2>&1; [ $? -eq 0 ] && pass "doctor passes (both payload styles end to end)" || { fail "doctor"; grep -E '^✗' "$TMP/doctor.txt" | head -4 | sed 's/^/         /'; }
  cd "$ROOT" || exit 2
fi

section "7. VS Code extension package"
( cd vscode && rm -f agentmirror-*.vsix && npx --yes @vscode/vsce package --allow-missing-repository --no-dependencies >"$TMP/vsce.out" 2>&1 )
VSIX=$(ls vscode/agentmirror-*.vsix 2>/dev/null | head -1)
if [ -n "$VSIX" ]; then
  mv "$VSIX" "dist/agentmirror-$V3.vsix"; VSIX="dist/agentmirror-$V3.vsix"
  L=$(python3 -c "import zipfile,sys;print('\n'.join(zipfile.ZipFile(sys.argv[1]).namelist()))" "$VSIX")
  for f in extension/extension.js extension/helpers.js extension/package.json; do echo "$L" | grep -q "^$f$" && pass "vsix contains $f" || fail "vsix missing $f"; done
  echo "$L" | grep -qE "extension/(test|node_modules)/" && fail "vsix contains tests or node_modules" || pass "vsix contains no tests or node_modules"
  [ "$(stat -f %z "$VSIX" 2>/dev/null || stat -c %s "$VSIX")" -lt 200000 ] && pass "vsix is small" || fail "vsix unexpectedly large"
else fail "vsix did not build"; tail -5 "$TMP/vsce.out" | sed 's/^/         /'; fi
ls dist/*.vsix 2>/dev/null | grep -v "agentmirror-$V3.vsix" | while read -r old; do rm -f "$old"; done

section "8. Leaks"
LEFT=$(ls /private/tmp 2>/dev/null | grep -v "^$(basename "$TMP")$" | grep -cE '^(am[a-z0-9_]{6,}|pip-unpack|am_e2e|amx)')
[ "$LEFT" -eq 0 ] && pass "no leftover temp directories" || fail "$LEFT leftover temp directories in /private/tmp"
STRAY=$(pgrep -fl "gpg-agent --homedir $ROOT|sleep 31337" | wc -l | tr -d ' ')
[ "$STRAY" -eq 0 ] && pass "no stray processes" || fail "$STRAY stray processes"
echo "  info free disk: $(df -h "$ROOT" | tail -1 | awk '{print $4}')"

rm -rf "$TMP"
echo; echo "=================================================="
if [ $FAIL -eq 0 ]; then echo "ALL $N CHECKS PASSED  (python $PYN, node $NODEN; artifacts in dist/)"; else echo "$FAIL OF $N CHECKS FAILED"; fi
exit $((FAIL>0))
