"""Portable visual report: one self-contained HTML file (no scripts, no external resources).

The same file is shown in a VS Code webview, a browser, a CI artifact or a PR comment attachment.
Colour is never the only signal: every verdict also has an icon and a text label.
"""
import dataclasses
import html
import unicodedata

from .decision import INSUFFICIENT, NO_CONTRA, REVIEW, Decision

SCHEMA_VERSION = "1"

VERDICT = {  # label, icon, css class
    "CONTRADICTED": ("Contradicted", "✗", "bad"),
    "SUPPORTED_BY_PRIOR_EVIDENCE": ("Supported", "✓", "good"),
    "NOT_CONTRADICTED": ("Not contradicted (scoped)", "~", "ok"),
    "UNKNOWN": ("Unknown", "?", "unk"),
}
HEADLINE = {
    REVIEW: ("bad", "Review before approving", "Something the agent said does not match what is in the repository."),
    INSUFFICIENT: ("unk", "Not enough evidence to judge", "Treat the agent's claims as unverified until the unknowns below are resolved."),
    NO_CONTRA: ("ok", "No contradiction found in what could be checked",
                "This is not a safety verdict: only the checks listed below were done."),
}


def to_dict(d: Decision) -> dict:
    out = dataclasses.asdict(d)
    out["schema_version"] = SCHEMA_VERSION
    return out


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _cut(x, n=150) -> str:
    x = str(x)
    return x if len(x) <= n else x[: n - 1] + "…"


def _map_svg(findings) -> str:
    """Claims on the left, the reality they were compared with on the right."""
    rows, w, rh = [], 900, 46
    left_x, right_x, node_w = 14, 560, 326
    right = []  # (label, kind)
    edges = []  # (claim_index, right_index, cls)
    for i, f in enumerate(findings):
        _, _, cls = VERDICT[f.verdict]
        for ev in f.evidence[:3]:
            right.append((ev, "evidence")); edges.append((i, len(right) - 1, cls))
        for u in f.unknowns[:2]:
            right.append((u, "unknown")); edges.append((i, len(right) - 1, "unk"))
        if not f.evidence and not f.unknowns:
            right.append(("no independent evidence found", "none")); edges.append((i, len(right) - 1, "unk"))
    n = max(len(findings), len(right), 1)
    h = n * rh + 40
    cy = lambda idx, total: 28 + (idx + 0.5) * (h - 40) / max(total, 1)
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Map from the agent\'s claims to the evidence found" class="map">',
             f'<text x="{left_x}" y="16" class="mh">WHAT THE AGENT SAID</text><text x="{right_x}" y="16" class="mh">WHAT THE REPOSITORY SHOWS</text>']
    for a, b, cls in edges:
        y1, y2 = cy(a, len(findings)), cy(b, len(right))
        parts.append(f'<path d="M{left_x + 326},{y1:.0f} C{left_x + 450},{y1:.0f} {right_x - 130},{y2:.0f} {right_x},{y2:.0f}" class="edge {cls}"/>')
    for i, f in enumerate(findings):
        label, icon, cls = VERDICT[f.verdict]
        y = cy(i, len(findings))
        parts.append(f'<g class="node {cls}"><title>{_e(f.claim)}</title><rect x="{left_x}" y="{y - 18:.0f}" width="326" height="36" rx="8"/>'
                     f'<text x="{left_x + 10}" y="{y - 2:.0f}" class="nt">{icon} {_e(_cut(f.claim, 44))}</text>'
                     f'<text x="{left_x + 10}" y="{y + 12:.0f}" class="ns">{_e(label)}</text></g>')
    for j, (label, kind) in enumerate(right):
        y = cy(j, len(right))
        cls = {"evidence": "ev", "unknown": "unk", "none": "unk"}[kind]
        tag = {"evidence": "evidence", "unknown": "unknown", "none": "gap"}[kind]
        parts.append(f'<g class="node {cls}"><title>{_e(label)}</title><rect x="{right_x}" y="{y - 16:.0f}" width="{node_w}" height="32" rx="8"/>'
                     f'<text x="{right_x + 10}" y="{y - 1:.0f}" class="nt">{_e(_cut(label, 46))}</text>'
                     f'<text x="{right_x + 10}" y="{y + 11:.0f}" class="ns">{tag}</text></g>')
    parts.append("</svg>")
    return "".join(parts)


