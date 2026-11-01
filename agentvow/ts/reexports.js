// Module specifiers a TypeScript file re-exports (`export * from "x"`, `export { a } from "x"`). Parser only; nothing is loaded or run.
// Usage: node reexports.js < {"src": "...", "file": "a.ts"} -> ["./x", ...]
const ts = require("typescript");
let buf = "";
process.stdin.on("data", d => (buf += d));
process.stdin.on("end", () => {
  const { src, file } = JSON.parse(buf);
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const out = [];
  for (const st of sf.statements) if (ts.isExportDeclaration(st) && st.moduleSpecifier && ts.isStringLiteral(st.moduleSpecifier)) out.push(st.moduleSpecifier.text);
  console.log(JSON.stringify(out));
});
