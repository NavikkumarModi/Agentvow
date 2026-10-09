"use strict";
// Pure helpers (no vscode import) so they can be unit-tested with plain node.
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");

const CSP = "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'; frame-src 'none';\">";

function buildArgs(cfg, repo) {
  const a = ["check", "--repo", repo, "--html", "-"];
  if (cfg.base) a.push("--base", cfg.base);
  if (cfg.runTests) {
    a.push("--run-tests");
    if (cfg.python) a.push("--python", cfg.python);
    if (cfg.testCommand) a.push("--test-cmd", cfg.testCommand);
  }
  if (cfg.useCI) a.push("--ci");
  return a;
}

function injectCsp(page) {
  return page.includes("<head>") ? page.replace("<head>", "<head>" + CSP) : CSP + page;
}

// Claude Code stores sessions at ~/.claude/projects/<cwd with / and . replaced by ->/<id>.jsonl
function claudeProjectDir(workspace, home = os.homedir()) {
  return path.join(home, ".claude", "projects", workspace.replace(/[/.]/g, "-"));
}

function latestSession(workspace, home = os.homedir()) {
  const dir = claudeProjectDir(workspace, home);
  let files;
  try { files = fs.readdirSync(dir).filter((f) => f.endsWith(".jsonl")); } catch (e) { return null; }
  if (!files.length) return null;
  return files.map((f) => ({ f: path.join(dir, f), t: fs.statSync(path.join(dir, f)).mtimeMs })).sort((a, b) => b.t - a.t)[0].f;
}

// The hook seals report.html + decision.json with an HMAC (key kept outside the repo, ~/.agentmirror/key). A repository (or an agent
// working in it) can write these files; only a result sealed by the tool is displayed.
function keyPath() { return path.join(process.env.AGENTMIRROR_HOME || path.join(os.homedir(), ".agentmirror"), "key"); }
function verifySeal(dir, kp = keyPath()) {
  try {
    const page = fs.readFileSync(path.join(dir, "report.html"));
    const dec = fs.readFileSync(path.join(dir, "decision.json"));
    const sig = fs.readFileSync(path.join(dir, "decision.sig"), "utf8").trim();
    const mac = crypto.createHmac("sha256", fs.readFileSync(kp)).update(Buffer.concat([page, Buffer.from([0]), dec])).digest("hex");
    return crypto.timingSafeEqual(Buffer.from(mac), Buffer.from(sig));
  } catch (e) { return false; }
}

// One call that answers: is there a result, is it new (stamp), is it sealed by AgentMirror, and what does it say?
function readResult(dir, kp) {
  let st;
  try { st = fs.lstatSync(path.join(dir, "decision.sig")); } catch (e) { return null; }
  for (const f of ["decision.sig", "decision.json", "report.html"]) {   // regular, bounded files only: no symlinks to elsewhere, no huge reads
    try { const x = fs.lstatSync(path.join(dir, f)); if (!x.isFile() || x.size > 20e6) return { stamp: `${st.mtimeMs}:${st.size}`, valid: false }; } catch (e) { return f === "decision.sig" ? null : { stamp: `${st.mtimeMs}:${st.size}`, valid: false }; }
  }   // the seal is written last: no seal, no (complete) result
  const stamp = `${st.mtimeMs}:${st.size}`;
  if (!verifySeal(dir, kp)) return { stamp, valid: false };
  try {
    return { stamp, valid: true, dec: JSON.parse(fs.readFileSync(path.join(dir, "decision.json"), "utf8")), page: fs.readFileSync(path.join(dir, "report.html"), "utf8") };
  } catch (e) { return { stamp, valid: false, error: String(e) }; }
}

const STATUS = {
  4: { text: "$(shield) AgentMirror: unverified result ignored", tip: "A result file in this repository was not sealed by AgentMirror (it may have been written by the repository or an agent), so it is not shown." },
  0: { text: "$(check) AgentMirror: no contradiction (scoped)", tip: "No contradiction found in what could be checked. Not a safety verdict." },
  1: { text: "$(error) AgentMirror: review required", tip: "Something the agent said does not match the repository." },
  2: { text: "$(question) AgentMirror: not enough evidence", tip: "Treat the agent's claims as unverified." },
  3: { text: "$(warning) AgentMirror: tool error", tip: "The check could not run. Nothing was verified." },
};

