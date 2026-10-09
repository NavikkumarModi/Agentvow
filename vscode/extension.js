"use strict";
const vscode = require("vscode");
const cp = require("child_process");
const fs = require("fs");
const path = require("path");
const { buildArgs, injectCsp, latestSession, STATUS, hookFileContent, statusCodeFromDecision, verifySeal, describeDecision, readResult, decisionMarkdown } = require("./helpers");

let panel, lastPage = null, statusItem, logChannel;

function log(msg) {
  if (!logChannel) logChannel = vscode.window.createOutputChannel("AgentMirror");
  logChannel.appendLine(`${new Date().toISOString()}  ${msg}`);
}

function config() {
  const c = vscode.workspace.getConfiguration("agentmirror");
  return { command: c.get("command") || "agentmirror", base: c.get("base"), runTests: c.get("runTests"),
           python: c.get("python"), testCommand: c.get("testCommand"), useCI: c.get("useCI") };
}

function workspaceRoot() {
  const f = vscode.workspace.workspaceFolders;
  return f && f.length ? f[0].uri.fsPath : null;
}

function show(page) {
  lastPage = injectCsp(page);
  if (!panel) {
    panel = vscode.window.createWebviewPanel("agentmirrorReport", "AgentMirror", vscode.ViewColumn.Beside,
      { enableScripts: false, retainContextWhenHidden: true });
    panel.onDidDispose(() => { panel = undefined; });
  }
  panel.webview.html = lastPage;
  panel.reveal(undefined, true);
}

function setStatus(code, tip) {
  const s = STATUS[code] || STATUS[3];
  statusItem.text = s.text; statusItem.tooltip = tip || s.tip; statusItem.command = "agentmirror.menu"; statusItem.show();
}

function run(message, extraArgs = []) {
  const root = workspaceRoot();
  if (!root) { vscode.window.showErrorMessage("AgentMirror: open a folder (a git repository) first."); return; }
  const cfg = config();
  if (cfg.runTests && !vscode.workspace.isTrusted) {
    vscode.window.showWarningMessage("AgentMirror: running tests executes workspace code; trust this workspace first. Checking without tests.");
    cfg.runTests = false;
  }
  vscode.window.withProgress({ location: vscode.ProgressLocation.Window, title: "AgentMirror: checking…" }, () => new Promise((resolve) => {
    const child = cp.execFile(cfg.command, [...buildArgs(cfg, root), ...extraArgs], { cwd: root, maxBuffer: 64 * 1024 * 1024, timeout: 20 * 60 * 1000 },
      (err, stdout, stderr) => {
        const code = err ? (typeof err.code === "number" ? err.code : 3) : 0;
        if (err && err.code === "ENOENT") {
          vscode.window.showErrorMessage(`AgentMirror: cannot find '${cfg.command}'. Install it (pip install .) or set agentmirror.command.`);
        } else if (stdout && stdout.includes("<html")) {
          show(stdout);
        } else {
          vscode.window.showErrorMessage("AgentMirror: no report produced. " + (stderr || "").split("\n").slice(-3).join(" "));
        }
        setStatus(code); resolve();
      });
    if (message !== null) { child.stdin.write(message); child.stdin.end(); }
  }));
}

