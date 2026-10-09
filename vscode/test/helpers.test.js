"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");
const { buildArgs, injectCsp, claudeProjectDir, latestSession, STATUS, hookFileContent, statusCodeFromDecision, verifySeal, shellQuote, describeDecision, decisionMarkdown } = require("../helpers");

test("buildArgs defaults are read-only (no tests, no CI)", () => {
  const a = buildArgs({}, "/r");
  assert.deepStrictEqual(a, ["check", "--repo", "/r", "--html", "-"]);
});
test("buildArgs passes tests, python and CI only when enabled", () => {
  const a = buildArgs({ base: "main", runTests: true, python: "/v/bin/python", testCommand: "{py} -m pytest", useCI: true }, "/r");
  assert.ok(a.includes("--run-tests") && a.includes("--python") && a.includes("--ci") && a.includes("--base"));
});
test("python is not passed unless tests run", () => {
  assert.ok(!buildArgs({ python: "/v/bin/python" }, "/r").includes("--python"));
});
test("injectCsp forbids scripts and network", () => {
  const p = injectCsp("<html><head><title>x</title></head></html>");
  assert.ok(p.includes("default-src 'none'") && !p.includes("script-src"));
});
test("claudeProjectDir mangles the path like Claude Code", () => {
  assert.strictEqual(claudeProjectDir("/Users/me/my.repo", "/h"), path.join("/h", ".claude", "projects", "-Users-me-my-repo"));
});
test("latestSession picks the newest jsonl, null when none", () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "am-"));
  assert.strictEqual(latestSession("/x/y", home), null);
  const d = claudeProjectDir("/x/y", home); fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(d, "a.jsonl"), "{}"); fs.utimesSync(path.join(d, "a.jsonl"), 1, 1);
  fs.writeFileSync(path.join(d, "b.jsonl"), "{}");
  assert.strictEqual(latestSession("/x/y", home), path.join(d, "b.jsonl"));
});
test("every exit code has a status", () => { for (const c of [0, 1, 2, 3]) assert.ok(STATUS[c].text); });
test("the real CLI emits a report the extension can display (exit 1 = review required)", () => {
  const root = path.resolve(__dirname, "..", "..");
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), "amr-"));
  execFileSync("python3", [path.join(root, "examples", "make_demo.py"), repo], { stdio: "ignore" });
  let out = "", code = 0;
  try { out = execFileSync("python3", ["-m", "agentmirror", ...buildArgs({}, repo)], { cwd: root, input: "No downstream impact." }).toString(); }
  catch (e) { out = e.stdout.toString(); code = e.status; }
  assert.strictEqual(code, 1);
  assert.ok(out.includes("<html") && out.includes("Review before approving"));
});

test("hook file is valid, never blocks, and matches the shipped example", () => {
  const h = JSON.parse(hookFileContent());
  assert.strictEqual(h.version, 1);
  assert.strictEqual(h.hooks.Stop[0].command, "agentmirror check --hook");
  assert.strictEqual(h.hooks.UserPromptSubmit, undefined, "the experimental chat hook must be off by default");
  const ex = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "examples", "hooks", "agentmirror.json"), "utf8"));
  assert.deepStrictEqual(h, ex);
});
test("decision status maps to status codes and unknown shapes fail closed", () => {
  assert.strictEqual(statusCodeFromDecision({ status: "REVIEW REQUIRED" }), 1);
  assert.strictEqual(statusCodeFromDecision({ status: "INSUFFICIENT EVIDENCE" }), 2);
  assert.strictEqual(statusCodeFromDecision({ status: "NO CONTRADICTION FOUND (scoped, not a safety verdict)" }), 0);
  assert.strictEqual(statusCodeFromDecision({}), 3);
  assert.strictEqual(statusCodeFromDecision(null), 3);
});
test("end to end: the hook command writes files the extension watcher reads", () => {
  const root = path.resolve(__dirname, "..", "..");
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), "amh-"));
  execFileSync("python3", [path.join(root, "examples", "make_demo.py"), repo], { stdio: "ignore" });
  const out = execFileSync("python3", ["-m", "agentmirror", "check", "--hook"], { cwd: root, input: JSON.stringify({ cwd: repo, last_assistant_message: "No downstream impact." }) }).toString();
  assert.ok(JSON.parse(out).systemMessage.includes("REVIEW REQUIRED"));
  const dec = JSON.parse(fs.readFileSync(path.join(repo, ".agentmirror", "last", "decision.json"), "utf8"));
  assert.strictEqual(statusCodeFromDecision(dec), 1);
  assert.ok(fs.readFileSync(path.join(repo, ".agentmirror", "last", "report.html"), "utf8").includes("<html"));
});

