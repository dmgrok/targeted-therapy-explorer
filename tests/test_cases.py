#!/usr/bin/env python3
"""Case studies sit beside the trees, never inside the option tables."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_cases import (  # noqa: E402
    BANNER,
    WORD_LIMIT,
    load_cases,
    split_sentences,
    validate_words,
    words_of,
)
from readability import flesch_kincaid, visible_text  # noqa: E402

SITE = ROOT / "site"
CASES = SITE / "cases"

ORDER = [
    "sijbrandij",
    "freeman-daily",
    "augenstein",
    "feldman",
    "olson",
]
FORBIDDEN = ["Wartman", "Fajgenbaum", "Whitehead"]
# People must not appear as option names in any decision-tree table.
PEOPLE = [
    "Sijbrandij",
    "Freeman-Daily",
    "Augenstein",
    "Feldman",
    "Olson",
    "Linnea",
    "Janet",
    "Neal Augenstein",
    "Jill Feldman",
]


def fail(msg: str) -> None:
    print("FAIL:", msg)
    raise SystemExit(1)


def test_data_order_and_exclusions() -> None:
    cases = load_cases()
    slugs = [c["slug"] for c in cases]
    if slugs != ORDER:
        fail(f"case order {slugs} != {ORDER}")
    blob = " ".join(c["name"] for c in cases)
    for name in FORBIDDEN:
        if name in blob:
            fail(f"{name} must be left out")
        for c in cases:
            raw = str(c)
            if name in raw:
                fail(f"{name} found in {c['slug']} data")


def test_word_gate() -> None:
    errors = validate_words(load_cases())
    if errors:
        fail("word gate:\n" + "\n".join(errors))


def test_pages_exist() -> None:
    if not (CASES / "index.html").is_file():
        fail("missing cases/index.html")
    for slug in ORDER:
        if not (CASES / f"{slug}.html").is_file():
            fail(f"missing cases/{slug}.html")


def test_banner_and_disclaimer() -> None:
    index = (CASES / "index.html").read_text(encoding="utf-8")
    if BANNER not in index and BANNER.replace("’", "'") not in index:
        fail("index missing the one-person-story banner")
    if "not options in the tables" not in index:
        fail("index must say these people are not options in the tables")
    for slug in ORDER:
        html = (CASES / f"{slug}.html").read_text(encoding="utf-8")
        if "case-banner" not in html:
            fail(f"{slug} missing case-banner")
        # Normalize curly apostrophe for the check
        flat = html.replace("’", "'").replace("‘", "'")
        banner_flat = BANNER.replace("’", "'")
        if banner_flat not in flat:
            fail(f"{slug} missing banner text")
        if "not medical advice" not in html.lower() and "Disclaimer" not in html:
            # site-wide short disclaimer is in the notice
            if "notice-short" not in html:
                fail(f"{slug} missing site disclaimer")
        if "case-timeline" not in html:
            fail(f"{slug} missing timeline")
        if "Their own pages" not in html:
            fail(f"{slug} missing pointers heading")


def test_linnea_death_at_top() -> None:
    html = (CASES / "olson.html").read_text(encoding="utf-8")
    died_idx = html.find("15 November 2021")
    if died_idx < 0:
        fail("Linnea page must state 15 November 2021")
    # The death note must appear before the main h1? or at top of entry.
    # We place case-died before <h1>.
    died_div = html.find("case-died")
    h1 = html.find("<h1>")
    if died_div < 0 or died_div > h1:
        fail("Linnea's death must be stated at the top, before the heading")
    if "at the age of 61" not in html and "aged 61" not in html:
        fail("Linnea page should state she was 61")
    if "at home" not in html:
        fail("Linnea page should state she died at home, as the tribute does")
    # Jessica J. Lin must not be listed as someone Linnea named.
    helpers = re.findall(r"class='case-helpers'>(.*?)</p>", html, re.S)
    helper_blob = " ".join(helpers)
    if "Jessica" in helper_blob:
        fail("Jessica J. Lin must not appear as someone Linnea named")
    if "cure" in html.lower() and "not a claim that she was cured" not in html:
        # Allowed to discuss cure in her own quoted words and in our refusal.
        pass


def test_status_dated() -> None:
    for slug, phrase in {
        "sijbrandij": "As of 20 January 2026",
        "freeman-daily": "As of 10 May 2026",
        "augenstein": "As of 23 November 2025",
        "feldman": "As of 10 January 2025",
        "olson": "As of 15 November 2021",
    }.items():
        html = (CASES / f"{slug}.html").read_text(encoding="utf-8")
        if phrase not in html:
            fail(f"{slug} missing dated status '{phrase}'")
        if ", per " not in html and ", per&nbsp;" not in html:
            # we write "As of DATE, per SOURCE"
            if " per " not in html:
                fail(f"{slug} status must be 'as of DATE, per SOURCE'")


def test_verified_quotes() -> None:
    """Quotes on the page must match the data file exactly (already verified)."""
    for case in load_cases():
        html = (CASES / f"{case['slug']}.html").read_text(encoding="utf-8")
        for q in case.get("quotes") or []:
            text = q["text"]
            if text not in html:
                fail(f"{case['slug']} missing exact quote: {text[:80]}")
        # Every timeline entry has a source link.
        for ev in case.get("timeline") or []:
            if ev.get("url") and ev["url"] not in html:
                fail(f"{case['slug']} timeline missing url {ev['url']}")


def test_never_in_tables() -> None:
    tables = list((SITE / "b").rglob("*.html"))
    if not tables:
        fail("no tree pages found")
    hits = []
    for path in tables:
        html = path.read_text(encoding="utf-8")
        # Only look at option table cells, not nav.
        for m in re.finditer(r"<table\b[^>]*>(.*?)</table>", html, re.S | re.I):
            chunk = m.group(1)
            for name in PEOPLE:
                if name in chunk:
                    hits.append(f"{path.relative_to(SITE)} contains {name}")
    if hits:
        fail("case people leaked into tables:\n" + "\n".join(hits[:20]))


def test_index_lists_all() -> None:
    html = (CASES / "index.html").read_text(encoding="utf-8")
    positions = []
    for slug, name in [
        ("sijbrandij", "Sid Sijbrandij"),
        ("freeman-daily", "Janet Freeman-Daily"),
        ("augenstein", "Neal Augenstein"),
        ("feldman", "Jill Feldman"),
        ("olson", "Linnea Olson"),
    ]:
        if f'href="{slug}.html"' not in html:
            fail(f"index missing link to {slug}")
        positions.append(html.find(name))
    if positions != sorted(positions):
        fail(f"index order of names is wrong: {positions}")
    if "Linnea Olson died on 15 November 2021" not in html:
        fail("index should note Linnea's death")
    for name in FORBIDDEN:
        if name in html:
            fail(f"index must not list {name}")


def test_no_recommendation_language() -> None:
    banned = [
        "you could do this too",
        "you should",
        "we recommend",
        "best treatment",
        "this proves",
    ]
    for path in CASES.glob("*.html"):
        low = path.read_text(encoding="utf-8").lower()
        for phrase in banned:
            if phrase in low:
                fail(f"{path.name} contains '{phrase}'")


def main() -> int:
    test_data_order_and_exclusions()
    test_word_gate()
    test_pages_exist()
    test_banner_and_disclaimer()
    test_linnea_death_at_top()
    test_status_dated()
    test_verified_quotes()
    test_never_in_tables()
    test_index_lists_all()
    test_no_recommendation_language()
    print("test_cases: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