CSS = """
:root{--bg:var(--vscode-editor-background,#fbfbfa);--fg:var(--vscode-editor-foreground,#1d1f23);--mut:#6b7280;--card:var(--vscode-sideBar-background,#fff);--line:#d9dbe0;
--bad:#c8352b;--badbg:#fdecea;--good:#1f7a4d;--goodbg:#e7f5ed;--ok:#2563a8;--okbg:#e8f0fb;--unk:#8a6d00;--unkbg:#fdf5dc}
@media (prefers-color-scheme:dark){:root{--bg:var(--vscode-editor-background,#16181d);--fg:var(--vscode-editor-foreground,#e6e8ec);--mut:#9aa1ad;--card:var(--vscode-sideBar-background,#1e2128);--line:#343a46;
--bad:#ff7b72;--badbg:#3a1d1f;--good:#56d390;--goodbg:#16301f;--ok:#79b8ff;--okbg:#14263d;--unk:#e3b341;--unkbg:#33290d}}
*{box-sizing:border-box}body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:980px;margin:0 auto}h1,h2,h3{margin:0}h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);margin:28px 0 10px}
.banner{border:1px solid var(--line);border-left:6px solid;border-radius:10px;padding:16px 18px;background:var(--card)}
.banner.bad{border-left-color:var(--bad)}.banner.unk{border-left-color:var(--unk)}.banner.ok{border-left-color:var(--ok)}
.banner h1{font-size:22px}.banner p{margin:6px 0 0;color:var(--mut)}
.q{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}
.q>div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}.q b{display:block;font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--mut);margin-bottom:4px}
.q ul{margin:4px 0 0;padding-left:18px}.q li{margin:2px 0;overflow-wrap:anywhere}
.claim{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}
.claim blockquote{margin:0 0 8px;font-style:italic;overflow-wrap:anywhere}
.badge{display:inline-flex;gap:6px;align-items:center;font-weight:600;font-size:13px;border-radius:999px;padding:2px 10px;margin-bottom:8px}
.badge.bad{color:var(--bad);background:var(--badbg)}.badge.good{color:var(--good);background:var(--goodbg)}.badge.ok{color:var(--ok);background:var(--okbg)}.badge.unk{color:var(--unk);background:var(--unkbg)}
.claim p{margin:4px 0}.claim ul{margin:6px 0 0;padding-left:18px;color:var(--mut);font-size:13px;overflow-wrap:anywhere}
.mapwrap{overflow-x:auto;border-radius:10px}.map{display:block;min-width:760px;width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
.map text{fill:var(--fg);font:12px system-ui,sans-serif}.map .mh{fill:var(--mut);font-size:11px;letter-spacing:.06em}.map .ns{fill:var(--mut);font-size:10.5px}
.map rect{fill:var(--card);stroke:var(--line);stroke-width:1.2}.map .node.bad rect{stroke:var(--bad);stroke-width:2}.map .node.good rect{stroke:var(--good);stroke-width:2}
.map .node.ok rect{stroke:var(--ok);stroke-width:2}.map .node.unk rect{stroke-dasharray:5 3;stroke:var(--unk)}.map .node.ev rect{stroke:var(--mut)}
.edge{fill:none;stroke-width:1.6;opacity:.8}.edge.bad{stroke:var(--bad)}.edge.good{stroke:var(--good)}.edge.ok{stroke:var(--ok)}.edge.unk{stroke:var(--unk);stroke-dasharray:4 4}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}.two>div{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px}
.two h3{font-size:15px;margin-bottom:6px}.two ul{margin:0;padding-left:18px}
footer{margin-top:28px;color:var(--mut);font-size:12.5px}code{font-family:ui-monospace,Menlo,monospace;font-size:12px}
"""


