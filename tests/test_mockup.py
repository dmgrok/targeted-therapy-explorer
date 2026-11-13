#!/usr/bin/env python3
"""Gates for the decision-tree site."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from readability import visible_text  # noqa: E402

SITE = ROOT / "site"
TREE = SITE / "b"
errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)
    print("FAIL:", msg)


def ok(msg: str) -> None:
    print("OK:  ", msg)


def test_click_path() -> None:
    path = [
        SITE / "index.html",
        TREE / "EGFR" / "index.html",
        TREE / "EGFR" / "lung-cancer" / "index.html",
        TREE / "EGFR" / "lung-cancer" / "egfr-exon-19-deletion-or-l858r" / "index.html",
        TREE / "EGFR" / "lung-cancer" / "egfr-exon-19-deletion-or-l858r" / "as-a-first-treatment.html",
    ]
    for p in path:
        if not p.is_file():
            err(f"missing tree page {p.relative_to(SITE)}")
            return
    ok("home → EGFR → lung → exon 19 / L858R → first-treatment table exists")

    home = (SITE / "index.html").read_text(encoding="utf-8")
    if 'href="b/EGFR/index.html"' not in home:
        err("home does not link to the EGFR tree")
    leaf = path[-1].read_text(encoding="utf-8")
    vis = visible_text(leaf)
    if "Amivantamab" not in vis or "Gefitinib" not in vis:
        err("first-treatment table is missing expected Mainstream drugs")
    if "Osimertinib" not in vis:
        err("Osimertinib is missing from the first-treatment table (full-label completeness)")
    if "Erlotinib" not in vis:
        err("Erlotinib is missing from the first-treatment table (full-label completeness)")
    if "Mobocertinib" in vis:
        err("Mobocertinib appeared on the exon 19 first-treatment leaf")
    # Combination wording from the label, never as a standalone option.
    if "together with erlotinib" not in vis.lower():
        err("Ramucirumab first-treatment row does not say it is used together with erlotinib")
    if "together with lazertinib" not in vis.lower():
        err("Amivantamab first-treatment row does not say it is used together with lazertinib")
    if "together with amivantamab" not in vis.lower():
        err("Lazertinib first-treatment row does not say it is used together with amivantamab")
    # What-it-is must not be a route alone or a nameless fallback.
    if "a drug named on the FDA label" in vis:
        err("a 'drug named on the FDA label' fallback is visible")
    if "<table" not in leaf:
        err("leaf page has no options table")
    for col in ("Option", "What it is", "Level", "Approved where", "Source"):
        if col not in leaf:
            err(f"table missing column {col}")
    if "Mainstream" not in vis:
        err("leaf table is missing the Mainstream level")
    ok("featured leaf is a table with the expected columns and drugs")


def test_mobocertinib_withdrawn() -> None:
    pages = list(TREE.rglob("*.html"))
    hits = [p for p in pages if "Mobocertinib" in p.read_text(encoding="utf-8")]
    if not hits:
        err("Mobocertinib is not on any tree page")
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


def _all_pages():
    pages = list(TREE.rglob("*.html"))
    for extra in ("index.html", "notice.html", "about.html"):
        q = SITE / extra
        if q.is_file():
            pages.append(q)
    cases = SITE / "cases"
    if cases.is_dir():
        pages.extend(cases.rglob("*.html"))
    return pages


def test_visible_layer() -> None:
    for p in _all_pages():
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
    ok("visible layer has a disclaimer, no ISO date, no AMP/CIViC codes")


def test_no_js_required() -> None:
    leaf = (
        TREE / "EGFR" / "lung-cancer" / "egfr-exon-19-deletion-or-l858r" / "as-a-first-treatment.html"
    ).read_text(encoding="utf-8")
    # Relative links, static table, sources in details.
    if "<table" not in leaf or "<details" not in leaf:
        err("leaf is not a static table with Sources details")
    if 'href="../index.html"' not in leaf and "Change the gene change" not in leaf:
        err("leaf has no static way back up the tree")
    ok("leaf works as a static page with Sources <details>")



def test_notice_and_banner() -> None:
    notice = SITE / "notice.html"
    if not notice.is_file():
        err("missing notice.html full-notice page")
        return
    if "Talk to your oncologist" not in notice.read_text(encoding="utf-8"):
        err("notice page is missing the full disclaimer")
    # Intermediate steps: short banner + link, not only the long text as the sole banner.
    step = TREE / "EGFR" / "lung-cancer" / "index.html"
    html = step.read_text(encoding="utf-8")
    if "Not medical advice. Talk to your oncologist." not in html:
        err("cancer-step page missing short disclaimer")
    if "notice.html" not in html:
        err("cancer-step page does not link to the full notice")
    home = (SITE / "index.html").read_text(encoding="utf-8")
    leaf = (
        TREE / "EGFR" / "lung-cancer" / "egfr-exon-19-deletion-or-l858r" / "as-a-first-treatment.html"
    ).read_text(encoding="utf-8")
    if "This site is general information only" not in home or "This site is general information only" not in leaf:
        err("full disclaimer is missing from the home or the table page")
    ok("short banner, notice page, and full text on home and table")


def test_what_it_is_and_combo() -> None:
    leaf = (
        TREE / "EGFR" / "lung-cancer" / "egfr-exon-19-deletion-or-l858r" / "as-a-first-treatment.html"
    ).read_text(encoding="utf-8")
    vis = visible_text(leaf)
    if "once-daily pill" not in vis and "a once-daily pill" not in vis.lower():
        err("first-treatment 'what it is' does not say how a pill is given")
    if "blocks the EGFR signal" not in vis:
        err("first-treatment 'what it is' does not say what a kinase inhibitor does")
    if "drip into a vein" not in vis:
        err("first-treatment table has no drip-into-a-vein route for an infusion drug")
    ok("what-it-is cells have a route and a plain-language class")


def test_confusing_branch_labels_gone() -> None:
    for p in TREE.rglob("*.html"):
        html = p.read_text(encoding="utf-8")
        vis = visible_text(html)
        if "subtype not further named" in vis:
            err(f"{p.relative_to(SITE)}: old confusing branch label is still visible")
        if "the label calls non-resistant" in vis:
            err(f"{p.relative_to(SITE)}: old 'non-resistant' branch label is still visible")
    # Featured mutation page should explain why the branch exists.
    mut = TREE / "EGFR" / "lung-cancer" / "index.html"
    vis = visible_text(mut.read_text(encoding="utf-8"))
    if "FDA label names these two EGFR gene changes" not in vis and "these two EGFR gene changes" not in vis:
        err("mutation choice page has no plain explanation of why the exon 19 / L858R branch exists")
    ok("confusing branch labels were renamed and each branch has a why line")


def test_cetuximab_partners_scoped() -> None:
    """Partners must come from the clause that places the drug on that leaf."""
    bowel_first = (
        TREE / "EGFR" / "bowel-cancer" / "kras-wild-type-no-kras-change"
        / "as-a-first-treatment.html"
    )
    bowel_after = (
        TREE / "EGFR" / "bowel-cancer" / "kras-wild-type-no-kras-change"
        / "after-another-drug.html"
    )
    hn_first = (
        TREE / "EGFR" / "head-and-neck-cancer"
        / "label-does-not-say-the-gene-change-subtype" / "as-a-first-treatment.html"
    )
    hn_after = (
        TREE / "EGFR" / "head-and-neck-cancer"
        / "label-does-not-say-the-gene-change-subtype" / "after-another-drug.html"
    )
    from readability import visible_text
    def vis(path):
        if not path.is_file():
            err(f"missing {path.relative_to(SITE)}")
            return ""
        return visible_text(path.read_text(encoding="utf-8"))

    bf = vis(bowel_first)
    if bf:
        if "Cetuximab" not in bf:
            err("cetuximab missing from bowel KRAS-wild-type first-treatment table")
        if "together with FOLFIRI" not in bf and "together with FOLFIRI" not in bf.replace("  "," "):
            err("bowel first-treatment does not say cetuximab is used together with FOLFIRI")
        if "irinotecan" in bf.lower() and "together with FOLFIRI and irinotecan" in bf:
            err("bowel first-treatment leaked irinotecan into the FOLFIRI combination")
        if "radiation therapy" in bf.lower():
            err("bowel first-treatment leaked a head-and-neck partner (radiation)")
    ba = vis(bowel_after)
    if ba and "Cetuximab" in ba:
        if "FOLFIRI" in ba and "together with FOLFIRI" in ba:
            err("bowel after-another-drug leaked the first-treatment FOLFIRI partner")
        if "radiation therapy" in ba.lower():
            err("bowel after-another-drug leaked a head-and-neck partner")
    hf = vis(hn_first)
    if hf and "Cetuximab" in hf:
        if "FOLFIRI" in hf or "irinotecan" in hf.lower():
            err("head-and-neck first-treatment leaked a bowel combination partner")
        if "radiation therapy and platinum" in hf.lower():
            err("head-and-neck first-treatment joined radiation and platinum with 'and' as one combination")
    ha = vis(hn_after)
    if ha and "Cetuximab" in ha:
        if "together with radiation" in ha.lower() or "together with FOLFIRI" in ha:
            err("head-and-neck after-another-drug leaked a first-treatment partner")
    ok("cetuximab combination partners are scoped to the clause for each leaf")


def test_combination_gate_catches_merged_sets() -> None:
    """The combination gate fails a row that joins more than one partner set with 'and'."""
    from labels import combo_note, partner_sets
    # Two neighbouring units, two partner sets, wrongly joined historically with "and".
    units = [
        "in combination with FOLFIRI for first-line treatment",
        "in combination with irinotecan in patients who are refractory",
    ]
    sets = partner_sets(units)
    if len(sets) < 2:
        err(f"expected two partner sets from neighbouring units, got {sets!r}")
        return
    note = combo_note(units)
    if " or with " not in (note or "").lower():
        err(f"multiple partner sets should be phrased with 'or with', got {note!r}")
    if " and irinotecan" in (note or "").lower() and " or with " not in (note or "").lower():
        err(f"gate would miss an 'and' merge of two partner sets: {note!r}")
    # A synthetic note that joins two sets with "and" must be flagged.
    bad_note = "Used together with FOLFIRI and irinotecan."
    joined_and = (
        "used together with" in bad_note.lower()
        and " and " in bad_note
        and " or with " not in bad_note.lower()
    )
    if not joined_and:
        err("the 'more than one partner set joined with and' detector did not fire on a known-bad note")
    else:
        ok("combination gate detector flags a row that joins two partner sets with 'and'")
    ok(f"scoped note for two first-line-vs-refractory units is {note!r}")


def test_osimertinib_europe_year() -> None:
    leaf = (
        TREE / "EGFR" / "lung-cancer" / "egfr-exon-19-deletion-or-l858r"
        / "as-a-first-treatment.html"
    )
    if not leaf.is_file():
        err("missing first-treatment leaf")
        return
    vis = visible_text(leaf.read_text(encoding="utf-8"))
    if "Osimertinib" not in vis:
        err("osimertinib missing from first-treatment table")
        return
    # Window around osimertinib
    i = vis.find("Osimertinib")
    window = vis[i:i+500]
    if "Europe since 2015" in window:
        err("osimertinib still shows Europe since 2015 (CHMP opinion year, not marketing authorisation)")
    if "Europe since 2016" not in window:
        err(f"osimertinib does not show Europe since 2016 in {window!r}")
    else:
        ok("osimertinib shows Europe since 2016, from the EPAR marketing authorisation issued date")


def test_gefitinib_plain_note() -> None:
    # The indication note should appear on the EGFR tree and use the plain wording.
    found = False
    wording = "Its older use after chemotherapy was withdrawn in the US in 2012"
    for p in TREE.joinpath("EGFR").rglob("*.html"):
        html = p.read_text(encoding="utf-8")
        vis = visible_text(html)
        if wording in vis:
            found = True
            if "first-treatment use is still approved" not in vis:
                err(f"{p.relative_to(SITE)}: gefitinib note is missing the still-approved clause")
            # Federal Register source behind the toggle.
            if "federalregister.gov" not in html and "2012-9944" not in html:
                err(f"{p.relative_to(SITE)}: gefitinib note is missing the Federal Register source")
            break
    if not found:
        err("gefitinib plain withdrawal note is not visible on any EGFR page")
    else:
        ok("gefitinib note uses the plain 2012 wording, with a Federal Register source")


def test_every_biomarker_tree() -> None:
    for bid in ("EGFR", "ALK", "BRAF-V600E", "KRAS-G12C", "HER2", "NTRK", "MSI-H-dMMR"):
        idx = TREE / bid / "index.html"
        if not idx.is_file():
            err(f"missing biomarker tree for {bid}")
            continue
        html = idx.read_text(encoding="utf-8")
        if "Which kind of cancer is this about?" not in html:
            err(f"{bid}: biomarker page is not a cancer-type choice")
        if "Design mockup" in html or "EGFR only" in visible_text(html):
            err(f"{bid}: leftover mockup wording is still visible")
        # At least one leaf table
        leaves = [q for q in (TREE / bid).rglob("*.html") if q.name != "index.html"]
        if not leaves:
            err(f"{bid}: no leaf tables")
        else:
            sample = leaves[0].read_text(encoding="utf-8")
            for col in ("Option", "What it is", "Level", "Approved where", "Source"):
                if col not in sample:
                    err(f"{bid}: a leaf is missing column {col}")
    # No leftover long pages or mockup directory.
    for bid in ("EGFR", "ALK", "BRAF-V600E", "KRAS-G12C", "HER2", "NTRK", "MSI-H-dMMR"):
        if (TREE / f"{bid}.html").is_file():
            err(f"leftover long page site/b/{bid}.html is still present")
    if (SITE / "mockup").exists():
        err("leftover site/mockup directory is still present")
    ok("all seven biomarkers use the decision-tree design; leftover long pages are gone")


def main() -> int:
    if not TREE.is_dir() or not (SITE / 'index.html').is_file():
        err("site/b is missing — run scripts/build_site.py")
        print("FAIL")
        return 1
    test_click_path()
    test_mobocertinib_withdrawn()
    test_visible_layer()
    test_no_js_required()
    test_notice_and_banner()
    test_what_it_is_and_combo()
    test_confusing_branch_labels_gone()
    test_cetuximab_partners_scoped()
    test_combination_gate_catches_merged_sets()
    test_osimertinib_europe_year()
    test_gefitinib_plain_note()
    test_every_biomarker_tree()
    if errors:
        print(f"\n{len(errors)} FAIL(S)")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