function shellQuote(p) { return /[^A-Za-z0-9_\/.@:+-]/.test(p) ? `"${p.replace(/(["\\$`])/g, "\\$1")}"` : p; }

// `command` is the agentmirror executable. Hooks run with the AGENT's PATH, which often lacks conda/venv/pyenv directories, so the
// installer writes the full path when it can find one.
function hookFileContent(command = "agentmirror", withChatHook = false) {
  const c = shellQuote(command);
  const hooks = { Stop: [{ type: "command", command: `${c} check --hook`, timeout: 60 }] };   // judges the final answer, writes the sealed result
  // EXPERIMENTAL, off by default: hands the last verdict to the agent as context on the next prompt. In one live session the first
  // delivery coincided with a Copilot chat that never got a model response (cause unproven), so it is never added unless asked for.
  if (withChatHook) hooks.UserPromptSubmit = [{ type: "command", command: `${c} prompt-hook`, timeout: 20 }];
  return JSON.stringify({ version: 1, hooks }, null, 2) + "\n";
}

// decision.json (written by `agentmirror check --hook`) -> exit-code-like status for the status bar
function statusCodeFromDecision(dec) {
  const s = (dec && dec.status) || "";
  if (s.startsWith("REVIEW")) return 1;
  if (s.startsWith("INSUFF")) return 2;
  if (s.startsWith("NO CONTRADICTION")) return 0;
  return 3;
}

function describeDecision(dec) {
  const f = ((dec && dec.findings) || []).filter((x) => x.kind !== "snapshot");
  const n = (vs) => f.filter((x) => vs.includes(x.verdict)).length;
  const first = f[0] ? ` First: ${String(f[0].claim).slice(0, 80)}` : "";
  const un = dec && dec.unexamined ? `; ${dec.unexamined} statement(s) not examined` : "";
  return `${(dec && dec.status) || "unknown status"}. ${n(["CONTRADICTED"])} contradicted, ${n(["SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED"])} not contradicted or supported, ${n(["UNKNOWN"])} unknown${un}.${first}`;
}

function decisionMarkdown(dec) {
  const esc = (x) => String(x).replace(/[\\`*_{}\[\]()#+!|<>~&@:]/g, "\\$&").replace(/\s+/g, " ").slice(0, 200);
  const f = ((dec && dec.findings) || []).filter((x) => x.kind !== "snapshot");
  const icon = { CONTRADICTED: "✗", SUPPORTED_BY_PRIOR_EVIDENCE: "✓", NOT_CONTRADICTED: "~", UNKNOWN: "?" };
  const label = { CONTRADICTED: "Contradicted", SUPPORTED_BY_PRIOR_EVIDENCE: "Supported", NOT_CONTRADICTED: "Not contradicted (scoped)", UNKNOWN: "Unknown" };
  const lines = [`### AgentMirror: ${esc((dec && dec.status) || "no result")}`, ""];
  if (!f.length) lines.push("No checkable claims were found, so nothing was verified.");
  for (const x of f) lines.push(`- ${icon[x.verdict] || "?"} **${label[x.verdict] || "Unknown"}** — ${esc(x.claim)}`, `  - ${esc(x.why)}`);
  if (dec && dec.unexamined) lines.push("", `_${dec.unexamined} other statement\\(s\\) in the answer were not examined._`);
  lines.push("", "_AgentMirror informs your decision; it does not approve, reject or merge anything._");
  return lines.join("\n");
}

module.exports = { decisionMarkdown, readResult, describeDecision, shellQuote, verifySeal, keyPath, hookFileContent, statusCodeFromDecision, buildArgs, injectCsp, claudeProjectDir, latestSession, STATUS, CSP };
