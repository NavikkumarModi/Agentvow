"""Rule-based claim extraction. No LLM: anything not matched is reported as unchecked."""
import re
from dataclasses import dataclass

NO_IMPACT = "no_downstream_impact"
TESTS_PASS = "tests_pass"
BACKCOMPAT = "backward_compatible"

_PATTERNS = [
    (BACKCOMPAT, re.compile(r"\b(?:no|without|non)[- ]breaking (?:changes?|api)\b|\bbackward[s]?[- ]compatib|\bno api changes?\b|\bpublic api (?:is )?unchanged\b", re.I)),
    (NO_IMPACT, re.compile(r"\bno (?:other |further )?(?:downstream |side )?(?:impact|effects?|consumers?|dependents?)\b|\bnothing else (?:depends|is affected)\b|\bdoes(?:n't| not) affect (?:any )?(?:other|downstream)", re.I)),
    (TESTS_PASS, re.compile(r"\b(?:all )?tests? (?:are )?(?:pass(?:ed|ing)?|green)\b|\b\d+ passed\b|\b(\d[\d,]*)\s*/\s*\1\s+(?:tests?\s+)?(?:pass\w*|green)\b|\b\d[\d,]*\s+(?:[\w-]+\s+){0,2}tests?\b[^.\n]{0,80}\b(?:all )?(?:green|pass\w*|succe\w+)\b|\b(?:ran|run|running)\b[^.\n]{0,40}\b(?:tests?|pytest|test suite|suite)\b[^.\n]{0,60}\b(?:pass\w*|green|succe\w+)\b|\b(?:tests?|pytest|test suite|suite)\b[^.\n]{0,25}[:—-]\s*(?:all )?(?:pass\w*|green|ok|succe\w+)\b|\b(?:verified|confirmed)\b[^.\n]{0,60}\b(?:tests?|pytest|suite)\b[^.\n]{0,40}\b(?:pass\w*|green|succe\w+)\b", re.I)),
]
_GENERIC = re.compile(r"\b(?:safe to merge|looks good|fully (?:tested|verified)|ready to ship|backward[- ]compatible)\b", re.I)


@dataclass
class Claim:
    kind: str  # NO_IMPACT, TESTS_PASS, or "unchecked"
    text: str
    count: int | None = None  # number of tests the agent says passed, if stated


_RATIO = re.compile(r"\b(\d[\d,]*)\s*/\s*(\d[\d,]*)\s+(?:tests?\s+)?(?:pass\w*|green)\b", re.I)
_COUNT = re.compile(r"\b(\d[\d,]*)\s+(?:[\w-]+\s+){0,3}?tests?\s+(?:are\s+|were\s+|all\s+)?(?:pass(?:ed|ing)?|green)\b|\b(\d[\d,]*)\s+passed\b|\b(\d[\d,]*)\s+(?:[\w-]+\s+){0,2}tests?\b[^.\n]{0,80}\b(?:all )?(?:green|passing)\b", re.I)


_NEGATED = re.compile(r"\b(?:not|never|no longer|n't|unable to|failed to|couldn't|cannot|can't)\b[^.\n]{0,40}\b(?:confirm|verify|verified|run|ran|pass\w*|green)\b|\b(?:could|can) ?not\b", re.I)


def extract(transcript: str) -> list[Claim]:
    claims: list[Claim] = []
    transcript = transcript[-20000:]  # bound the work done on agent-controlled text (the regexes are not linear-time on adversarial input)
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", transcript):
        s = sentence.strip()[:600]
        if not s:
            continue
        if _NEGATED.search(s):
            claims.append(Claim("unchecked", s))  # a negated statement is not a claim of success; surface it as unchecked
            continue
        if re.search(r"\b[1-9]\d*\s+(?:failed|failing|failures?|errors?)\b", s, re.I):
            claims.append(Claim("unchecked", s))  # an honest failure report is not a claim that tests pass
            continue
        matched = False
        for kind, pat in _PATTERNS:
            if pat.search(s):
                r = _RATIO.search(s) if kind == TESTS_PASS else None
                m = _COUNT.search(s) if kind == TESTS_PASS and not r else None
                n = int(r.group(2).replace(",", "")) if r else (int(next(g for g in m.groups() if g).replace(",", "")) if m else None)
                claims.append(Claim(kind, s, n))
                matched = True
        if not matched and _GENERIC.search(s):
            claims.append(Claim("unchecked", s))
    return claims


def sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text) if x.strip()]


def count_unexamined(text: str, found: list) -> int:
    """Substantive sentences (5+ words) that no extractor pattern looked at."""
    seen = {c.text for c in found}
    return sum(1 for x in sentences(text) if len(x.split()) >= 5 and x not in seen)
