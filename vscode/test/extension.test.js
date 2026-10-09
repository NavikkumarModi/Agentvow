"use strict";
// Loads the REAL extension.js against a stubbed `vscode` module and drives it with REAL hook output (agentvow check --hook).
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const Module = require("module");
const { execFileSync } = require("child_process");

const ROOT = path.resolve(__dirname, "..", "..");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(fn, ms = 6000) { const t = Date.now(); while (Date.now() - t < ms) { if (fn()) return true; await sleep(100); } return false; }

function makeStub(folder, settings) {
  const rec = { participant: null, messages: [], status: { text: "", tooltip: "", shown: false }, log: [], panels: 0, commands: {}, executed: [] };
  const stub = {
    workspace: { workspaceFolders: [{ uri: { fsPath: folder } }], isTrusted: true,
      getConfiguration: () => ({ get: (k) => settings[k] }),
      createFileSystemWatcher: () => ({ onDidChange() {}, onDidCreate() {}, dispose() {} }) },
    RelativePattern: class { constructor(f, p) { this.f = f; this.p = p; } },
    window: {
      createStatusBarItem: () => ({ set text(v) { rec.status.text = v; }, get text() { return rec.status.text; }, set tooltip(v) { rec.status.tooltip = v; },
        set command(v) {}, show() { rec.status.shown = true; }, dispose() {} }),
      showInformationMessage: (m, ...b) => { rec.messages.push({ kind: "info", m }); return Promise.resolve(undefined); },
      showWarningMessage: (m, ...b) => { rec.messages.push({ kind: "warning", m }); return Promise.resolve(undefined); },
      showErrorMessage: () => Promise.resolve(undefined),
      createOutputChannel: () => ({ appendLine: (l) => rec.log.push(l), show() {}, clear() {} }),
      createWebviewPanel: () => { rec.panels++; return { webview: {}, reveal() {}, onDidDispose() {} }; },
      withProgress: () => Promise.resolve(), showInputBox: () => Promise.resolve(undefined), showQuickPick: (items) => Promise.resolve(items[1]), activeTextEditor: undefined },
    chat: { createChatParticipant: (id, handler) => { rec.participant = { id, handler }; return { dispose() {} }; } },
    commands: { registerCommand: (id, fn) => { rec.commands[id] = fn; return { dispose() {} }; }, executeCommand: (id) => { rec.executed.push(id); return Promise.resolve(); } },
    Uri: { file: (p) => p },
    StatusBarAlignment: { Left: 1 }, ViewColumn: { Beside: 2 }, ProgressLocation: { Window: 10 }, env: { clipboard: { readText: () => Promise.resolve(""), writeText: (t) => { rec.clip = t; return Promise.resolve(); } } },
  };
  return { stub, rec };
}

function loadExtension(stub) {
  const orig = Module._load;
  Module._load = function (request, ...rest) { return request === "vscode" ? stub : orig.call(this, request, ...rest); };
  try { delete require.cache[require.resolve("../extension")]; return require("../extension"); } finally { Module._load = orig; }
}

function setup(settings) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "amx-"));
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), "amxr-"));
  process.env.AGENTVOW_HOME = home;
  process.env.AGENTVOW_POLL_MS = "150";
  execFileSync("python3", [path.join(ROOT, "examples", "make_demo.py"), repo], { stdio: "ignore", env: { ...process.env } });
  const { stub, rec } = makeStub(repo, settings);
  const ext = loadExtension(stub);
  const ctx = { subscriptions: [] };
  const hook = (message) => execFileSync("python3", ["-m", "agentvow", "check", "--hook"], { cwd: ROOT, env: { ...process.env },
    input: JSON.stringify({ cwd: repo, last_assistant_message: message }) });
  return { repo, ext, ctx, rec, hook, stop: () => ctx.subscriptions.forEach((d) => d.dispose && d.dispose()) };
}

test("a new sealed result raises a warning notification and sets the status bar (REVIEW REQUIRED)", async () => {
  const t = setup({ notify: "always", autoOpen: false });
  t.ext.activate(t.ctx);
  await sleep(300);
  assert.strictEqual(t.rec.messages.length, 0, "nothing to show before any agent turn");
  t.hook("There is no downstream impact.");
  assert.ok(await until(() => t.rec.messages.length > 0), "no notification was shown for a new result");
  assert.strictEqual(t.rec.messages[0].kind, "warning");
  assert.ok(t.rec.messages[0].m.includes("REVIEW REQUIRED"), t.rec.messages[0].m);
  assert.ok(t.rec.status.text.includes("review required") && t.rec.status.shown, t.rec.status.text);
  assert.ok(t.rec.log.some((l) => l.includes("NEW result")), "the log channel must record the detection");
  t.stop();
});

test("with notify=always an INSUFFICIENT result also notifies (information), and notify=never stays silent", async () => {
  let t = setup({ notify: "always", autoOpen: false });
  t.ext.activate(t.ctx);
  t.hook("Refactored a few things in the code.");
  assert.ok(await until(() => t.rec.messages.length > 0));
  assert.strictEqual(t.rec.messages[0].kind, "info");
  assert.ok(t.rec.status.text.includes("not enough evidence"), t.rec.status.text);
  t.stop();
  t = setup({ notify: "never", autoOpen: false });
  t.ext.activate(t.ctx);
  t.hook("There is no downstream impact.");
  assert.ok(await until(() => t.rec.status.text.includes("review required")));
  assert.strictEqual(t.rec.messages.length, 0, "notify=never must not show a toast");
  t.stop();
});

