// What a TypeScript file re-exports, by name. Parser only; nothing is loaded or run.
// Usage: node reexports.js < {"src": "...", "file": "a.ts"} -> {"edges": [{"spec": "./x", "names": ["a", "b"] | "*"}]}
//   `export * from "x"` and `export * as ns from "x"`        -> names "*" (the whole module is public through this file)
//   `export { a, b as c } from "x"`, `export type { T } from` -> names the *underlying* symbols ["a", "b"]
//   `import { a } from "x"; export { a }` and `export default a` -> an edge to "x" for the underlying symbol
const ts = require("typescript");
let buf = "";
process.stdin.on("data", d => (buf += d));
process.stdin.on("end", () => {
  const { src, file } = JSON.parse(buf);
  const sf = ts.createSourceFile(file, src, ts.ScriptTarget.Latest, true, file.endsWith("x") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const imports = {};                       // local name -> {spec, orig}
  for (const st of sf.statements) {
    if (!ts.isImportDeclaration(st) || !ts.isStringLiteral(st.moduleSpecifier) || !st.importClause) continue;
    const spec = st.moduleSpecifier.text, c = st.importClause;
    if (c.name) imports[c.name.text] = { spec, orig: "default" };
    if (c.namedBindings && ts.isNamedImports(c.namedBindings)) for (const e of c.namedBindings.elements) imports[e.name.text] = { spec, orig: (e.propertyName || e.name).text };
    if (c.namedBindings && ts.isNamespaceImport(c.namedBindings)) imports[c.namedBindings.name.text] = { spec, orig: "*" };
  }
  const edges = {};
  const add = (spec, name) => {
    if (edges[spec] === "*") return;
    if (name === "*") { edges[spec] = "*"; return; }
    (edges[spec] = edges[spec] || new Set()).add(name);
  };
  for (const st of sf.statements) {
    if (ts.isExportDeclaration(st)) {
      if (st.moduleSpecifier && ts.isStringLiteral(st.moduleSpecifier)) {
        const spec = st.moduleSpecifier.text;
        if (!st.exportClause || ts.isNamespaceExport(st.exportClause)) add(spec, "*");
        else for (const e of st.exportClause.elements) add(spec, (e.propertyName || e.name).text);
      } else if (st.exportClause && ts.isNamedExports(st.exportClause)) {
        for (const e of st.exportClause.elements) { const loc = (e.propertyName || e.name).text; if (imports[loc]) add(imports[loc].spec, imports[loc].orig); }
      }
    } else if (ts.isExportAssignment(st) && ts.isIdentifier(st.expression) && imports[st.expression.text]) {
      const i = imports[st.expression.text]; add(i.spec, i.orig);
    }
  }
  console.log(JSON.stringify({ edges: Object.entries(edges).map(([spec, n]) => ({ spec, names: n === "*" ? "*" : [...n].sort() })) }));
});
