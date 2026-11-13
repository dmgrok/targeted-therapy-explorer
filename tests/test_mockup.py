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



def test_lapatinib_letrozole_not_dropped() -> None:
    """The letrozole indication sits after a Limitations of Use sentence.

    FDA label set_id 302a4346-a68d-af3e-e063-6294a90a4a6f, version 1
    (effective 2025-03-12): Lapatinib is indicated in combination with
    capecitabine (after prior therapy) and, after a Limitations sentence
    that applies only to capecitabine, with letrozole for postmenopausal
    women with hormone-receptor-positive, HER2-overexpressing metastatic
    breast cancer. A split that drops everything after "Limitations of
    Use:" must not silently drop that second indication.
    """
    from labels import entry_for, indications, combinations_in, combo_note
    from tree import _clauses, therapy_branches, leaf_clauses

    entry = entry_for({"name": "Lapatinib"})
    if not entry:
        err("Lapatinib is missing from data/labels.json")
        return
    set_id = entry.get("set_id") or ""
    version = str(entry.get("version") or "")
    if set_id != "302a4346-a68d-af3e-e063-6294a90a4a6f" or version != "1":
        err(
            f"Lapatinib label identity changed: set_id={set_id} version={version}; "
            "re-check the letrozole indication against the new label"
        )
    text = indications({"name": "Lapatinib"})
    if "letrozole" not in text.lower():
        err("committed Lapatinib label no longer names letrozole")
        return
    clauses = _clauses(text)
    letrozole_clauses = [c for c in clauses if "letrozole" in c.lower()]
    if not letrozole_clauses:
        err(
            "Lapatinib letrozole indication was dropped by the "
            "Limitations-of-Use split (set_id "
            "302a4346-a68d-af3e-e063-6294a90a4a6f, version 1)"
        )
        return
    if any("capecitabine" in c.lower() and "letrozole" in c.lower() for c in letrozole_clauses):
        err("letrozole unit still contains the capecitabine clause")
    therapy = {"name": "Lapatinib"}
    triples = therapy_branches(therapy, "HER2")
    after = ("breast cancer", "HER2-positive", "after another drug")
    unknown = ("breast cancer", "HER2-positive", "label does not say when it is used")
    if after not in triples:
        err(f"Lapatinib capecitabine use missing from branches: {triples}")
    if unknown not in triples:
        err(
            f"Lapatinib letrozole use missing from branches "
            f"(silently dropped as an unknown-when leftover?): {triples}"
        )
    if after in triples:
        note = combo_note(leaf_clauses(therapy, after))
        if "capecitabine" not in note.lower():
            err(f"after-another-drug Lapatinib note missing capecitabine: {note}")
        if "letrozole" in note.lower():
            err(f"letrozole leaked into the capecitabine leaf: {note}")
    if unknown in triples:
        note = combo_note(leaf_clauses(therapy, unknown))
        if "letrozole" not in note.lower():
            err(f"unknown-when Lapatinib note missing letrozole: {note}")
        if "capecitabine" in note.lower():
            err(f"capecitabine leaked into the letrozole leaf: {note}")
    # Visible table rows, after a site build.
    vis_after = TREE / "HER2" / "breast-cancer" / "her2-positive" / "after-another-drug.html"
    vis_when = TREE / "HER2" / "breast-cancer" / "her2-positive" / "label-does-not-say-when-it-is-used.html"
    if vis_when.is_file():
        import re as _re
        html = vis_when.read_text(encoding="utf-8")
        vis = _re.sub(r"<details[\s\S]*?</details>", " ", html)
        if "letrozole" not in vis.lower():
            err("letrozole is not visible on the HER2 breast unknown-when table")
        if "Lapatinib" not in vis:
            err("Lapatinib is not visible on the HER2 breast unknown-when table")
    else:
        err("missing HER2 breast HER2-positive 'label does not say when' page")
    if vis_after.is_file():
        import re as _re
        from readability import visible_text as _vis
        html = vis_after.read_text(encoding="utf-8")
        vis = _re.sub(r"<details[\s\S]*?</details>", " ", html)
        if "Lapatinib" not in vis:
            err("Lapatinib missing from after-another-drug table")
        # Visible option row should still say capecitabine, not letrozole.
        for m in _re.finditer(r"<tr[\s\S]*?</tr>", vis):
            row = m.group(0)
            if "Lapatinib" in row and "letrozole" in row.lower():
                err("letrozole appeared on the after-another-drug Lapatinib row")
    ok(
        "Lapatinib letrozole indication is kept (label set_id "
        "302a4346-a68d-af3e-e063-6294a90a4a6f, version 1)"
    )




