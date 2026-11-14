#!/usr/bin/env python3
"""Build the Case studies pages from data/cases/*.json.

These pages are kept separate from the decision trees. A case study is
one published person's story. It is not evidence that a treatment
works, and the people are never options in the tables.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_mockup import crumbs, page_shell, sources_block, write  # noqa: E402
from build_site import esc  # noqa: E402

CASES_DIR = ROOT / "data" / "cases"
SITE = ROOT / "site" / "cases"

BANNER = "This is one person’s story, not evidence that a treatment works."
BANNER_EXTRA = (
    "It is not medical advice, a recommendation, or a ranking. "
    "The people on these pages are not options in the tables."
)
INDEX_LEDE = (
    "These pages retell one published person’s story, in plain language. "
    "A case study is not evidence that a treatment works. "
    "It is not medical advice. These people are not options in the tables."
)
WORD_LIMIT = 28


def words_of(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", text or "")


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"[.!?]+", text)
    return [p.strip() for p in parts if re.search(r"[A-Za-z]", p or "")]


def load_cases() -> list[dict]:
    cases = []
    for path in sorted(CASES_DIR.glob("*.json")):
        cases.append(json.loads(path.read_text(encoding="utf-8")))
    cases.sort(key=lambda c: (c.get("order") or 99, c.get("slug") or ""))
    return cases


def prose_fields(case: dict) -> list[tuple[str, str]]:
    """Our words, not quoted words from the person."""
    out = []
    for i, s in enumerate(case.get("summary") or []):
        out.append((f"summary[{i}]", s))
    died = case.get("died") or {}
    if died.get("text"):
        out.append(("died.text", died["text"]))
    if case.get("status", {}).get("note"):
        out.append(("status.note", case["status"]["note"]))
    for i, ev in enumerate(case.get("timeline") or []):
        out.append((f"timeline[{i}].decision", ev.get("decision") or ""))
    return out


def validate_words(cases: list[dict]) -> list[str]:
    errors = []
    for case in cases:
        slug = case.get("slug") or "?"
        for loc, text in prose_fields(case):
            for sent in split_sentences(text):
                n = len(words_of(sent))
                if n > WORD_LIMIT:
                    errors.append(
                        f"{slug} {loc}: {n} words (limit {WORD_LIMIT}): {sent}"
                    )
    return errors


def case_banner() -> str:
    return (
        f'<div class="case-banner" role="note">'
        f"<strong>{esc(BANNER)}</strong> {esc(BANNER_EXTRA)}"
        f"</div>"
    )


def quote_block(q: dict) -> str:
    text = (q.get("text") or "").strip()
    if not text:
        return ""
    opened = q.get("opened") or ""
    label = q.get("label") or "source"
    url = q.get("url") or ""
    cite = f'<a href="{esc(url)}">{esc(label)}</a>' if url else esc(label)
    opened_h = f" Page opened {esc(opened)}." if opened else ""
    return (
        "<blockquote class='case-quote'>"
        f"<p>{esc(text)}</p>"
        f"<footer>Per {cite}.{opened_h}</footer>"
        "</blockquote>"
    )


def timeline_html(case: dict) -> str:
    items = []
    for ev in case.get("timeline") or []:
        helpers = ev.get("helpers") or []
        help_h = ""
        if helpers:
            help_h = (
                "<p class='case-helpers'>Who they named: "
                + esc("; ".join(helpers))
                + ".</p>"
            )
        url = ev.get("url") or ""
        label = ev.get("label") or "source"
        opened = ev.get("opened") or ""
        src = (
            f'<p class="fine"><a href="{esc(url)}">{esc(label)}</a>'
            f"{', opened ' + esc(opened) if opened else ''}.</p>"
        )
        items.append(
            "<li>"
            f"<p class='case-date'>{esc(ev.get('date') or '')}</p>"
            f"<p>{esc(ev.get('decision') or '')}</p>"
            + help_h
            + src
            + "</li>"
        )
    if not items:
        return ""
    return (
        "<h2>Timeline</h2>"
        "<p class='fine'>Dates are only as precise as the source. "
        "A name appears only when that person or place is named on the "
        "linked public page.</p>"
        f"<ol class='case-timeline'>{''.join(items)}</ol>"
    )


def status_html(case: dict) -> str:
    st = case.get("status") or {}
    if not st:
        return ""
    as_of = st.get("as_of") or ""
    label = st.get("label") or "source"
    url = st.get("url") or ""
    opened = st.get("opened") or ""
    quote = (st.get("quote") or "").strip()
    note = (st.get("note") or "").strip()
    cite = f'<a href="{esc(url)}">{esc(label)}</a>' if url else esc(label)
    body = (
        f"<p>As of {esc(as_of)}, per {cite}"
        f"{', opened ' + esc(opened) if opened else ''}.</p>"
    )
    if quote:
        body += f"<blockquote class='case-quote'><p>{esc(quote)}</p></blockquote>"
    if note:
        body += f"<p>{esc(note)}</p>"
    return "<h2>Status</h2>" + body


def pointers_html(case: dict) -> str:
    items = []
    for p in case.get("pointers") or []:
        items.append(
            f'<li><a href="{esc(p.get("url") or "")}">{esc(p.get("label") or p.get("url"))}</a></li>'
        )
    if not items:
        return ""
    whose = "their"
    name = case.get("name") or ""
    # "his" / "her" is easy to get wrong; keep it neutral.
    return (
        f"<h2>Their own pages</h2>"
        f"<p class='fine'>Read {esc(name)}’s story on the pages they, "
        "or a page that publishes their words, made public.</p>"
        f"<ul class='case-pointers'>{''.join(items)}</ul>"
    )


def died_html(case: dict) -> str:
    died = case.get("died") or {}
    if not died:
        return ""
    text = died.get("text") or ""
    url = died.get("url") or ""
    label = died.get("label") or "source"
    opened = died.get("opened") or ""
    quote = (died.get("quote") or "").strip()
    quote2 = (died.get("quote2") or "").strip()
    also = died.get("also") or {}
    src = (
        f'<p class="fine"><a href="{esc(url)}">{esc(label)}</a>'
        f"{', opened ' + esc(opened) if opened else ''}.</p>"
    )
    q = ""
    if quote:
        q += f"<blockquote class='case-quote'><p>{esc(quote)}</p></blockquote>"
    if quote2:
        q += f"<blockquote class='case-quote'><p>{esc(quote2)}</p></blockquote>"
    also_h = ""
    if also:
        also_h = (
            f'<p class="fine">Also given as {esc(died.get("date") or "")} on '
            f'<a href="{esc(also.get("url") or "")}">{esc(also.get("label") or "another public page")}</a>'
            f"{', opened ' + esc(also.get('opened') or '') if also.get('opened') else ''}."
            f" {esc(also.get('note') or '')}</p>"
        )
    return (
        f'<div class="case-died" role="note">'
        f"<p><strong>{esc(text)}</strong></p>"
        + q
        + src
        + also_h
        + "</div>"
    )


def sources_list(case: dict) -> str:
    seen = []
    rows = []

    def add(url, label, opened):
        if not url or url in seen:
            return
        seen.append(url)
        rows.append((url, label or url, opened or ""))

    for q in case.get("quotes") or []:
        add(q.get("url"), q.get("label"), q.get("opened"))
    for ev in case.get("timeline") or []:
        add(ev.get("url"), ev.get("label"), ev.get("opened"))
    st = case.get("status") or {}
    add(st.get("url"), st.get("label"), st.get("opened"))
    died = case.get("died") or {}
    add(died.get("url"), died.get("label"), died.get("opened"))
    if died.get("also"):
        add(died["also"].get("url"), died["also"].get("label"), died["also"].get("opened"))
    for p in case.get("pointers") or []:
        add(p.get("url"), p.get("label"), "")
    if not rows:
        return ""
    items = "".join(
        f"<li><a href='{esc(u)}'>{esc(lab)}</a>"
        f"{' — opened ' + esc(op) if op else ''}.</li>"
        for u, lab, op in rows
    )
    inner = f"<ul>{items}</ul>"
    return sources_block(inner, "Sources opened for this page")


def case_body(case: dict) -> str:
    parts = [case_banner()]
    died = died_html(case)
    if died:
        parts.append(died)
    parts.append(f"<h1>{esc(case['name'])}</h1>")
    if case.get("short"):
        parts.append(f"<p class='lede'>{esc(case['short'])}</p>")
    parts.append("<h2>Summary</h2>")
    parts.append("".join(f"<p>{esc(s)}</p>" for s in case.get("summary") or []))
    quotes = "".join(quote_block(q) for q in case.get("quotes") or [])
    if quotes:
        parts.append("<h2>In their own words</h2>")
        parts.append(quotes)
    parts.append(timeline_html(case))
    parts.append(status_html(case))
    parts.append(pointers_html(case))
    parts.append(sources_list(case))
    if case.get("slug") == "sijbrandij":
        parts.append(
            '<p class="fine">A shorter telling of this story, with the same '
            "verified-quote rules, is on the "
            '<a href="../index.html#sid-sijbrandij">steps page</a>.</p>'
        )
    return "\n".join(parts)


def index_body(cases: list[dict]) -> str:
    items = []
    for c in cases:
        died_bit = ""
        if c.get("died"):
            died_bit = (
                f'<p class="fine">{esc(c["name"])} died on '
                f'{esc(c["died"]["date"])}.</p>'
            )
        items.append(
            "<li>"
            f'<a class="choice" href="{esc(c["slug"])}.html">'
            f'<span class="choice-name">{esc(c["name"])}</span>'
            f'<span class="choice-n">{esc(c.get("short") or "")}</span>'
            "</a>"
            + died_bit
            + "</li>"
        )
    return (
        case_banner()
        + "<h1>Case studies</h1>"
        + f"<p class='lede'>{esc(INDEX_LEDE)}</p>"
        + "<p>Each page has a short summary, a dated timeline of decisions, "
        "and links to that person’s own public pages. A name of a doctor or "
        "a hospital appears only when they named that person or place in public.</p>"
        + "<ul class='choices case-choices'>"
        + "".join(items)
        + "</ul>"
        + '<p>The <a href="../index.html#sid-sijbrandij">steps page</a> also '
        "tells Sid Sijbrandij’s story, briefly, as one person’s example. "
        "It is not evidence that a treatment works.</p>"
    )


def build(snap: dict) -> dict:
    cases = load_cases()
    errors = validate_words(cases)
    if errors:
        raise SystemExit("Case word-count gate failed:\n" + "\n".join(errors))

    SITE.mkdir(parents=True, exist_ok=True)
    # Drop any leftover case page whose data file was removed.
    wanted = {c["slug"] + ".html" for c in cases} | {"index.html"}
    for path in SITE.glob("*.html"):
        if path.name not in wanted:
            path.unlink()

    crumbs_index = crumbs(
        [("../index.html", "Home"), ("", "Case studies")],
        1,
    )
    write(
        SITE / "index.html",
        page_shell("Case studies", 1, snap, index_body(cases), crumbs_index),
    )
    for case in cases:
        crumbs_c = crumbs(
            [
                ("../index.html", "Home"),
                ("index.html", "Case studies"),
                ("", case["name"]),
            ],
            1,
        )
        title = f"{case['name']} — Case study"
        write(
            SITE / f"{case['slug']}.html",
            page_shell(title, 1, snap, case_body(case), crumbs_c),
        )
    return {"pages": 1 + len(cases), "cases": [c["slug"] for c in cases]}


def main() -> int:
    snap = json.loads((ROOT / "data" / "snapshot.json").read_text(encoding="utf-8"))
    report = build(snap)
    print(
        f"Wrote {report['pages']} case pages: " + ", ".join(report["cases"])
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
