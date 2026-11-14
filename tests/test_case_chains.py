#!/usr/bin/env python3
"""Gates for the phase-chain diagram on every case page (site/cases/<slug>.html).

Every row traces to a source line, quoted words match the stored source quote,
WHY boxes match the sourced causes, milestones are backed and quiet, anatomy
words and codes are backed, staff-written pages are never used, and each case
page stays plain (FK grade). Quotes were checked against saved copies of each
person's own pages when the data was written; CI checks the data against the
drawing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import diagrams as dg  # noqa: E402
from readability import flesch_kincaid, visible_text  # noqa: E402

CASES = ROOT / "data" / "cases"
SITE = ROOT / "site" / "cases"
FK_MAX = 9.0
KINDS = {"own", "record", "tribute"}
STAFF_HOSTS = ("news.cuanschutz.edu", "iaslc.org")  # staff-written pages: never a chain source
ANATOMY = ("lung", "lobe", "chest", "collarbone", "lymph node", "spine", "vertebra", "brain",
           "bone", "liver", "airway")
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
STOP = {"the", "that", "her", "his", "their", "a", "an", "on", "it", "of", "in"}
CELEBRATE = re.compile(r"(?i)[★☆✓✔🏆🎉\U0001F300-\U0001FAFF]|congrat|victory|triumph|hero\b|miracle|"
                       r"amazing|incredible|beat (?:the )?cancer|winning|celebrat")
LEVEL_RE = re.compile(r"\bT(?:h)?(\d{1,2})(?:\s*[–/-]\s*T?(?:h)?(\d{1,2}))?\b")

errors: list[str] = []
QUIET = [False]


def err(msg: str) -> None:
    errors.append(msg)
    if not QUIET[0]:
        print(f"FAIL: {msg}")


def ok(msg: str) -> None:
    print(f"ok: {msg}")


def levels(s: str) -> set:
    out = set()
    for m in LEVEL_RE.finditer(s):
        a_, b_ = int(m.group(1)), m.group(2)
        out.add((a_, int(b_)) if b_ else (a_,))
    return out


def quotes_of(x) -> list[str]:
    if not x:
        return []
    if isinstance(x, str):
        return [x]
    return [q if isinstance(q, str) else q.get("quote", "") for q in x]


def words(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def chain_cases() -> list[dict]:
    out = []
    for p in sorted(CASES.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("phases"):
            out.append(d)
    return out


def check_row(d: dict, a: dict, src: dict) -> None:
    who, what = d["name"], a["what"]
    u = a.get("url")
    if u not in src:
        err(f"{who}: row {what!r} URL not in phase_sources")
        return
    kind = src[u].get("kind")
    if kind not in KINDS:
        err(f"{who}: source {u} has kind {kind!r}; must be one of {sorted(KINDS)}")
    if kind == "tribute" and not a.get("died"):
        err(f"{who}: a tribute source may back only the death row, not {what!r}")
    backing = quotes_of(a.get("evidence")) + [a.get("quote", "")] + quotes_of(a.get("label_basis"))
    backing += quotes_of(a.get("milestone")) + quotes_of(a.get("date_basis"))
    if not any(b.strip() for b in backing):
        err(f"{who}: row {what!r} has no backing line")
    for key in ("label_basis", "milestone", "date_basis"):
        for b in a.get(key) or []:
            if isinstance(b, dict) and (b.get("url") not in src or not b.get("quote")):
                err(f"{who}: row {what!r} {key} entry needs a URL in phase_sources and a quote")
    back = " ".join(backing).lower()
    # plain anatomy: body-part words and bracketed codes must be in the row's own backing
    bl = set().union(*[levels(b) for b in backing])
    for part in ANATOMY:
        if re.search(rf"\b{part}", what.lower()) and part not in back:
            if part in ("spine", "vertebra") and bl:
                continue  # a vertebra level in the backing supports plain "spine"
            err(f"{who}: row {what!r} says {part!r} but no backing line does")
    for par in re.findall(r"\(([^)]+)\)", what):
        for bit in re.split(r",\s*|\s+and\s+", par):
            rest = LEVEL_RE.sub("", bit)
            rest = re.sub(r"(?i)\bvertebrae?\b", "", rest).strip()
            if rest and rest.lower() not in back:
                err(f"{who}: row {what!r} bracket part {bit!r} is not in its backing lines")
    lab = levels(what)
    if any(lv[0] <= 3 for lv in lab):
        err(f"{who}: row {what!r} presents a time-point code (T0–T3) as a vertebra")
    for lv in lab:
        if lv not in bl:
            err(f"{who}: row {what!r} vertebra level {lv} is not in its backing lines")
    if re.search(r"spine|vertebra", what) and not re.search(r"spine|vertebra", back) and not bl:
        err(f"{who}: row {what!r} says spine/vertebra without backing")
    # dates
    when = a["when"]
    if a.get("evidence"):
        dates = []
        for row in a["evidence"]:
            m = re.match(r"(\d{4})-(\d{2})-\d{2}(?:–(\d{4})-(\d{2})-\d{2})?", row)
            if not m:
                err(f"{who}: evidence row without an ISO date: {row!r}")
                continue
            dates.append((int(m.group(1)), int(m.group(2))))
            if m.group(3):
                dates.append((int(m.group(3)), int(m.group(4))))
        start, end = dg.when_bounds(when)
        def ym(s):
            parts = s.split()
            return (int(parts[-1]), MONTHS.index(parts[-2][:3].lower()) + 1
                    if len(parts) >= 2 and parts[-2][:3].lower() in MONTHS else None)
        if dates and ym(start) != min(dates):
            err(f"{who}: {when!r} start does not match its earliest evidence row")
        if dates and not when.startswith("From ") and ym(end) != max(dates):
            err(f"{who}: {when!r} end does not match its latest evidence row")
        return
    basis = " ".join([a.get("quote", "")] + quotes_of(a.get("date_basis"))
                     + [a.get("date_note", ""), src[u].get("published", "")]).lower()
    years = re.findall(r"\b(19|20)\d{2}\b", when)
    if re.search(r"\b(19|20)\d{2}\b", when):
        for y in re.findall(r"\b(?:19|20)\d{2}\b", when):
            if y not in basis:
                err(f"{who}: row {what!r} year {y} is not in its quote, date basis, note or source date")
        for tok in re.findall(r"[A-Za-z]+", when):
            if tok[:3].lower() in MONTHS and len(tok) <= 9 and tok[:3].lower() not in basis:
                err(f"{who}: row {what!r} month {tok} is not in its backing")
        for day in re.findall(r"^(\d{1,2}) ", when):
            if not re.search(rf"\b{day}\b", basis):
                err(f"{who}: row {what!r} day {day} is not in its backing")
    else:
        need = words(re.sub(r"\([^)]*\)", "", when)) - STOP
        if not need <= words(basis) and not a.get("date_note"):
            err(f"{who}: row {what!r} time words {sorted(need - words(basis))} are not in its quote "
                "and it has no date note")
    del years


def check_case(d: dict) -> None:
    who, slug = d["name"], d["slug"]
    src = d.get("phase_sources", {})
    for u in src:
        if any(h in u for h in STAFF_HOSTS):
            err(f"{who}: staff-written source {u} must not back the chain")
    phases, links = d["phases"], d["phase_links"]
    whens = set()
    for ph in phases:
        if not ph.get("actions"):
            err(f"{who}: phase {ph.get('title')!r} has no rows")
        for a in ph["actions"]:
            whens.add(a["when"])
            check_row(d, a, src)
        if ph.get("span_label"):
            if not ph.get("span_note"):
                err(f"{who}: phase {ph['title']!r} span label needs a span_note saying where it comes from")
            for y in re.findall(r"\b(?:19|20)\d{2}\b", ph["span_label"]):
                pool = " ".join([ph.get("span_note", "")] + [a["when"] for a in ph["actions"]]
                                + [a.get("date_note", "") for a in ph["actions"]])
                if y not in pool:
                    err(f"{who}: phase {ph['title']!r} span year {y} is not in its rows or note")
    milestones = [a for ph in phases for a in ph["actions"] if "milestone" in a]
    for m in milestones:
        if not m["milestone"] or any(b.get("url") not in src or not b.get("quote") for b in m["milestone"]):
            err(f"{who}: milestone {m['what']!r} lacks a sourced backing quote")
        if m.get("died"):
            err(f"{who}: a death is never marked as a milestone")
    causes = [ln for ln in links if ln.get("cause")]
    if len(links) != len(phases) - 1:
        err(f"{who}: expected {len(phases) - 1} links between phases, found {len(links)}")
    for ln in causes:
        if not ln.get("sources") or any(s.get("url") not in src or not s.get("quote") for s in ln["sources"]):
            err(f"{who}: cause on {ln['from']}->{ln['to']} lacks a sourced quote")
        if any(src.get(s.get("url"), {}).get("kind") not in ("own", "record") for s in ln.get("sources", [])):
            err(f"{who}: cause on {ln['from']}->{ln['to']} must come from the person's own sources")
        for frag in re.findall(r"“([^”]+)”", ln["cause"]):
            f = frag.rstrip(".,")
            if not any(f in s.get("quote", "") for s in ln.get("sources", [])):
                err(f"{who}: quoted words {frag!r} on a link are not in its source quote")
    # drawing on the case page
    page = SITE / f"{slug}.html"
    if not page.is_file():
        err(f"{who}: missing case page {page.name}")
        return
    html = page.read_text(encoding="utf-8")
    m = re.search(r'<figure class="dg[^"]*" id="chain-' + re.escape(slug) + r'">(.*?)</figure>', html, re.S)
    if not m:
        err(f"{who}: chain figure #chain-{slug} missing on the case page")
        return
    fig = m.group(1)
    cap = re.search(r"<figcaption>(.*?)</figcaption>", fig, re.S)
    cap = cap.group(1) if cap else ""
    if not cap.startswith("One person’s story, not evidence that a treatment works"):
        err(f"{who}: caption must start 'One person’s story, not evidence that a treatment works'")
    pron = d.get("pronoun", "their")
    if f"a key step we picked; each one is described in {pron} own sources" not in cap:
        err(f"{who}: caption must say the milestone selection is ours")
    if CELEBRATE.search(cap):
        err(f"{who}: caption has celebration words or emoji")
    svgs = re.findall(r"<svg\b.*?</svg>", fig, re.S)
    if len(svgs) != 2 or 'class="dg-wide"' not in svgs[0] or 'class="dg-tall"' not in svgs[1]:
        err(f"{who}: chain needs a wide and a tall (mobile) svg")
    for s in svgs:
        head = re.match(r"<svg\b[^>]*>", s).group(0)
        if 'role="img"' not in head or "aria-labelledby" not in head or "viewBox" not in head:
            err(f"{who}: svg lacks role=img / aria-labelledby / viewBox")
        labels = re.findall(r">([^<>]+)</text>", s)
        joined = " ".join(labels)
        for ph in phases:
            if dg.phase_span(ph) not in joined:
                err(f"{who}: phase span {dg.phase_span(ph)!r} not drawn")
        for frag in set(re.findall(r'fill="#b02058"[^>]*>([^<]+)</text>', s)) - {"MILESTONE"}:
            if not any(frag in w for w in whens):
                err(f"{who}: draws a date {frag!r} that is not in the phase data")
        if joined.count("WHY") != len(causes):
            err(f"{who}: WHY boxes ({joined.count('WHY')}) differ from sourced causes ({len(causes)})")
        if "stroke-dasharray" in s or "reason not stated" in joined.lower():
            err(f"{who}: no dashed or 'not stated' boxes; plain arrows only")
        desc = re.search(r"<desc[^>]*>([^<]+)</desc>", s).group(1)
        if desc.count("give no reason") != len(links) - len(causes):
            err(f"{who}: description must say which links have no stated reason")
        if desc.count("Why the next phase:") != len(causes):
            err(f"{who}: description must give each sourced cause")
        if not desc.endswith("One person’s story, not evidence that a treatment works."):
            err(f"{who}: description must end with the one-person caveat")
        marks = len(re.findall(r'<rect class="ms-mark"', s))
        if marks != len(milestones) + 1:
            err(f"{who}: milestone markers ({marks - 1}) differ from milestones in the data ({len(milestones)})")
        if joined.upper().count("MILESTONE") != len(milestones) + 1 or desc.count("Milestone: ") != len(milestones):
            err(f"{who}: each milestone row (and the key) needs the word Milestone, also in the description")
        if f"described in {pron} own sources" not in joined:
            err(f"{who}: key must say each milestone is described in {pron} own sources")
        if CELEBRATE.search(joined) or CELEBRATE.search(desc):
            err(f"{who}: milestones must stay quiet: no stars, emoji or celebration words")
    ok(f"{who}: {len(phases)} phases, {len(causes)} WHY, {len(links) - len(causes)} plain arrows, "
       f"{len(milestones)} milestones")


def test_readability() -> None:
    for p in sorted(SITE.glob("*.html")):
        if p.name == "index.html":
            continue
        sc = flesch_kincaid(visible_text(p.read_text(encoding="utf-8")))
        g = sc.get("grade")
        if g is None:
            err(f"{p.name}: could not score FK grade")
        elif g > FK_MAX:
            err(f"{p.name}: FK grade {g} is above {FK_MAX}")
        else:
            ok(f"{p.name}: FK grade {g}")


def self_test() -> None:
    """The gate must catch an unbacked anatomy word, a wrong year and a stray WHY."""
    d = json.loads((CASES / "augenstein.json").read_text(encoding="utf-8"))
    before = len(errors)
    QUIET[0] = True
    a = dict(d["phases"][0]["actions"][0])
    a["what"] = "Cancer found in his liver (T4/5)"
    a["when"] = "Nov 2019"
    check_row(d, a, d["phase_sources"])
    QUIET[0] = False
    caught = errors[before:]
    del errors[before:]
    if len(caught) < 3:
        err(f"self-test: expected the gate to catch liver, T4/5 and 2019, caught {caught}")
    else:
        ok(f"self-test: a bad row is caught ({len(caught)} problems)")


def main() -> int:
    cases = chain_cases()
    if len(cases) < 5:
        err(f"expected a chain on every case (5), found {len(cases)}")
    for d in cases:
        check_case(d)
    test_readability()
    self_test()
    if errors:
        print(f"\n{len(errors)} failure(s)")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