// `agentmirror check --hook` (run by Copilot, Claude Code, Codex, Cursor, ... when an agent stops) writes a sealed result under
// <repo>/.agentmirror/last/. We POLL that seal (every 2 s) and also use VS Code's file watcher as a fast path: the watcher was never
// verified to fire for a hidden folder, and a result nobody notices is the same as no result.
function watchHookResults(context) {
  const seen = new Map();
  const POLL_MS = Number(process.env.AGENTMIRROR_POLL_MS) || 2000;
  const folders = vscode.workspace.workspaceFolders || [];
  log(`activated; watching ${folders.length} folder(s) every ${POLL_MS} ms: ${folders.map((f) => f.uri.fsPath).join(", ")}`);
  const check = (folder, initial) => {
    const dir = path.join(folder.uri.fsPath, ".agentmirror", "last");
    try {
      const r = readResult(dir, undefined, folder.uri.fsPath);
      if (!r || seen.get(dir) === r.stamp) return;
      seen.set(dir, r.stamp);
      log(`${initial ? "existing" : "NEW"} result in ${dir} (stamp ${r.stamp}); sealed and readable: ${r.valid}`);
      if (!r.valid) { setStatus(4); return; }   // never display or trust an unsealed result
      const code = statusCodeFromDecision(r.dec);
      setStatus(code, describeDecision(r.dec));
      lastPage = injectCsp(r.page);
      if (vscode.workspace.getConfiguration("agentmirror").get("autoOpen") || panel) show(r.page);
      const mode = vscode.workspace.getConfiguration("agentmirror").get("notify");
      log(`status ${code}: ${describeDecision(r.dec)} | notify=${mode}${initial ? " (no toast for an existing result)" : ""}`);
      if (!initial && (mode === "always" || (mode === "review" && code === 1))) {
        const msg = `AgentMirror: ${describeDecision(r.dec)}`;
        (code === 1 ? vscode.window.showWarningMessage(msg, "Open report") : vscode.window.showInformationMessage(msg, "Open report"))
          .then((pick) => { if (pick) show(r.page); });
      }
    } catch (e) { log(`error while reading a result: ${e && e.stack || e}`); }
  };
  for (const folder of folders) {
    check(folder, true);
    try {
      const w = vscode.workspace.createFileSystemWatcher(new vscode.RelativePattern(folder, ".agentmirror/last/decision.sig"));
      w.onDidChange(() => check(folder, false)); w.onDidCreate(() => check(folder, false));
      context.subscriptions.push(w);
    } catch (e) { log(`file watcher unavailable (polling continues): ${e}`); }
    const timer = setInterval(() => check(folder, false), POLL_MS);
    context.subscriptions.push({ dispose: () => clearInterval(timer) });
  }
}

// Where would an agent's hook find agentmirror? Prefer an absolute path: the setting if absolute, else what a login shell resolves.
function resolveCommand(cfgCommand) {
  if (path.isAbsolute(cfgCommand)) return cfgCommand;
  try {
    const out = cp.execFileSync(process.env.SHELL || "/bin/zsh", ["-lc", 'command -v -- "$1"', "sh", cfgCommand], { timeout: 8000, encoding: "utf8" }).trim().split("\n").pop();
    if (out && path.isAbsolute(out)) return out;
  } catch (e) { /* fall through */ }
  return null;
}

async function installHook() {
  const root = workspaceRoot();
  if (!root) { vscode.window.showErrorMessage("AgentMirror: open a folder first."); return; }
  const target = path.join(root, ".github", "hooks", "agentmirror.json");
  if (fs.existsSync(target)) { vscode.window.showInformationMessage("AgentMirror: .github/hooks/agentmirror.json already exists; left unchanged. Run 'AgentMirror: Check the setup' to verify it."); return; }
  const cmd = resolveCommand(config().command);
  const note = cmd ? `The hook will run ${cmd} check --hook.` : `Could not find '${config().command}' on your login shell's PATH; the hook will use the bare name and may fail inside agents. Install it first (pip install .) or set agentmirror.command to its full path.`;
  const pick = await vscode.window.showWarningMessage(
    `Add .github/hooks/agentmirror.json? Agents that support hooks (Copilot in VS Code, Copilot CLI and cloud agent, and others that read this format) will run AgentMirror when they stop. It only informs; it never blocks. ${note}`,
    { modal: true, detail: "Optional and EXPERIMENTAL: also add a chat hook that tells the agent the last verdict on your next prompt. In one live test the first delivery coincided with a stalled Copilot chat (cause unproven). Not recommended yet." },
    "Add the file", "Add with the experimental chat hook");
  if (!pick) return;
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, hookFileContent(cmd || "agentmirror", pick === "Add with the experimental chat hook"));
  vscode.window.showInformationMessage("AgentMirror: hook file added. IMPORTANT: hooks are loaded when a chat session STARTS. Reload the window and start a NEW chat (a Local agent session; if a 'Copilot CLI' session does not run it, see docs/LIVE_TESTING.md).");
}