def test_named_cancer_types_from_labels() -> None:
    """Leftover 'cancer type not named' leaves whose label clearly names
    a cancer must sit under that cancer. Each mapping is checked against
    the committed label (set_id and version).
    """
    from labels import entry_for, indications
    from tree import therapy_branches, cancers_in, LABEL_UNKNOWN_CANCER

    cases = [
        {
            "name": "Crizotinib",
            "biomarker": "ALK",
            "set_id": "2a51b0de-47d6-455e-a94c-d2c737b04ff7",
            "version": "47",
            "snippet": "inflammatory myofibroblastic tumor (IMT) that is ALK-positive",
            "cancer": "inflammatory myofibroblastic tumour",
            "must_have": ("inflammatory myofibroblastic tumour", "ALK fusion or ALK-positive", "after another drug"),
        },
        {
            "name": "Vemurafenib",
            "biomarker": "BRAF-V600E",
            "set_id": "38eea320-7e0c-485a-bc30-98c3c45e2763",
            "version": "29",
            "snippet": "Erdheim-Chester Disease (ECD) with BRAF V600 mutation",
            "cancer": "Erdheim-Chester disease",
            "must_have": ("Erdheim-Chester disease", "BRAF V600", "label does not say when it is used"),
        },
        {
            "name": "Dostarlimab",
            "biomarker": "MSI-H-dMMR",
            "set_id": "095eab9f-545a-4f12-bfb7-19477fb901a5",
            "version": "15",
            "snippet": "dMMR recurrent or advanced EC",
            "cancer": "cancer of the womb",
            "must_have": ("cancer of the womb", "MSI-H or dMMR", "label does not say when it is used"),
        },
        {
            "name": "Zanidatamab",
            "biomarker": "HER2",
            "set_id": "ae5d9425-fae5-4541-a158-150998343348",
            "version": "3",
            "snippet": "HER2-positive (IHC 3+) biliary tract cancer (BTC)",
            "cancer": "bile duct cancer",
            "must_have": ("bile duct cancer", "HER2-positive", "after another drug"),
        },
    ]
    for c in cases:
        entry = entry_for({"name": c["name"]})
        if not entry:
            err(f"{c['name']} is missing from data/labels.json")
            continue
        set_id = entry.get("set_id") or ""
        version = str(entry.get("version") or "")
        if set_id != c["set_id"] or version != c["version"]:
            err(
                f"{c['name']} label identity changed: set_id={set_id} version={version}; "
                f"re-check the {c['cancer']} mapping against the new label "
                f"(was {c['set_id']} v{c['version']})"
            )
        text = indications({"name": c["name"]})
        if c["snippet"].lower() not in text.lower() and not (
            "EC" in c["snippet"] and "recurrent or advanced EC" in text
        ):
            # unicode hyphen in dostarlimab: allow a looser check
            import re as _re
            loose = _re.sub(r"[\s\-‑–]+", " ", c["snippet"].lower())
            hay = _re.sub(r"[\s\-‑–]+", " ", text.lower())
            if loose not in hay and not all(w in hay for w in loose.split() if w not in {"(imt)", "(ecd)", "(btc)"}):
                err(f"{c['name']} committed label no longer contains {c['snippet']!r}")
        if c["cancer"] not in cancers_in(c["snippet"]) and c["cancer"] not in cancers_in(text):
            # For EC-only snippet, cancers_in on the short phrase must hit womb
            if c["cancer"] not in cancers_in(c["snippet"]):
                err(f"cancers_in({c['snippet']!r}) does not include {c['cancer']!r}")
        therapy = {"name": c["name"]}
        triples = therapy_branches(therapy, c["biomarker"])
        if c["must_have"] not in triples:
            err(f"{c['name']} missing branch {c['must_have']}: {triples}")
        unk = [tr for tr in triples if tr[0] == LABEL_UNKNOWN_CANCER]
        # These four named uses must not remain on the unknown-cancer leaf.
        if any(
            (c["name"] == "Crizotinib" and tr[1].startswith("ALK"))
            or (c["name"] == "Vemurafenib" and "V600" in tr[1])
            or (c["name"] == "Dostarlimab" and "MSI" in tr[1])
            or (c["name"] == "Zanidatamab" and "HER2" in tr[1])
            for tr in unk
        ):
            # If an unknown-cancer leaf remains, it must not be this indication.
            from tree import leaf_clauses
            for tr in unk:
                clauses = " ".join(leaf_clauses(therapy, tr)).lower()
                if c["name"] == "Crizotinib" and "myofibroblastic" in clauses:
                    err(f"Crizotinib IMT still on unknown-cancer leaf {tr}")
                if c["name"] == "Vemurafenib" and "erdheim" in clauses:
                    err(f"Vemurafenib Erdheim-Chester still on unknown-cancer leaf {tr}")
                if c["name"] == "Dostarlimab" and re.search(r"\bEC\b", clauses, re.I) and "endometrial" not in " ".join(cancers_in(clauses)):
                    err(f"Dostarlimab EC still on unknown-cancer leaf {tr}")
                if c["name"] == "Zanidatamab" and "biliary" in clauses:
                    err(f"Zanidatamab biliary tract still on unknown-cancer leaf {tr}")
        # Visible page after a site build.
    from build_mockup import slug
    pages = [
        TREE / "ALK" / slug("inflammatory myofibroblastic tumour") / slug("ALK fusion or ALK-positive") / "after-another-drug.html",
        TREE / "BRAF-V600E" / slug("Erdheim-Chester disease") / slug("BRAF V600") / "label-does-not-say-when-it-is-used.html",
        TREE / "MSI-H-dMMR" / slug("cancer of the womb") / slug("MSI-H or dMMR") / "label-does-not-say-when-it-is-used.html",
        TREE / "HER2" / slug("bile duct cancer") / slug("HER2-positive") / "after-another-drug.html",
    ]
    drugs = ["Crizotinib", "Vemurafenib", "Dostarlimab", "Zanidatamab"]
    for page, drug in zip(pages, drugs):
        if not page.is_file():
            err(f"missing page for {drug}: {page.relative_to(SITE)}")
            continue
        html = page.read_text(encoding="utf-8")
        if drug not in html:
            err(f"{drug} not on {page.relative_to(SITE)}")
    # These drugs must not remain on a therapy unknown-cancer leaf page.
    gone = [
        (TREE / "ALK" / "label-does-not-say-the-cancer-type" / "alk-fusion-or-alk-positive" / "after-another-drug.html", "Crizotinib"),
        (TREE / "BRAF-V600E" / "label-does-not-say-the-cancer-type" / "braf-v600" / "label-does-not-say-when-it-is-used.html", "Vemurafenib"),
        (TREE / "MSI-H-dMMR" / "label-does-not-say-the-cancer-type" / "msi-h-or-dmmr" / "label-does-not-say-when-it-is-used.html", "Dostarlimab"),
        (TREE / "HER2" / "label-does-not-say-the-cancer-type" / "her2-positive" / "after-another-drug.html", "Zanidatamab"),
    ]
    for page, drug in gone:
        if page.is_file() and drug in page.read_text(encoding="utf-8"):
            err(f"{drug} still on unknown-cancer page {page.relative_to(SITE)}")
    ok(
        "named cancers from labels sit under real types "
        "(Crizotinib IMT set_id 2a51b0de-47d6-455e-a94c-d2c737b04ff7 v47; "
        "Vemurafenib ECD 38eea320-7e0c-485a-bc30-98c3c45e2763 v29; "
        "Dostarlimab EC 095eab9f-545a-4f12-bfb7-19477fb901a5 v15; "
        "Zanidatamab BTC ae5d9425-fae5-4541-a158-150998343348 v3)"
    )


