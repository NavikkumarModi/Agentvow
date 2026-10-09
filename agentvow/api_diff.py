"""Public-API diff between two commits (Python, static): removed names and incompatible signature changes."""
import ast
import subprocess

from .reality import safe_prefix
from pathlib import Path


def _show(repo: Path, ref: str, path: str):
    r = subprocess.run(["git", *safe_prefix(repo), "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def _sig(fn):
    a = fn.args
    pos = [x.arg for x in a.posonlyargs + a.args]
    req = pos[: len(pos) - len(a.defaults)]
    kw = [x.arg for x in a.kwonlyargs]
    kwreq = [x.arg for x, d in zip(a.kwonlyargs, a.kw_defaults) if d is None]
    return {"pos": pos, "req": req, "kw": kw, "kwreq": kwreq, "var": a.vararg is not None, "varkw": a.kwarg is not None}


def public_api(source: str, is_init: bool = False) -> dict:
    api = {}
    for n in ast.parse(source).body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_"):
            api[n.name] = _sig(n)
        elif isinstance(n, ast.ClassDef) and not n.name.startswith("_"):
            api[n.name] = {"class": True}
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and (not m.name.startswith("_") or m.name == "__init__"):
                    api[f"{n.name}.{m.name}"] = _sig(m)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and not n.target.id.startswith("_"):
            api[n.target.id] = {"const": True}
        elif is_init and isinstance(n, ast.ImportFrom):
            for a in n.names:  # names re-exported from a package __init__ are part of its public API
                nm = a.asname or a.name
                if not nm.startswith("_") and nm != "*":
                    api.setdefault(nm, {"const": True})
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and not t.id.startswith("_"):
                    api[t.id] = {"const": True}
    return api


def breaking(old: dict, new: dict) -> list:
    out = []
    for name, o in old.items():
        n = new.get(name)
        if n is None:
            out.append(f"removed: {name}")
        elif "pos" in o and "pos" in n:
            gone = [p for p in o["pos"] + o["kw"] if p not in n["pos"] + n["kw"] and not n["varkw"]]
            added = [p for p in n["req"] if p not in o["req"]] + [p for p in n["kwreq"] if p not in o["kwreq"]]
            order = o["pos"] != n["pos"][: len(o["pos"])] and not gone
            if gone:
                out.append(f"{name}: parameter(s) removed or renamed: {', '.join(gone)}")
            if added:
                out.append(f"{name}: new required parameter(s): {', '.join(added)}")
            if order:
                out.append(f"{name}: positional parameter order changed")
        elif ("pos" in o) != ("pos" in n):
            out.append(f"{name}: changed kind (function/class/constant)")
    return out


def diff(repo: Path, base: str, files: list):
    """Return (breaking_changes, gaps). Files that fail to parse are gaps, never silently OK."""
    found, gaps = [], []
    for f in files:
        if not f.endswith(".py"):
            continue
        old = _show(repo, base, f)
        if old is None:
            continue  # new file: nothing to break
        try:
            new_src = (repo / f).read_text(encoding="utf-8") if (repo / f).exists() else None
            if new_src is None:
                found.append(f"removed file: {f}")
                continue
            found += [f"{f}: {x}" for x in breaking(public_api(old, f.endswith('__init__.py')), public_api(new_src, f.endswith('__init__.py')))]
        except (SyntaxError, UnicodeDecodeError, RecursionError, MemoryError, ValueError):
            gaps.append(f"could not parse {f} for API comparison")
    return found, gaps
