#!/usr/bin/env python3
"""Gates for the static site: disclaimer, schema, sources, no OncoKB, no patient input."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DATA = ROOT / "data" / "snapshot.json"

sys.path.insert(0, str(ROOT / "scripts"))
from matching import (  # noqa: E402
    analyse_text,
    classify_relation,
    is_her2_negative_only,
    targeting_therapies,
    TARGETS,
    NOT_SHOWN,
    dedupe_therapies,
    therapies_are_same_drug,
)
DISCLAIMER = "Not medical advice. Talk to your oncologist."
BIOMARKER_IDS = ["EGFR", "ALK", "BRAF-V600E", "KRAS-G12C", "HER2", "NTRK", "MSI-H-dMMR"]
FORBIDDEN = [
    r"oncokb\.org",
    r"type=\"file\"",
    r"type='file'",
    r"<textarea",
    r"type=\"password\"",
    r"google-analytics",
    r"gtag\(",
    r"googletagmanager",
    r"document\.cookie\s*=",
    r"localStorage\.(set|get|remove)",
    r"\bAXA\b",
]
# Free-text clinical intake is forbidden. A closed <select> is allowed.

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)
    print("FAIL:", msg)


def ok(msg: str) -> None:
    print("OK:  ", msg)


def test_snapshot_schema() -> None:
    if not DATA.is_file():
        err(f"missing snapshot {DATA}")
        return
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    for key in ("snapshotDate", "biomarkers", "whatsNew", "counts", "sourceStats"):
        if key not in snap:
            err(f"snapshot missing {key}")
    if not re.match(r"\d{4}-\d{2}-\d{2}", snap.get("snapshotDate") or ""):
        err("snapshotDate is not YYYY-MM-DD")
    else:
        ok(f"snapshotDate {snap['snapshotDate']}")
    ids = [b.get("id") for b in snap.get("biomarkers") or []]
    for i in BIOMARKER_IDS:
        if i not in ids:
            err(f"missing biomarker {i}")
    ok(f"{len(ids)} biomarkers")
    # No OncoKB anywhere in the data
    blob = json.dumps(snap)
    if re.search(r"oncokb\.org", blob, re.I):
        err("OncoKB URL in snapshot data")
    else:
        ok("no OncoKB source URLs in snapshot")
    # Every therapy has at least one citation with a URL
    n_th = 0
    for b in snap.get("biomarkers") or []:
        for t in b.get("therapies") or []:
            n_th += 1
            cites = t.get("citations") or []
            if not any(c.get("url") for c in cites):
                err(f"{b['id']}/{t.get('name')}: therapy without a citation URL")
        for tr in b.get("trials") or []:
            if not (tr.get("url") and tr.get("nctId")):
                err(f"{b['id']}: trial missing url or nctId")
    ok(f"{n_th} therapies, each citation-checked")
    # France and Switzerland appear as filterable countries (may have 0 trials)
    # The site generator always lists them; here we just note counts.
    for name in ("France", "Switzerland"):
        n = sum(
            1
            for b in snap.get("biomarkers") or []
            for t in b.get("trials") or []
            if name in (t.get("countries") or [])
        )
        ok(f"{name}: {n} trials across biomarkers")


def html_pages() -> list[Path]:
    return sorted(SITE.glob("*.html")) + sorted((SITE / "b").glob("*.html"))


def test_pages() -> None:
    pages = html_pages()
    if len(pages) < 9:
        err(f"expected at least 9 HTML pages, found {len(pages)}")
    for p in pages:
        text = p.read_text(encoding="utf-8")
        if DISCLAIMER not in text:
            err(f"{p.relative_to(ROOT)}: missing disclaimer")
        if "snapshot-date" not in text and "Snapshot date" not in text:
            err(f"{p.relative_to(ROOT)}: missing snapshot date")
        if 'id="stale-banner"' not in text:
            err(f"{p.relative_to(ROOT)}: missing stale banner")
        for pat in FORBIDDEN:
            if re.search(pat, text):
                err(f"{p.relative_to(ROOT)}: forbidden pattern {pat}")
        # no free-text input
        if re.search(r"<input[^>]+type=[\"']text[\"']", text, re.I):
            err(f"{p.relative_to(ROOT)}: text input (free text is not allowed)")
        if re.search(r"<input[^>]+type=[\"']search[\"']", text, re.I):
            err(f"{p.relative_to(ROOT)}: search input (free text is not allowed)")
    ok(f"disclaimer, snapshot date and stale banner on {len(pages)} pages")

    # Country filter lists France and Switzerland on biomarker pages
    for p in (SITE / "b").glob("*.html"):
        text = p.read_text(encoding="utf-8")
        if 'id="country-filter"' not in text:
            err(f"{p.name}: missing country filter")
        if ">France" not in text or ">Switzerland" not in text:
            err(f"{p.name}: country filter must include France and Switzerland")
    ok("country filter includes France and Switzerland")

    about = (SITE / "about.html").read_text(encoding="utf-8")
    for label in (
        "ClinicalTrials.gov",
        "openFDA",
        "European Medicines Agency",
        "CIViC",
        "OncoKB is not used",
        "CC0",
        "PubMed",
    ):
        if label not in about:
            err(f"about.html missing {label}")
    ok("about page carries source attributions")

    # Home has the seven biomarkers
    home = (SITE / "index.html").read_text(encoding="utf-8")
    for i in BIOMARKER_IDS:
        if f"b/{i}.html" not in home:
            err(f"home missing link to {i}")
    ok("home links all seven biomarkers")

    # JS has stale-after-8-days and no cookies
    js = (SITE / "assets" / "js" / "app.js").read_text(encoding="utf-8")
    if "days > 8" not in js and "days>8" not in js:
        err("app.js does not implement the 8-day stale rule")
    if re.search(r"document\.cookie\s*=", js) or re.search(r"localStorage\.(set|get|remove)", js):
        err("app.js must not use cookies or localStorage")
    ok("stale-banner logic and no storage in app.js")


def test_css_identity() -> None:
    css = (SITE / "assets" / "css" / "style.css").read_text(encoding="utf-8")
    for token in ("#f4efe4", "#1b4f4c", "#b02058", "#d13a72", "Barlow Condensed", "Source Sans 3"):
        if token not in css:
            err(f"CSS missing identity token {token}")
    # no rust orange, no typical Claude orange
    if re.search(r"#d97[0-9a-fA-F]{3}|#c65[0-9a-fA-F]{3}|#e67e22|#ff6b00", css):
        err("CSS appears to contain orange")
    ok("Risograph identity present, no orange")


def test_matching_patterns() -> None:
    """Unit checks for selection-criterion vs exclusion polarity."""
    cases = [
        ("EGFR", "whose tumors have epidermal growth factor receptor (EGFR) exon 19 deletions", "positive"),
        ("EGFR", "NSCLC with no EGFR or ALK genomic tumor aberrations", "negative"),
        ("EGFR", "metastatic NSCLC with no sensitizing EGFR mutations", "negative"),
        ("EGFR", "Patients with EGFR or ALK genomic tumor aberrations should have disease progression on FDA-approved therapy", "unclear"),
        ("EGFR", "ERBITUX is an epidermal growth factor receptor (EGFR) antagonist indicated for Head and Neck Cancer", "positive"),
        ("EGFR", "Vectibix is an epidermal growth factor receptor (EGFR) antagonist indicated for wild-type RAS metastatic colorectal cancer", "positive"),
        ("ALK", "no known epidermal growth factor receptor (EGFR) mutations or anaplastic lymphoma kinase (ALK) rearrangements", "negative"),
        ("HER2", "HR-positive, HER2-negative advanced or metastatic breast cancer", "negative"),
        ("HER2", "human epidermal growth factor receptor 2 (HER2)-negative, node-positive, early breast cancer", "negative"),
        ("HER2", "KADCYLA is a HER2-targeted antibody indicated for HER2-positive metastatic breast cancer", "positive"),
        ("HER2", "ENHERTU is a HER2-directed antibody indicated for HER2-low (IHC 1+ or IHC 2+/ISH-negative) breast cancer", "positive"),
        ("KRAS-G12C", "adult patients with KRAS G12C-mutated locally advanced or metastatic NSCLC", "positive"),
        ("KRAS-G12C", "wild-type RAS (defined as wild-type in both KRAS and NRAS) metastatic colorectal cancer", "negative"),
        ("MSI-H-dMMR", "unresectable or metastatic MSI-H or dMMR colorectal cancer", "positive"),
        ("MSI-H-dMMR", "endometrial carcinoma that is mismatch repair proficient (pMMR) or not microsatellite instability-high (MSI-H)", "negative"),
        ("BRAF-V600E", "unresectable or metastatic melanoma with a BRAF V600E or V600K mutation", "positive"),
        ("NTRK", "solid tumors that have a neurotrophic tyrosine receptor kinase ( NTRK ) gene fusion", "positive"),
    ]
    for bid, text, expect in cases:
        a = analyse_text(text, bid)
        got = (
            "positive" if a["positives"]
            else "negative" if a["negatives"]
            else "unclear" if a["has_mention"]
            else "none"
        )
        if expect == "positive" and a["positives"]:
            continue
        if expect == "negative" and a["negatives"] and not a["positives"]:
            continue
        if expect == "unclear" and not a["positives"] and not a["negatives"]:
            continue
        err(f"matching {bid}: expected {expect}, got {got} for {text[:80]}")
    ok(f"{len(cases)} matching polarity cases")


def test_matching_correctness() -> None:
    """EGFR must not list atezolizumab; HER2 must not list HER2-negative-only indications.

    Core EGFR TKIs and trastuzumab must remain where present. The check applies
    to the rendered pages and to therapies marked as targeting in the snapshot
    (mentioned/exclusion associations stay in the data, flagged, and are not
    treated as listings of the drug as a therapy for that biomarker).
    """
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    by_id = {b["id"]: b for b in snap.get("biomarkers") or []}

    egfr = by_id.get("EGFR") or {}
    shown_egfr = targeting_therapies(egfr)
    names_egfr = [t.get("name") or "" for t in shown_egfr]
    page_egfr = (SITE / "b" / "EGFR.html").read_text(encoding="utf-8")
    # Only the approved-therapies section: trial intervention lists may
    # mention atezolizumab without listing it as an EGFR-targeted therapy.
    th_section = page_egfr
    if 'id="therapies"' in page_egfr:
        th_section = page_egfr.split('id="therapies"', 1)[1]
        if 'id="trials"' in th_section:
            th_section = th_section.split('id="trials"', 1)[0]

    for t in shown_egfr:
        if re.search(r"atezolizumab", t.get("name") or "", re.I):
            err("EGFR data lists atezolizumab as a targeting therapy")
    if re.search(r"atezolizumab", th_section, re.I):
        err("EGFR page lists atezolizumab")
    else:
        ok("EGFR page and targeting data do not list atezolizumab")

    present = {t.get("name", "").lower() for t in (egfr.get("therapies") or [])}
    shown_l = {n.lower() for n in names_egfr}
    for core in ("osimertinib", "erlotinib", "gefitinib", "afatinib", "amivantamab"):
        if core in present and core not in shown_l:
            err(f"EGFR dropped core drug {core}")
        elif core in shown_l:
            if core not in page_egfr.lower():
                err(f"EGFR page is missing core drug {core}")
    ok("EGFR keeps osimertinib/erlotinib/gefitinib/afatinib/amivantamab where present")

    her2 = by_id.get("HER2") or {}
    shown_her2 = targeting_therapies(her2)
    page_her2 = (SITE / "b" / "HER2.html").read_text(encoding="utf-8")
    for t in shown_her2:
        if is_her2_negative_only(t):
            err(f"HER2 lists HER2-negative-only indication: {t.get('name')}")
    # The rendered excerpts of shown therapies must not be HER2-negative-only.
    for t in shown_her2:
        excerpt = t.get("indicationsExcerpt") or ""
        if is_her2_negative_only({"indicationsExcerpt": excerpt}):
            err(f"HER2 page would show a HER2-negative-only excerpt for {t.get('name')}")
    present_h = {t.get("name", "").lower() for t in (her2.get("therapies") or [])}
    if any("trastuzumab" == t.get("name", "").lower() or t.get("name", "").lower() == "trastuzumab" for t in (her2.get("therapies") or [])):
        if not any("trastuzumab" == (t.get("name") or "").lower() for t in shown_her2):
            err("HER2 dropped trastuzumab")
        if "trastuzumab" not in page_her2.lower():
            err("HER2 page is missing trastuzumab")
    ok("HER2 keeps trastuzumab and lists no HER2-negative-only indication")

    # MSI-H / any biomarker with 0 CIViC assertions: the page is not an empty block.
    for b in snap.get("biomarkers") or []:
        assertions = ((b.get("civic") or {}).get("assertions")) or []
        page = (SITE / "b" / f"{b['id']}.html").read_text(encoding="utf-8")
        if not assertions and "No curated assertions yet" not in page:
            err(f"{b['id']} page has 0 CIViC assertions but is missing 'No curated assertions yet'")
    ok("biomarkers with 0 CIViC assertions show 'No curated assertions yet'")

    # Mentioned/exclusion associations stay in the data.
    atezo = [t for t in (egfr.get("therapies") or []) if re.search(r"atezolizumab", t.get("name") or "", re.I)]
    if not atezo:
        err("EGFR data should still keep the atezolizumab association, flagged")
    elif atezo[0].get("relation") == TARGETS:
        err("EGFR atezolizumab association is still marked as targeting")
    else:
        ok(f"EGFR keeps atezolizumab in the data as relation={atezo[0].get('relation')}")


def _therapies_section(page: str) -> str:
    """The approved-therapies block, excluding later trial lists."""
    if 'id="therapies"' not in page:
        return page
    section = page.split('id="therapies"', 1)[1]
    if 'id="trials"' in section:
        section = section.split('id="trials"', 1)[0]
    return section


def _therapy_headings(section: str) -> list[str]:
    """Visible therapy titles (h3 text, including any brand in parentheses)."""
    return re.findall(r"<h3>(.*?)</h3>", section, flags=re.I | re.S)


def test_her2_partners_and_brand_dedup() -> None:
    """HER2 must not show palbociclib or capecitabine; EGFR shows sunvozertinib once.

    Palbociclib and capecitabine stay in the snapshot, flagged as not shown.
    The Zegfrovy / sunvozertinib brand-generic collision is a single entry,
    and the same dedup is applied generally (sharing a brand is not enough).
    """
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    by_id = {b["id"]: b for b in snap.get("biomarkers") or []}

    her2 = by_id.get("HER2") or {}
    shown_her2 = targeting_therapies(her2)
    page_her2 = (SITE / "b" / "HER2.html").read_text(encoding="utf-8")
    th_her2 = _therapies_section(page_her2)
    headings_her2 = _therapy_headings(th_her2)
    heading_text = [re.sub(r"<[^>]+>", "", h) for h in headings_her2]
    for drug in ("palbociclib", "capecitabine"):
        for rec in shown_her2:
            if re.search(drug, rec.get("name") or "", re.I):
                err(f"HER2 targeting data lists {drug}")
        # Only the therapy title, not excerpts of other drugs that are used
        # "in combination with capecitabine".
        titled = [h for h in heading_text if re.search(drug, h, re.I)]
        if titled:
            err(f"HER2 page lists {drug} as a therapy: {titled}")
        kept = [rec for rec in (her2.get("therapies") or []) if re.search(drug, rec.get("name") or "", re.I)]
        if not kept:
            err(f"HER2 data should still keep {drug}, flagged as not shown")
        elif kept[0].get("relation") == TARGETS:
            err(f"HER2 {drug} is still marked as targeting")
        else:
            ok(f"HER2 keeps {drug} in the data as relation={kept[0].get('relation')}, not shown")
    ok("HER2 page and targeting data do not list palbociclib or capecitabine")

    egfr = by_id.get("EGFR") or {}
    shown_egfr = targeting_therapies(egfr)
    page_egfr = (SITE / "b" / "EGFR.html").read_text(encoding="utf-8")
    th_egfr = _therapies_section(page_egfr)
    headings = _therapy_headings(th_egfr)
    # Headings include the brand in parentheses, e.g. "Sunvozertinib (Zegfrovy)".
    sunvo = [h for h in headings if re.search(r"sunvozertinib", h, re.I)]
    zeg_alone = []
    for h in headings:
        # The main name is the text before a brand span or parenthesis.
        main = re.sub(r"<[^>]+>", "", h)
        main_name = re.split(r"\s*\(", main, maxsplit=1)[0].strip()
        if re.fullmatch(r"zegfrovy", main_name, re.I):
            zeg_alone.append(h)
    if len(sunvo) != 1:
        err(f"EGFR page should show sunvozertinib exactly once, got {len(sunvo)}: {sunvo}")
    else:
        ok(f"EGFR page shows sunvozertinib once: {re.sub(r'<[^>]+>', '', sunvo[0])}")
    if zeg_alone:
        err(f"EGFR page has a separate Zegfrovy entry: {zeg_alone}")
    else:
        ok("EGFR page has no separate Zegfrovy entry")

    shown_names = [t.get("name") or "" for t in shown_egfr]
    sunvo_data = [n for n in shown_names if re.search(r"sunvozertinib", n, re.I)]
    zeg_data = [n for n in shown_names if re.fullmatch(r"zegfrovy", n, re.I)]
    if len(sunvo_data) != 1:
        err(f"EGFR targeting data should list sunvozertinib exactly once, got {sunvo_data}")
    if zeg_data:
        err(f"EGFR targeting data still has a separate Zegfrovy entry: {zeg_data}")
    # After the merge, the raw therapies list also has a single record.
    all_egfr = [t.get("name") or "" for t in (egfr.get("therapies") or [])]
    sunvo_all = [n for n in all_egfr if re.search(r"sunvozertinib|zegfrovy", n, re.I)]
    if len(sunvo_all) != 1 or not re.search(r"sunvozertinib", sunvo_all[0], re.I):
        err(f"EGFR snapshot should have one sunvozertinib record, not {sunvo_all}")
    else:
        ok(f"EGFR snapshot has one merged record: {sunvo_all[0]}")

    # Dedup is general: brand-vs-generic merges, shared-brand-only does not.
    a = {
        "name": "Sunvozertinib",
        "brandNames": ["ZEGFROVY"],
        "genericNames": ["SUNVOZERTINIB"],
    }
    b = {"name": "Zegfrovy", "brandNames": [], "genericNames": []}
    out, reports = dedupe_therapies([a, b])
    if len(out) != 1 or not reports:
        err("dedupe_therapies did not merge a brand/generic pair")
    else:
        display_brands = " ".join(out[0].get("brandNames") or [])
        if not re.search(r"zegfrovy", display_brands, re.I) or not re.search(r"sunvozertinib", out[0].get("name") or "", re.I):
            err(f"merged entry should be sunvozertinib with Zegfrovy as brand, got {out[0].get('name')} ({display_brands})")
        else:
            ok("dedupe_therapies merges a brand/generic pair into one entry")

    trast = {"name": "Trastuzumab", "brandNames": ["Herceptin", "KADCYLA"], "genericNames": []}
    tdm1 = {
        "name": "Ado-Trastuzumab Emtansine",
        "brandNames": ["KADCYLA"],
        "genericNames": ["ADO-TRASTUZUMAB EMTANSINE"],
    }
    if therapies_are_same_drug(trast, tdm1):
        err("Trastuzumab and Ado-Trastuzumab Emtansine must not be treated as the same drug")
    out2, reports2 = dedupe_therapies([trast, tdm1])
    if len(out2) != 2 or reports2:
        err(f"shared-brand-only pair was merged: {reports2}")
    else:
        ok("dedupe_therapies does not merge distinct drugs that only share a brand")



def main() -> int:
    test_snapshot_schema()
    test_pages()
    test_css_identity()
    test_matching_patterns()
    test_matching_correctness()
    test_her2_partners_and_brand_dedup()
    if errors:
        print(f"\n{len(errors)} failure(s)")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