def render_html(d: Decision, title: str = "AgentMirror report") -> str:
    cls, head, sub = HEADLINE.get(d.status, ("unk", d.status, ""))
    claims = [f for f in d.findings if f.kind not in ("snapshot",)]
    verified = [f for f in claims if f.verdict in ("SUPPORTED_BY_PRIOR_EVIDENCE", "NOT_CONTRADICTED")]
    bad = [f for f in claims if f.verdict == "CONTRADICTED"]
    unknown = [f for f in claims if f.verdict == "UNKNOWN"]
    changed = d.changed[:8]
    o = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
         f'<title>{_e(title)}</title><style>{CSS}</style></head><body><main>',
         f'<div class="banner {cls}" role="status"><h1>{_e(head)}</h1><p>{_e(sub)}</p></div>',
         '<h2>The four questions</h2><div class="q">',
         f'<div><b>1 · What did the agent do?</b>{len(d.changed)} file(s) changed'
         + ("<ul>" + "".join(f"<li><code>{_e(_cut(f, 60))}</code></li>" for f in changed) + (f"<li>… and {len(d.changed) - 8} more</li>" if len(d.changed) > 8 else "") + "</ul>" if d.changed else "") + "</div>",
         f'<div><b>2 · What does it believe?</b>{len(claims)} statement(s) checked'
         + (f'<ul>{"".join(f"<li>{_e(_cut(f.claim, 70))}</li>" for f in claims[:4])}</ul>' if claims else "") + "</div>",
         f'<div><b>3 · What does the repository show?</b><ul><li>{len(bad)} contradicted</li><li>{len(verified)} not contradicted or supported</li><li>{len(unknown)} unknown</li></ul></div>',
         f'<div><b>4 · What are you deciding?</b>Whether to accept this change as the agent described it.'
         + (f"<ul><li>{d.unexamined} other statement(s) were not examined</li></ul>" if d.unexamined else "") + "</div></div>",
         "<h2>Claim to reality</h2>", '<div class="mapwrap">' + _map_svg(claims) + '</div>' if claims else "<p>No checkable claims were found, so nothing was verified.</p>",
         "<h2>Each claim in detail</h2>"]
    for f in claims:
        label, icon, c = VERDICT[f.verdict]
        o.append(f'<section class="claim"><span class="badge {c}"><span aria-hidden="true">{icon}</span>{_e(label)}</span><blockquote>“{_e(f.claim)}”</blockquote><p>{_e(f.why)}</p>')
        if f.evidence:
            o.append("<ul>" + "".join(f"<li>evidence: {_e(_cut(x, 220))}</li>" for x in f.evidence[:6]) + "</ul>")
        if f.unknowns:
            o.append("<ul>" + "".join(f"<li>unknown: {_e(_cut(x, 220))}</li>" for x in f.unknowns[:6]) + "</ul>")
        o.append("</section>")
    o.append('<h2>What your approval would and would not mean</h2><div class="two"><div><h3>Approving would mean</h3><ul>'
             "<li>you accept this change as the agent described it</li>"
             + "".join(f"<li>checked: {_e(_cut(f.claim, 60))}</li>" for f in verified[:4]) + "</ul></div>"
             '<div><h3>It would NOT mean</h3><ul>'
             + "".join(f"<li>verified: {_e(_cut(f.claim, 60))}</li>" for f in unknown[:4] + bad[:4])
             + "<li>that anything outside the checks listed here is safe</li><li>permission to deploy or make unrelated changes</li></ul></div></div>")
    o.append(f'<footer>Checked commit <code>{_e(d.commit[:10])}</code>{" (including uncommitted changes)" if d.dirty else ""}. Scope: {_e(d.scope)}. '
             "AgentMirror informs your decision; it does not approve, reject or merge anything.</footer></main></body></html>")
    return "".join(o)


MARKER = "<!-- agentmirror-report -->"


_MD_SPECIAL = "\\`*_{}[]()#+-.!|<>~&"


def _md(x, n=200) -> str:
    """Escape agent-controlled text for markdown/GitHub: no HTML, links, images, @mentions, emoji shortcodes, table breaks or invisible characters."""
    x = "".join(ch for ch in str(x) if unicodedata.category(ch) not in ("Cf", "Cc") or ch in "\n\t")
    x = " ".join(x.split())
    x = x if len(x) <= n else x[: n - 1] + "…"
    out = []
    for ch in x:
        if ch == "@":
            out.append("&#64;")
        elif ch == ":":
            out.append("\\:")
        elif ch in _MD_SPECIAL:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def render_markdown(d: Decision) -> str:
    """Compact summary for PR comments / terminals. The full visual report is the HTML file."""
    cls, head, sub = HEADLINE.get(d.status, ("unk", d.status, ""))
    icon = {"bad": "🔴", "unk": "🟡", "ok": "🔵"}[cls]
    claims = [f for f in d.findings if f.kind != "snapshot"]
    o = [MARKER, f"## {icon} AgentMirror: {head}", "", _md(sub), "",
         f"Checked commit `{d.commit[:10]}`{' (including uncommitted changes)' if d.dirty else ''}.", ""]
    if claims:
        o += ["| | Claim | Result |", "|---|---|---|"]
        for f in claims:
            label, ic, _ = VERDICT[f.verdict]
            o.append(f"| {ic} | {_md(f.claim, 90)} | **{label}** |")
        o.append("")
        for f in claims:
            label, ic, _ = VERDICT[f.verdict]
            o += [f"<details><summary>{ic} {label}: {_md(f.claim, 80)}</summary>", "", _md(f.why, 700), ""]
            o += [f"- evidence: {_md(x)}" for x in f.evidence[:5]]
            o += [f"- unknown: {_md(x)}" for x in f.unknowns[:5]]
            o += ["", "</details>", ""]
    else:
        o += ["No checkable claims were found, so nothing was verified.", ""]
    if d.unexamined:
        o += [f"_{d.unexamined} other statement\\(s\\) in the agent's message were not examined._", ""]
    o += [f"_Scope: {_md(d.scope)}. AgentMirror informs your decision; it does not approve, reject or merge anything._"]
    return "\n".join(o)