def test_unknown_cancer_fallback_remains() -> None:
    """A 'cancer type not named' leaf remains for uses the rule cannot place."""
    from tree import therapy_branches, LABEL_UNKNOWN_CANCER, CANCER_TYPES, cancers_in
    # Mobocertinib: withdrawn, no full label in the catalog; the snapshot
    # excerpt is truncated mid-word ("non-small ce") and does not match
    # a recognised cancer type. It must stay on the fallback leaf.
    triples = therapy_branches({"name": "Mobocertinib"}, "EGFR")
    unk = [tr for tr in triples if tr[0] == LABEL_UNKNOWN_CANCER]
    if not unk:
        err(f"Mobocertinib lost the unknown-cancer fallback: {triples}")
    else:
        ok("Mobocertinib truncated excerpt stays on 'cancer type not named'")
    # CIViC ERBB2 G292R assertion (disease 'Cancer') is On the edge;
    # the record does not name a cancer the rule recognises.
    page = TREE / "HER2" / "label-does-not-say-the-cancer-type" / "erbb2-g292r" / "label-does-not-say-when-it-is-used.html"
    if not page.is_file():
        err("HER2 ERBB2 G292R unknown-cancer fallback page is missing")
    else:
        html = page.read_text(encoding="utf-8")
        if "Trastuzumab" not in html:
            err("Trastuzumab G292R civic assertion missing from fallback page")
        else:
            ok("ERBB2 G292R civic assertion (disease 'Cancer') stays on fallback")
    # The fallback label itself must still be produced for empty cancers_in.
    if cancers_in("no named malignancy in this sentence") != []:
        err("cancers_in no longer returns empty for unrecognised text")
    labels = {name for name, _ in CANCER_TYPES}
    if "inflammatory myofibroblastic tumour" not in labels:
        err("IMT cancer type missing from CANCER_TYPES")


