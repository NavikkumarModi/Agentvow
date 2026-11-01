// Prototype (docs/research/API_DIFF_TS_PROTOTYPE.md): syntactic public-API diff of one TypeScript file between two versions of its text.
// Parses with the TypeScript parser only (createSourceFile): no type checking, no module resolution, no build, nothing from the repository is loaded or run.
// Usage: node exports.js < {"old": "...", "new": "...", "file": "a.ts"}   -> {"breaking": [...], "changed": [...], "gaps": [...]}
// "breaking" follows the rules @clerk/break-check documents (removed export or member, required parameter added, optional made required, parameter removed);
// "changed" is a declared type or return text that differs (break-check calls any type change breaking; here it is reported separately because only text is compared).
const ts = require("typescript");

function parse(src, file) {
  return ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
}
const hasMod = (n, k) => (ts.getCombinedModifierFlags ? !!(ts.canHaveModifiers(n) && (ts.getModifiers(n) || []).some(m => m.kind === k)) : false);
const exported = n => hasMod(n, ts.SyntaxKind.ExportKeyword);
const text = (n, sf) => (n ? n.getText(sf).replace(/\s+/g, " ") : "");

function params(fn, sf) {
  return (fn.parameters || []).map(p => ({
    name: p.name.getText(sf), optional: !!p.questionToken || !!p.initializer, rest: !!p.dotDotDotToken, type: text(p.type, sf),
  }));
}
function sig(fn, sf) { return { kind: "fn", params: params(fn, sf), ret: text(fn.type, sf) }; }

function members(node, sf, out, prefix) {
  for (const m of node.members || []) {
    const name = m.name ? m.name.getText(sf) : null;
    if (!name && m.kind !== ts.SyntaxKind.Constructor && m.kind !== ts.SyntaxKind.CallSignature) continue;
    if (hasMod(m, ts.SyntaxKind.PrivateKeyword) || (name && name.startsWith("#"))) continue;
    if (hasMod(m, ts.SyntaxKind.ProtectedKeyword) && node.kind === ts.SyntaxKind.ClassDeclaration) { /* protected counts: subclasses use it */ }
    const key = `${prefix}.${name || (m.kind === ts.SyntaxKind.Constructor ? "constructor" : "()")}`;
    if (ts.isMethodDeclaration(m) || ts.isMethodSignature(m) || ts.isConstructorDeclaration(m) || ts.isCallSignatureDeclaration(m)) {
      const s = sig(m, sf); s.optional = !!m.questionToken; out[key + (out[key] ? "#overload" + Object.keys(out).filter(k => k.startsWith(key)).length : "")] = s;
    } else if (ts.isPropertyDeclaration(m) || ts.isPropertySignature(m)) {
      out[key] = { kind: "prop", optional: !!m.questionToken, readonly: hasMod(m, ts.SyntaxKind.ReadonlyKeyword), type: text(m.type, sf) };
    } else if (ts.isGetAccessorDeclaration(m) || ts.isSetAccessorDeclaration(m)) {
      out[key] = { kind: "prop", optional: false, readonly: false, type: text(m.type, sf) };
    }
  }
}

function api(src, file) {
  const sf = parse(src, file), out = {}, gaps = [];
  for (const st of sf.statements) {
    if (ts.isFunctionDeclaration(st) && exported(st) && st.name) {
      const key = st.name.text; out[key + (out[key] ? "#overload" + Object.keys(out).length : "")] = sig(st, sf);
    } else if (ts.isClassDeclaration(st) && exported(st) && st.name) {
      out[st.name.text] = { kind: "class", ext: (st.heritageClauses || []).map(h => text(h, sf)).join(",") }; members(st, sf, out, st.name.text);
    } else if (ts.isInterfaceDeclaration(st) && exported(st)) {
      out[st.name.text] = { kind: "interface", ext: (st.heritageClauses || []).map(h => text(h, sf)).join(",") }; members(st, sf, out, st.name.text);
    } else if (ts.isTypeAliasDeclaration(st) && exported(st)) {
      out[st.name.text] = { kind: "type", type: text(st.type, sf) };
    } else if (ts.isEnumDeclaration(st) && exported(st)) {
      out[st.name.text] = { kind: "enum" }; for (const m of st.members) out[`${st.name.text}.${m.name.getText(sf)}`] = { kind: "member" };
    } else if (ts.isVariableStatement(st) && exported(st)) {
      for (const d of st.declarationList.declarations) if (ts.isIdentifier(d.name)) out[d.name.text] = { kind: "var", type: text(d.type, sf) };
    } else if (ts.isExportDeclaration(st)) {
      if (!st.exportClause) gaps.push(`wildcard re-export: ${text(st, sf).slice(0, 80)}`);
      else if (ts.isNamedExports(st.exportClause)) for (const e of st.exportClause.elements) out[e.name.text] = { kind: "reexport" };
      else if (ts.isNamespaceExport(st.exportClause)) out[st.exportClause.name.text] = { kind: "reexport" };
    } else if (ts.isExportAssignment(st)) {
      out["default"] = { kind: "default", type: text(st.expression, sf).slice(0, 80) };
    } else if (ts.isModuleDeclaration(st) && exported(st) && st.name) {
      out[st.name.text] = { kind: "namespace" };
    }
  }
  if (sf.parseDiagnostics && sf.parseDiagnostics.length) gaps.push(`parse errors: ${sf.parseDiagnostics.length}`);
  return { out, gaps };
}