let channel;
function runDoctor() {
  const root = workspaceRoot();
  if (!root) { vscode.window.showErrorMessage("AgentMirror: open a folder first."); return; }
  channel = channel || vscode.window.createOutputChannel("AgentMirror setup check");
  channel.clear(); channel.show(true);
  const cmd = resolveCommand(config().command) || config().command;
  cp.execFile(cmd, ["doctor", "--repo", root], { cwd: root, timeout: 180000, maxBuffer: 8 * 1024 * 1024 }, (err, stdout, stderr) => {
    if (err && err.code === "ENOENT") { channel.appendLine(`Cannot find '${cmd}'. Install it (pip install .) or set agentmirror.command to its full path.`); return; }
    channel.appendLine(stdout || ""); if (stderr) channel.appendLine(stderr);
  });
}

// A guided demo: builds a small repo where a (simulated) agent made a false claim, shows the red verdict, and offers a prompt that
// makes Copilot produce a checkable claim in the user's own chat. Needs no agent and touches nothing in the user's workspace.
function tryDemo(context) {
  const base = (context.globalStorageUri && context.globalStorageUri.fsPath) || require("os").tmpdir();
  const dest = path.join(base, "agentmirror-demo");
  try { fs.mkdirSync(base, { recursive: true }); } catch (e) { /* execFile will report */ }
  const cmd = resolveCommand(config().command) || config().command;
  cp.execFile(cmd, ["demo", "--path", dest], { timeout: 120000, maxBuffer: 8 * 1024 * 1024 }, (err, stdout, stderr) => {
    if (err) { vscode.window.showErrorMessage(`AgentMirror demo failed: ${err.code === "ENOENT" ? `cannot find '${cmd}' (pip install . or set agentmirror.command)` : (stderr || String(err)).split("\n").slice(-2).join(" ")}`); return; }
    let info; try { info = JSON.parse(stdout); } catch (e) { vscode.window.showErrorMessage("AgentMirror demo: unexpected output."); return; }
    const r = readResult(path.join(dest, ".agentmirror", "last"), undefined, dest);
    if (!r || !r.valid) { vscode.window.showErrorMessage("AgentMirror demo: the demo result could not be verified."); return; }
    const code = statusCodeFromDecision(r.dec);
    setStatus(code, describeDecision(r.dec)); show(r.page);
    log(`demo shown (status ${code}) from ${dest}`);
    vscode.window.showWarningMessage(`AgentMirror demo: an agent said "${info.claim}" and AgentMirror says: ${describeDecision(r.dec)}`, "Copy a prompt to try it in Copilot", "Open the demo folder")
      .then((pick) => {
        if (pick === "Open the demo folder") vscode.commands.executeCommand("vscode.openFolder", vscode.Uri.file(dest), { forceNewWindow: true });
        else if (pick) { vscode.env.clipboard.writeText(info.copilot_prompt); vscode.window.showInformationMessage("Prompt copied. Open the demo folder in a new window, add the hook (AgentMirror: Add the agent hook), start a new Copilot chat and paste it."); }
      });
  });
}

// The status bar item opens this menu, so every feature is reachable with one click (no command palette needed).
async function showMenu() {
  const items = [
    { label: "$(eye) Open the last report", cmd: "agentmirror.showReport" },
    { label: "$(play) Try the demo (see a verdict in 10 seconds)", cmd: "agentmirror.tryDemo" },
    { label: "$(checklist) Check the setup (doctor)", cmd: "agentmirror.doctor" },
    { label: "$(add) Add the agent hook to this workspace", cmd: "agentmirror.installHook" },
    { label: "$(output) Show the log", cmd: "agentmirror.showLog" },
  ];
  const pick = await vscode.window.showQuickPick(items, { placeHolder: "AgentMirror" });
  if (pick) vscode.commands.executeCommand(pick.cmd);
}