test("CSP forbids forms, base-uri, frames, scripts and network", () => {
  const p = injectCsp("<html><head></head></html>");
  for (const d of ["default-src 'none'", "form-action 'none'", "base-uri 'none'", "frame-src 'none'"]) assert.ok(p.includes(d), d);
  assert.ok(!p.includes("script-src") && !p.includes("connect-src"));
});
test("command, python and testCommand cannot be set by a workspace; untrusted workspaces restrict them", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "package.json"), "utf8"));
  const props = pkg.contributes.configuration.properties;
  for (const k of ["agentmirror.command", "agentmirror.python", "agentmirror.testCommand"]) {
    assert.strictEqual(props[k].scope, "machine", k);
    assert.ok(pkg.capabilities.untrustedWorkspaces.restrictedConfigurations.includes(k), k);
  }
});
test("a sealed hook result verifies; a forged or tampered one does not", () => {
  const root = path.resolve(__dirname, "..", "..");
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "amk-"));
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), "amr-"));
  const env = { ...process.env, AGENTMIRROR_HOME: home };
  execFileSync("python3", [path.join(root, "examples", "make_demo.py"), repo], { stdio: "ignore", env });
  execFileSync("python3", ["-m", "agentmirror", "check", "--hook"], { cwd: root, env, input: JSON.stringify({ cwd: repo, last_assistant_message: "No downstream impact." }) });
  const dir = path.join(repo, ".agentmirror", "last");
  const kp = path.join(home, "key");
  assert.ok(verifySeal(dir, kp), "genuine result must verify");
  fs.appendFileSync(path.join(dir, "decision.json"), " ");                       // tamper with the decision
  assert.ok(!verifySeal(dir, kp), "tampered decision must not verify");
  fs.writeFileSync(path.join(dir, "decision.sig"), "0".repeat(64));              // forged signature
  assert.ok(!verifySeal(dir, kp), "forged signature must not verify");
  assert.ok(!verifySeal(path.join(repo, "nonexistent"), kp));
});
test("a repository-written green result without a seal is rejected", () => {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), "amf-"));
  const dir = path.join(repo, ".agentmirror", "last"); fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "report.html"), "<html>all good</html>");
  fs.writeFileSync(path.join(dir, "decision.json"), JSON.stringify({ status: "NO CONTRADICTION FOUND (scoped, not a safety verdict)" }));
  assert.ok(!verifySeal(dir, path.join(repo, "nokey")));
});

test("the hook file uses the full path when given one, quoted if it has spaces", () => {
  assert.strictEqual(JSON.parse(hookFileContent("/opt/anaconda3/bin/agentmirror")).hooks.Stop[0].command, "/opt/anaconda3/bin/agentmirror check --hook");
  assert.strictEqual(JSON.parse(hookFileContent("/Users/me/My Tools/agentmirror")).hooks.Stop[0].command, '"/Users/me/My Tools/agentmirror" check --hook');
  assert.strictEqual(shellQuote("/a/b"), "/a/b");
  assert.ok(shellQuote("/a b/$x").startsWith('"') && shellQuote("/a b/$x").includes("\\$"));
});
test("the doctor command is contributed", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "package.json"), "utf8"));
  assert.ok(pkg.contributes.commands.some((c) => c.command === "agentmirror.doctor"));
  assert.ok(pkg.contributes.commands.some((c) => c.command === "agentmirror.installHook"));
});

test("the extension activates at startup so its result watcher runs without any command", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "package.json"), "utf8"));
  assert.ok(pkg.activationEvents.includes("onStartupFinished"));
});

test("describeDecision summarises counts, unexamined statements and the first claim, and survives odd input", () => {
  const t = describeDecision({ status: "REVIEW REQUIRED", unexamined: 3, findings: [
    { kind: "x", claim: "No downstream impact.", verdict: "CONTRADICTED" }, { kind: "tests_pass", claim: "All tests pass", verdict: "UNKNOWN" },
    { kind: "snapshot", claim: "(tree)", verdict: "UNKNOWN" }] });
  assert.ok(t.includes("1 contradicted") && t.includes("1 unknown") && t.includes("3 statement(s) not examined") && t.includes("No downstream impact"));
  assert.ok(describeDecision(null).includes("unknown status"));
  assert.ok(describeDecision({}).includes("0 contradicted"));
});
test("a notify setting exists with a conservative default", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "package.json"), "utf8"));
  const n = pkg.contributes.configuration.properties["agentmirror.notify"];
  assert.strictEqual(n.default, "review");
  assert.deepStrictEqual(n.enum, ["review", "always", "never"]);
});

test("decisionMarkdown renders the verdict and escapes agent-controlled text (no links, mentions or html)", () => {
  const md = decisionMarkdown({ status: "REVIEW REQUIRED", unexamined: 2, findings: [
    { kind: "x", claim: "![t](http://evil.example) @octocat <img src=x>", verdict: "CONTRADICTED", why: "two modules depend on it" }] });
  assert.ok(md.includes("REVIEW REQUIRED") && md.includes("Contradicted") && md.includes("2 other statement"));
  assert.ok(!/(?<!\\)!\[/.test(md) && !/(?<!\\)\]\(/.test(md) && !/(?<!\\)<img/.test(md) && !/(?<!\\)@octocat/.test(md), md);
  assert.ok(decisionMarkdown(null).includes("No checkable claims"));
});
test("the chat participant is contributed and the engine supports the chat API", () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "package.json"), "utf8"));
  assert.strictEqual(pkg.contributes.chatParticipants[0].name, "agentmirror");
  assert.ok(parseFloat(pkg.engines.vscode.replace("^", "").split(".").slice(0, 2).join(".")) >= 1.95);
});

test("the experimental chat hook is added only when explicitly requested", () => {
  const h = JSON.parse(hookFileContent("agentmirror", true));
  assert.strictEqual(h.hooks.UserPromptSubmit[0].command, "agentmirror prompt-hook");
  assert.ok(h.hooks.Stop);
  const ex = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "..", "examples", "hooks", "agentmirror-with-experimental-chat-hook.json"), "utf8"));
  assert.deepStrictEqual(h, ex);
});