function diff(o, n) {
  const breaking = [], changed = [];
  for (const [k, a] of Object.entries(o)) {
    const b = n[k];
    if (!b) {
      const parent = k.includes(".") ? k.split(".")[0] : null;
      const po = parent && o[parent], pn = parent && n[parent];
      if (po && pn && (po.kind === "class" || po.kind === "interface") && po.ext !== pn.ext) { changed.push(`removed from ${parent} (its base types changed, so the member may be inherited): ${k}`); continue; }
      breaking.push(`removed: ${k}`); continue;
    }
    if (a.kind !== b.kind) { breaking.push(`${k}: changed kind ${a.kind} -> ${b.kind}`); continue; }
    if (a.kind === "fn") {
      const ap = a.params, bp = b.params;
      const bnames = new Set(bp.map(p => p.name)); const removed = bp.length < ap.length ? ap.filter(p => !p.rest && !bnames.has(p.name)) : [];
      if (removed.length) breaking.push(`${k}: parameter(s) removed: ${removed.map(p => p.name).join(", ")}`);
      for (let i = 0; i < Math.min(ap.length, bp.length); i++) {
        if (ap[i].optional && !bp[i].optional) breaking.push(`${k}: parameter ${bp[i].name} made required`);
        if (ap[i].rest !== bp[i].rest) breaking.push(`${k}: parameter ${bp[i].name} rest-ness changed`);
        if (ap[i].type && bp[i].type && ap[i].type !== bp[i].type) changed.push(`${k}: parameter ${bp[i].name} type text changed`);
      }
      const added = bp.slice(ap.length).filter(p => !p.optional && !p.rest);
      if (added.length) breaking.push(`${k}: new required parameter(s): ${added.map(p => p.name).join(", ")}`);
      if (a.ret && b.ret && a.ret !== b.ret) changed.push(`${k}: return type text changed`);
    } else if (a.kind === "prop") {
      if (a.optional && !b.optional) breaking.push(`${k}: property made required`);
      if (!a.readonly && b.readonly) breaking.push(`${k}: property made readonly`);
      if (a.type && b.type && a.type !== b.type) changed.push(`${k}: type text changed`);
    } else if ((a.kind === "type" || a.kind === "var") && a.type !== b.type) changed.push(`${k}: ${a.kind} text changed`);
    else if (a.kind === "class" && a.ext !== b.ext) changed.push(`${k}: heritage changed`);
  }
  return { breaking, changed };
}

let buf = "";
process.stdin.on("data", d => (buf += d));
process.stdin.on("end", () => {
  const { old, new: nw, file } = JSON.parse(buf);
  try {
    const o = api(old, file), n = api(nw, file);
    if (o.gaps.some(g => g.startsWith("parse errors")) || n.gaps.some(g => g.startsWith("parse errors"))) {
      console.log(JSON.stringify({ breaking: [], changed: [], gaps: [`parse errors in the ${o.gaps.some(g => g.startsWith("parse errors")) ? "old" : "new"} version; no comparison made`] })); return;
    }
    const d = diff(o.out, n.out);
    const gaps = [...new Set([...o.gaps, ...n.gaps])];
    console.log(JSON.stringify({ ...d, gaps }));
  } catch (e) { console.log(JSON.stringify({ breaking: [], changed: [], gaps: ["exception: " + String(e).slice(0, 120)] })); }
});