function activate(context) {
  statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);   // must exist before anything calls setStatus
  context.subscriptions.push(statusItem);
  context.subscriptions.push(vscode.commands.registerCommand("agentmirror.installHook", installHook));
  context.subscriptions.push(vscode.commands.registerCommand("agentmirror.doctor", runDoctor));
  context.subscriptions.push(vscode.commands.registerCommand("agentmirror.menu", showMenu));
  context.subscriptions.push(vscode.commands.registerCommand("agentmirror.tryDemo", () => tryDemo(context)));
  context.subscriptions.push(vscode.commands.registerCommand("agentmirror.showLog", () => { log("log opened"); logChannel.show(true); }));
  statusItem.text = "$(shield) AgentMirror"; statusItem.tooltip = "AgentMirror: click for the menu (try the demo, open the last report, check the setup)"; statusItem.command = "agentmirror.menu"; statusItem.show();
  watchHookResults(context);
  // `@agentmirror` in the chat: shows the last sealed verdict as a chat message (deterministic text, not model output).
  if (vscode.chat && vscode.chat.createChatParticipant) {
    try {
      const part = vscode.chat.createChatParticipant("agentmirror.chat", async (request, chatContext, stream) => {
        const root = workspaceRoot();
        const r = root ? readResult(path.join(root, ".agentmirror", "last"), undefined, root) : null;
        if (!r) stream.markdown("No AgentMirror result in this workspace yet. Add the hook (command: *AgentMirror: Add the agent hook*), run an agent turn, then ask again.");
        else if (!r.valid) stream.markdown("The result file in this workspace was **not sealed by AgentMirror**, so it is not shown.");
        else {
          stream.markdown(decisionMarkdown(r.dec));
          stream.button({ command: "agentmirror.showReport", title: "Open the full report" });
        }
        log(`@agentmirror answered (result present: ${!!r}, sealed: ${!!(r && r.valid)})`);
        return {};
      });
      context.subscriptions.push(part);
      log("chat participant @agentmirror registered");
    } catch (e) { log(`chat participant not available: ${e}`); }
  }
  const reg = (id, fn) => context.subscriptions.push(vscode.commands.registerCommand(id, fn));
  reg("agentmirror.checkMessage", async () => {
    const text = await vscode.window.showInputBox({ prompt: "Paste the agent's final message (any agent)", placeHolder: "e.g. I raised retries to 5. All 217 tests pass. No downstream impact." });
    if (text) run(text);
  });
  reg("agentmirror.checkClipboard", async () => {
    const text = await vscode.env.clipboard.readText();
    if (text && text.trim()) run(text); else vscode.window.showInformationMessage("AgentMirror: the clipboard is empty.");
  });
  reg("agentmirror.checkSelection", () => {
    const ed = vscode.window.activeTextEditor;
    const text = ed && ed.document.getText(ed.selection);
    if (text && text.trim()) run(text); else vscode.window.showInformationMessage("AgentMirror: select the agent's message first.");
  });
  reg("agentmirror.checkClaudeSession", () => {
    const root = workspaceRoot();
    const file = root && latestSession(root);
    if (!file) { vscode.window.showInformationMessage("AgentMirror: no Claude Code session found for this workspace."); return; }
    run(null, ["--session", file]);
  });
  reg("agentmirror.showReport", () => {
    if (lastPage) show(lastPage.replace(/^<meta[^>]*>/, "")); else vscode.window.showInformationMessage("AgentMirror: no report yet.");
  });
}

function deactivate() {}
module.exports = { activate, deactivate };