test("notify=review notifies only for contradicted claims", async () => {
  const t = setup({ notify: "review", autoOpen: false });
  t.ext.activate(t.ctx);
  t.hook("Refactored a few things in the code.");
  assert.ok(await until(() => t.rec.status.text.includes("not enough evidence")));
  assert.strictEqual(t.rec.messages.length, 0);
  fs.appendFileSync(path.join(t.repo, "payments", "retry.py"), "# changed in the second turn\n");   // changes are counted per turn
  t.hook("There is no downstream impact.");
  assert.ok(await until(() => t.rec.messages.length > 0));
  assert.strictEqual(t.rec.messages[0].kind, "warning");
  t.stop();
});

test("a result that already exists when the window opens updates the status bar but shows no toast", async () => {
  const t = setup({ notify: "always", autoOpen: false });
  t.hook("There is no downstream impact.");                  // written before activation
  t.ext.activate(t.ctx);
  assert.ok(await until(() => t.rec.status.text.includes("review required")), t.rec.status.text);
  await sleep(500);
  assert.strictEqual(t.rec.messages.length, 0, "old news must not toast");
  t.stop();
});

test("a result that was not sealed by Agentvow is ignored and flagged, never trusted", async () => {
  const t = setup({ notify: "always", autoOpen: false });
  t.ext.activate(t.ctx);
  t.hook("There is no downstream impact.");
  assert.ok(await until(() => t.rec.messages.length > 0));
  const n = t.rec.messages.length;
  const dir = path.join(t.repo, ".agentvow", "last");
  fs.writeFileSync(path.join(dir, "decision.json"), JSON.stringify({ status: "NO CONTRADICTION FOUND (scoped, not a safety verdict)", findings: [] }));  // forged green
  fs.writeFileSync(path.join(dir, "decision.sig"), "0".repeat(64));
  assert.ok(await until(() => t.rec.status.text.includes("unverified")), t.rec.status.text);
  assert.strictEqual(t.rec.messages.length, n, "a forged result must not produce a verdict toast");
  assert.ok(!t.rec.status.text.includes("no contradiction"));
  t.stop();
});

test("the extension survives a workspace with no result and no key (fails quiet, logs it)", async () => {
  const t = setup({ notify: "always", autoOpen: false });
  t.ext.activate(t.ctx);
  await sleep(500);
  assert.strictEqual(t.rec.messages.length, 0);
  assert.ok(t.rec.log.some((l) => l.includes("activated")));
  t.stop();
});

test("@agentvow shows the sealed verdict in the chat (deterministic text + a button), and refuses unsealed results", async () => {
  const t = setup({ notify: "never", autoOpen: false });
  t.ext.activate(t.ctx);
  assert.ok(t.rec.participant && t.rec.participant.id === "agentvow.chat", "participant not registered");
  const reply = { md: [], buttons: [] };
  const stream = { markdown: (m) => reply.md.push(m), button: (b) => reply.buttons.push(b) };
  await t.rec.participant.handler({}, {}, stream);
  assert.ok(reply.md.join("").includes("No Agentvow result"), "no result yet: say so");
  t.hook("There is no downstream impact.");
  reply.md.length = 0; reply.buttons.length = 0;
  await t.rec.participant.handler({}, {}, stream);
  assert.ok(reply.md.join("").includes("REVIEW REQUIRED") && reply.md.join("").includes("Contradicted"), reply.md.join(""));
  assert.strictEqual(reply.buttons[0].command, "agentvow.showReport");
  const dir = path.join(t.repo, ".agentvow", "last");
  fs.writeFileSync(path.join(dir, "decision.sig"), "0".repeat(64));                // forge
  reply.md.length = 0;
  await t.rec.participant.handler({}, {}, stream);
  assert.ok(reply.md.join("").includes("not sealed"), reply.md.join(""));
  assert.ok(!reply.md.join("").includes("REVIEW REQUIRED"));
  t.stop();
});

test("the demo command builds the demo, shows the red verdict and offers a Copilot prompt", async () => {
  const settings = { notify: "never", autoOpen: false };
  const t = setup(settings);
  const gs = fs.mkdtempSync(path.join(os.tmpdir(), "amxg-"));
  t.ctx.globalStorageUri = { fsPath: gs };
  const bin = path.join(gs, "agentvow");
  fs.writeFileSync(bin, `#!/bin/sh\nPYTHONPATH=${ROOT} exec python3 -m agentvow.cli "$@"\n`, { mode: 0o755 });
  settings.command = bin;
  t.ext.activate(t.ctx);
  t.rec.commands["agentvow.tryDemo"]();
  assert.ok(await until(() => t.rec.messages.some((m) => m.m.includes("Agentvow demo")), 20000), "no demo notification: " + t.rec.log.join("|"));
  assert.ok(t.rec.messages.find((m) => m.m.includes("Agentvow demo")).m.includes("REVIEW REQUIRED"));
  assert.ok(t.rec.status.text.includes("review required"), t.rec.status.text);
  assert.ok(t.rec.panels >= 1);
  t.stop();
});

test("the status bar item is shown at once and opens a menu that reaches the demo (click-only access)", async () => {
  const t = setup({ notify: "never", autoOpen: false });
  t.ext.activate(t.ctx);
  assert.ok(t.rec.status.shown && t.rec.status.text.includes("Agentvow"));
  await t.rec.commands["agentvow.menu"]();
  assert.deepStrictEqual(t.rec.executed, ["agentvow.tryDemo"]);
  t.stop();
});