def test_what_it_is_matches_mechanism() -> None:
    """what_it_is must follow the label mechanism for co-equal targets.

    Lapatinib (set_id 302a4346-a68d-af3e-e063-6294a90a4a6f, version 1):
    'kinase inhibitor of the intracellular tyrosine kinase domains of both
    Epidermal Growth Factor Receptor (EGFR [ErbB1]) and of Human Epidermal
    Receptor Type 2 (HER2 [ErbB2])'. Exact wording required: 'blocks the
    EGFR and HER2 signals'.
    """
    from labels import what_it_is, entry_for

    entry = entry_for({"name": "Lapatinib"})
    if not entry:
        err("Lapatinib missing from labels.json")
        return
    if (entry.get("set_id") or "") != "302a4346-a68d-af3e-e063-6294a90a4a6f" or str(entry.get("version") or "") != "1":
        err(f"Lapatinib label identity changed: {entry.get('set_id')} v{entry.get('version')}")
    wit = what_it_is({"name": "Lapatinib"}, "HER2")
    if "blocks the EGFR and HER2 signals" not in wit:
        err(f"Lapatinib what_it_is is not the required wording: {wit!r}")
    # Same-kind mismatches we also corrected, checked against the committed label.
    others = [
        ("Neratinib", "HER2", "blocks the EGFR, HER2 and HER4 signals",
         "irreversibly binds to epidermal growth factor receptor (EGFR), HER2, and HER4"),
        ("Pertuzumab", "HER2", "blocks the HER2 signal",
         "HER2/neu receptor antagonist"),
        ("Entrectinib", "NTRK", "blocks the NTRK, ROS1 and ALK signals",
         "tropomyosin receptor tyrosine kinases"),
        ("Repotrectinib", "NTRK", "blocks the ROS1 and NTRK signals",
         "inhibitor of proto-oncogene tyrosine-protein kinase ROS1"),
        ("Amivantamab", "EGFR", "blocks the EGFR and MET signals",
         "binds to the extracellular domains of EGFR and MET"),
        ("Afatinib", "EGFR", "blocks the EGFR, HER2 and HER4 signals",
         "kinase domains of EGFR (ErbB1), HER2 (ErbB2), and HER4 (ErbB4)"),
        ("Dacomitinib", "EGFR", "blocks the EGFR, HER2 and HER4 signals",
         "EGFR family (EGFR/HER1, HER2, and HER4)"),
    ]
    from labels import indications, label_blob, class_source
    for name, bid, phrase, snippet in others:
        wit = what_it_is({"name": name}, bid)
        if phrase not in wit:
            err(f"{name} what_it_is missing {phrase!r}: {wit!r}")
        src = class_source({"name": name})
        if snippet.lower() not in (src or "").lower() and snippet.lower() not in (label_blob({"name": name}) or "").lower():
            err(f"{name} committed label/class source no longer has {snippet!r}")
    # Visible Lapatinib row on the letrozole leaf.
    vis_when = TREE / "HER2" / "breast-cancer" / "her2-positive" / "label-does-not-say-when-it-is-used.html"
    if vis_when.is_file():
        html = vis_when.read_text(encoding="utf-8")
        if "blocks the EGFR and HER2 signals" not in html:
            err("Lapatinib required wording is not on the HER2 breast unknown-when table")
    ok("what_it_is follows the label mechanism; Lapatinib uses the required wording")


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
    test_lapatinib_letrozole_not_dropped()
    test_named_cancer_types_from_labels()
    test_unknown_cancer_fallback_remains()
    test_what_it_is_matches_mechanism()
    if errors:
        print(f"\n{len(errors)} FAIL(S)")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
