#!/usr/bin/env python3
"""Gates for the EGFR design mockup."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from readability import visible_text  # noqa: E402

SITE = ROOT / "site"
MOCK = SITE / "mockup"
errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)
    print("FAIL:", msg)


def ok(msg: str) -> None:
    print("OK:  ", msg)


def test_click_path() -> None:
    path = [
        MOCK / "index.html",
        MOCK / "EGFR" / "index.html",
        MOCK / "EGFR" / "lung-cancer" / "index.html",
        MOCK / "EGFR" / "lung-cancer" / "egfr-exon-19-deletion-or-l858r" / "index.html",
        MOCK / "EGFR" / "lung-cancer" / "egfr-exon-19-deletion-or-l858r" / "as-a-first-treatment.html",
    ]
    for p in path:
        if not p.is_file():
            err(f"missing mockup page {p.relative_to(SITE)}")
            return
    ok("home → EGFR → lung → exon 19 / L858R → first-treatment table exists")

    home = (MOCK / "index.html").read_text(encoding="utf-8")
    if 'href="EGFR/index.html"' not in home:
        err("mockup home does not link to the EGFR tree")
    leaf = path[-1].read_text(encoding="utf-8")
    vis = visible_text(leaf)
    if "Amivantamab" not in vis or "Gefitinib" not in vis:
        err("first-treatment table is missing expected Mainstream drugs")
    if "Mobocertinib" in vis:
        err("Mobocertinib appeared on the exon 19 first-treatment leaf")
    if "<table" not in leaf:
        err("leaf page has no options table")
    for col in ("Option", "What it is", "Level", "Approved where", "Source"):
        if col not in leaf:
            err(f"table missing column {col}")
    if "Mainstream" not in vis:
        err("leaf table is missing the Mainstream level")
    ok("featured leaf is a table with the expected columns and drugs")


def test_mobocertinib_withdrawn() -> None:
    pages = list(MOCK.rglob("*.html"))
    hits = [p for p in pages if "Mobocertinib" in p.read_text(encoding="utf-8")]
    if not hits:
        err("Mobocertinib is not on any mockup page")
        return
    for p in hits:
        html = p.read_text(encoding="utf-8")
        vis = visible_text(html)
        if "Mobocertinib" not in vis:
            continue
        # Must not be tagged Mainstream next to the drug in the visible layer.
        # The word Mainstream still appears in the level legend.
        # The withdrawn article/row must carry the Withdrawn tag.
        if "Withdrawn" not in vis:
            err(f"{p.relative_to(SITE)}: Mobocertinib is visible without a Withdrawn tag")
        if "Federal Register" not in html and "federalregister.gov" not in html:
            err(f"{p.relative_to(SITE)}: withdrawal source is missing")
        # The options table row should not say Mainstream for this drug.
        window = vis[vis.find("Mobocertinib"): vis.find("Mobocertinib") + 280]
        if "Mainstream" in window and "not tagged Mainstream" not in window and "Withdrawn" not in window:
            err(f"{p.relative_to(SITE)}: Mobocertinib looks Mainstream in visible text: {window!r}")
    ok(f"Mobocertinib is shown as withdrawn on {len(hits)} page(s), with a source")


def test_visible_layer() -> None:
    for p in MOCK.rglob("*.html"):
        html = p.read_text(encoding="utf-8")
        vis = visible_text(html)
        rel = p.relative_to(SITE)
        if "Not medical advice. Talk to your oncologist." not in html:
            err(f"{rel}: missing disclaimer")
        if "2026-11-10T" in vis:
            err(f"{rel}: ISO timestamp is visible")
        if re.search(r"\bTIER_[IVX]", vis) or "ampLevel" in vis:
            err(f"{rel}: CIViC / AMP codes are visible")
        if "ChiCTR" in html or "NCCN" in html or re.search(r"\bESMO\b", html):
            err(f"{rel}: forbidden source")
    ok("mockup visible layer has a disclaimer, no ISO date, no AMP/CIViC codes")


def test_no_js_required() -> None:
    leaf = (
        MOCK / "EGFR" / "lung-cancer" / "egfr-exon-19-deletion-or-l858r" / "as-a-first-treatment.html"
    ).read_text(encoding="utf-8")
    # Relative links, static table, sources in details.
    if "<table" not in leaf or "<details" not in leaf:
        err("leaf is not a static table with Sources details")
    if 'href="../index.html"' not in leaf and "Change the gene change" not in leaf:
        err("leaf has no static way back up the tree")
    ok("leaf works as a static page with Sources <details>")


def main() -> int:
    if not MOCK.is_dir():
        err("site/mockup is missing — run scripts/build_mockup.py")
        print("FAIL")
        return 1
    test_click_path()
    test_mobocertinib_withdrawn()
    test_visible_layer()
    test_no_js_required()
    if errors:
        print(f"\n{len(errors)} FAIL(S)")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
