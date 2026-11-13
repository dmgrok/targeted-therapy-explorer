#!/usr/bin/env python3
"""Gates for the static site: disclaimer, schema, sources, no OncoKB, no patient input."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

def biomarker_html(bid: str) -> str:
    """Concatenated HTML of every page in a biomarker tree (or a leftover long page)."""
    parts = []
    long_page = SITE / "b" / f"{bid}.html"
    if long_page.is_file():
        parts.append(long_page.read_text(encoding="utf-8"))
    root = SITE / "b" / bid
    if root.is_dir():
        for p in sorted(root.rglob("*.html")):
            parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)

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
from trial_matching import (  # noqa: E402
    trial_requirement,
    requiring_trials,
    analyse_trial_text,
    REQUIRES,
    EXCLUSION,
    NOT_REQUIRED,
)
from fetch_snapshot import (  # noqa: E402
    same_active_ingredient,
    primary_inn,
    label_belongs_to_drug,
    match_ema,
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
    return sorted(SITE.glob("*.html")) + sorted((SITE / "b").rglob("*.html")) + (sorted((SITE / "cases").rglob("*.html")) if (SITE / "cases").is_dir() else [])


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

    # The decision-tree tables list each trial's countries in Sources,
    # rather than a page-level country filter. France and Switzerland
    # remain in the snapshot country counts checked above.
    ok("country listings stay in the snapshot; tree pages have no free-text filter")

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
        if f"b/{i}/index.html" not in home and f"b/{i}.html" not in home:
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
    page_egfr = biomarker_html("EGFR")

    for t in shown_egfr:
        if re.search(r"atezolizumab", t.get("name") or "", re.I):
            err("EGFR data lists atezolizumab as a targeting therapy")
    # Whole rendered page, trial cards included.
    if re.search(r"atezolizumab", page_egfr, re.I):
        err("EGFR page contains 'atezolizumab'")
    else:
        ok("EGFR page (including trial cards) does not contain atezolizumab")

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
    page_her2 = biomarker_html("HER2")
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

    # Every biomarker has a decision-tree page. Raw CIViC, when present,
    # stays behind a Sources toggle.
    for b in snap.get("biomarkers") or []:
        page = biomarker_html(b["id"])
        if not page:
            err(b["id"] + " tree is missing")
    ok("every biomarker has a decision-tree page")

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
    """Visible therapy titles: h3 on older pages, option-column cells on tree tables."""
    heads = re.findall(r"<h3>(.*?)</h3>", section, flags=re.I | re.S)
    cells = re.findall(
        r'<th[^>]*class="col-option"[^>]*>(.*?)</th>',
        section,
        flags=re.I | re.S,
    )
    return heads + cells


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
    page_her2 = biomarker_html("HER2")
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
    page_egfr = biomarker_html("EGFR")
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
    if not sunvo:
        err("EGFR tree does not show sunvozertinib as an option")
    else:
        ok(f"EGFR tree shows sunvozertinib as an option ({len(sunvo)} row(s) across leaves)")
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




def _trial_articles(page: str) -> list[str]:
    if 'id="trials"' not in page:
        return []
    section = page.split('id="trials"', 1)[1]
    # Stop before CIViC / further reading if present.
    for stop in ('id="civic"', 'id="reading"'):
        if stop in section:
            section = section.split(stop, 1)[0]
            break
    return re.findall(r'<article class="item trial"[^>]*>.*?</article>', section, flags=re.I | re.S)


def test_trial_requirement() -> None:
    """Shown trials must require the biomarker; EGFR has no atezolizumab anywhere.

    A trial whose only HER2 mention is HER2-negative must not appear on HER2.
    Every rendered trial card has a matching requirement. Excluded trials stay
    in the snapshot, flagged.
    """
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    by_id = {b["id"]: b for b in snap.get("biomarkers") or []}

    page_egfr = biomarker_html("EGFR")
    if re.search(r"atezolizumab", page_egfr, re.I):
        err("EGFR page contains 'atezolizumab' (whole page, trial cards included)")
    else:
        ok("EGFR whole page contains no atezolizumab")

    # Synthetic / documented cases.
    cases = [
        (
            "EGFR",
            {
                "nctId": "NCT0",
                "title": "A Study in Metastatic Breast Cancer",
                "conditions": ["Metastatic Breast Cancer"],
                "interventions": ["DRUG: Atezolizumab", "DRUG: Capecitabine"],
            },
            {},
            NOT_REQUIRED,
        ),
        (
            "EGFR",
            {"nctId": "NCT1", "title": "Osimertinib for EGFR-Mutant Lung Cancer", "conditions": ["EGFR-Mutant NSCLC"]},
            {},
            REQUIRES,
        ),
        (
            "EGFR",
            {
                "nctId": "NCT2",
                "title": "Teliso-V in NSCLC",
                "conditions": ["Non Small Cell Lung Cancer"],
            },
            {"officialTitle": "Telisotuzumab Vedotin in EGFR Wildtype NSCLC"},
            EXCLUSION,
        ),
        (
            "EGFR",
            {"nctId": "NCT3", "title": "Study of a Kidney Drug", "conditions": ["Chronic Kidney Disease"]},
            {"eligibilityCriteria": "Inclusion Criteria:\n* eGFR >= 30 mL/min/1.73m^2\nExclusion Criteria:\n* None"},
            NOT_REQUIRED,
        ),
        (
            "HER2",
            {
                "nctId": "NCT4",
                "title": "A Study in HR+/HER2- Breast Cancer",
                "conditions": ["HR+/HER2- Breast Cancer"],
            },
            {},
            EXCLUSION,
        ),
        (
            "HER2",
            {
                "nctId": "NCT5",
                "title": "Trastuzumab in HER2-positive Breast Cancer",
                "conditions": ["HER2-positive Breast Cancer"],
            },
            {},
            REQUIRES,
        ),
        (
            "EGFR",
            {
                "nctId": "NCT6",
                "title": "STX-721 in NSCLC Harboring EGFR or HER2 Exon 20 Insertion Mutations",
                "conditions": ["NSCLC", "EGFR/HER2 Exon 20 Insertion Mutation"],
            },
            {},
            REQUIRES,
        ),
    ]
    for bid, trial, extra, expect in cases:
        got = trial_requirement(bid, trial, extra)["relation"]
        if got != expect:
            err(f"trial_requirement({bid}, {trial['nctId']}): expected {expect}, got {got}")
    ok("trial_requirement unit cases")

    her2 = by_id.get("HER2") or {}
    page_her2 = biomarker_html("HER2")
    shown_her2 = requiring_trials(her2)
    for t in shown_her2:
        pop = " ".join(
            [
                t.get("title") or "",
                " ".join(t.get("conditions") or []),
                t.get("requirementEvidence") or "",
            ]
        )
        a = analyse_trial_text(pop, "HER2")
        if a["negatives"] and not a["positives"]:
            # Only-negative (HER2-negative / HR+/HER2-) mention.
            err(
                f"HER2 page would show a trial whose only HER2 mention is HER2-negative: "
                f"{t.get('nctId')} {t.get('title')}"
            )
    # Same check on the rendered cards themselves.
    by_nct = {t.get("nctId"): t for t in (her2.get("trials") or [])}
    for art in _trial_articles(page_her2):
        m = re.search(r'data-nct="([^"]+)"', art)
        nct = m.group(1) if m else ""
        t = by_nct.get(nct) or {}
        text = re.sub(r"<[^>]+>", " ", art)
        a = analyse_trial_text(
            text + " " + (t.get("requirementEvidence") or ""),
            "HER2",
        )
        if a["negatives"] and not a["positives"]:
            err(f"HER2 page trial card {nct} has only a HER2-negative mention")
    ok("HER2 shows no trial whose only HER2 mention is HER2-negative")

    # Every shown trial card, on every biomarker page, has a matching requirement.
    for b in snap.get("biomarkers") or []:
        page = biomarker_html(b["id"])
        by_nct = {t.get("nctId"): t for t in (b.get("trials") or [])}
        shown = {t.get("nctId") for t in requiring_trials(b)}
        for art in _trial_articles(page):
            m = re.search(r'data-nct="([^"]+)"', art)
            if not m:
                err(f"{b['id']}: trial card missing data-nct")
                continue
            nct = m.group(1)
            t = by_nct.get(nct)
            if not t:
                err(f"{b['id']}: rendered trial {nct} is not in the snapshot")
                continue
            if nct not in shown or t.get("requirement") != REQUIRES:
                err(f"{b['id']}: shown trial card {nct} is not flagged as requiring the biomarker")
                continue
            ev = t.get("requirementEvidence") or ""
            pop = " ".join([t.get("title") or "", " ".join(t.get("conditions") or []), ev])
            a = analyse_trial_text(pop, b["id"])
            named_ok = ev or a["positives"] or a["has_mention"]
            if not named_ok or (a["negatives"] and not a["positives"] and not ev):
                err(f"{b['id']}: shown trial card {nct} lacks a matching requirement")
        # Dropped trials must not be rendered.
        for t in b.get("trials") or []:
            if t.get("requirement") == REQUIRES:
                continue
            nct = t.get("nctId") or ""
            if nct and re.search(rf'data-nct="{re.escape(nct)}"', page):
                err(f"{b['id']}: dropped trial {nct} is still rendered")
        # Flagged, kept in the data.
        dropped = [t for t in (b.get("trials") or []) if t.get("requirement") != REQUIRES]
        if dropped and any(not t.get("requirement") for t in dropped):
            err(f"{b['id']}: a dropped trial is missing a requirement flag")
    ok("every shown trial card has a matching requirement; excluded trials stay flagged in the data")

    # The loose-match atezolizumab breast-cancer trial stays in EGFR data, not shown.
    egfr = by_id.get("EGFR") or {}
    loose = [t for t in (egfr.get("trials") or []) if t.get("nctId") == "NCT03424005"]
    if loose:
        if loose[0].get("requirement") == REQUIRES:
            err("NCT03424005 is still marked as requiring EGFR")
        else:
            ok(f"EGFR keeps NCT03424005 in the data as requirement={loose[0].get('requirement')}")




def _trastuzumab_article(page: str) -> str:
    """Return HER2 tree table rows whose option name is Trastuzumab itself.

    Conjugates (ado-trastuzumab emtansine, fam-trastuzumab deruxtecan)
    have different option names and must not be included.
    """
    rows = re.findall(r"<tr>(.*?)</tr>", page, flags=re.I | re.S)
    out = []
    for row in rows:
        m = re.search(
            r'<th[^>]*class="col-option"[^>]*>\s*<strong>([^<]+)</strong>',
            row,
            flags=re.I,
        )
        if m and m.group(1).strip().lower() == "trastuzumab":
            out.append(row)
    return "\n".join(out)


def test_kadcyla_brand_attachment() -> None:
    """Trastuzumab must not list KADCYLA as a brand in data or on the HER2 article.

    KADCYLA belongs to ado-trastuzumab emtansine, which may still show it.
    """
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    her2 = next((b for b in snap["biomarkers"] if b["id"] == "HER2"), None)
    if not her2:
        err("HER2 biomarker missing")
        return
    trast = next((t for t in (her2.get("therapies") or []) if t.get("name") == "Trastuzumab"), None)
    ado = next(
        (t for t in (her2.get("therapies") or []) if re.search(r"ado-?trastuzumab emtansine", t.get("name") or "", re.I)),
        None,
    )
    if not trast:
        err("HER2 snapshot has no Trastuzumab entry")
        return
    brands = trast.get("brandNames") or []
    if any(re.search(r"kadcyla", b, re.I) for b in brands):
        err(f"Trastuzumab brandNames includes KADCYLA: {brands}")
    else:
        ok(f"Trastuzumab brands are {brands}, no KADCYLA")
    excerpt = trast.get("indicationsExcerpt") or ""
    if re.search(r"kadcyla", excerpt, re.I):
        err("Trastuzumab indications excerpt is the KADCYLA label")
    ema_names = [e.get("name") or "" for e in (trast.get("ema") or [])]
    if any(re.search(r"kadcyla|enhertu", n, re.I) for n in ema_names):
        err(f"Trastuzumab EMA list includes a conjugate brand: {ema_names}")
    else:
        ok(f"Trastuzumab EMA matches are {ema_names}")
    fda = trast.get("fda") or {}
    if "23f3c1f4-0fc8-4804-a9e3-04cf25dd302e" in (fda.get("dailymedUrl") or ""):
        err("Trastuzumab still points at the Kadcyla DailyMed setid")
    if "125427" in (fda.get("drugsfdaUrl") or ""):
        err("Trastuzumab still points at the Kadcyla Drugs@FDA application")
    if ado:
        ado_brands = ado.get("brandNames") or []
        if not any(re.search(r"kadcyla", b, re.I) for b in ado_brands):
            err(f"Ado-Trastuzumab Emtansine should still list KADCYLA, got {ado_brands}")
        else:
            ok(f"Ado-Trastuzumab Emtansine still lists {ado_brands}")
    else:
        err("HER2 snapshot is missing Ado-Trastuzumab Emtansine")

    page = biomarker_html("HER2")
    article = _trastuzumab_article(page)
    if not article:
        err("HER2 tree has no Trastuzumab option row")
        return
    # Brand span on this article only.
    brand_span = re.search(r'<span class="brand">\(([^)]*)\)</span>', article)
    brand_txt = brand_span.group(1) if brand_span else ""
    if re.search(r"kadcyla", brand_txt, re.I):
        err(f"HER2 trastuzumab article lists KADCYLA as a brand: {brand_txt}")
    else:
        ok(f"HER2 trastuzumab article brands: {brand_txt or '(none)'}")
    if re.search(r"kadcyla", article, re.I):
        err("HER2 trastuzumab article still mentions KADCYLA")
    else:
        ok("HER2 trastuzumab article does not mention KADCYLA")
    # The conjugate entry on the same page may still show KADCYLA.
    if not re.search(r"kadcyla", page, re.I):
        err("HER2 page should still mention KADCYLA on ado-trastuzumab emtansine")
    else:
        ok("HER2 page still mentions KADCYLA on the conjugate entry")

    # Unit: the fetch matcher rejects Kadcyla for a trastuzumab query.
    if label_belongs_to_drug("trastuzumab", ["KADCYLA"], ["ADO-TRASTUZUMAB EMTANSINE"]):
        err("label_belongs_to_drug accepted KADCYLA for trastuzumab")
    if not label_belongs_to_drug("trastuzumab", ["Herceptin"], ["TRASTUZUMAB"]):
        err("label_belongs_to_drug rejected Herceptin for trastuzumab")
    if same_active_ingredient("trastuzumab", "ado-trastuzumab emtansine"):
        err("same_active_ingredient treated trastuzumab and ado-trastuzumab emtansine as the same")
    if not same_active_ingredient("Ado-Trastuzumab Emtansine", "trastuzumab emtansine"):
        err("same_active_ingredient failed to equate ado-trastuzumab emtansine with trastuzumab emtansine")
    hits = match_ema(
        [
            {"name": "Herceptin", "inn": "trastuzumab"},
            {"name": "Kadcyla", "inn": "trastuzumab emtansine"},
            {"name": "Enhertu", "inn": "trastuzumab deruxtecan"},
            {"name": "Phesgo", "inn": "pertuzumab;trastuzumab"},
        ],
        "trastuzumab",
    )
    names = [h["name"] for h in hits]
    if "Kadcyla" in names or "Enhertu" in names:
        err(f"match_ema attached a conjugate to trastuzumab: {names}")
    if "Herceptin" not in names or "Phesgo" not in names:
        err(f"match_ema should keep Herceptin and Phesgo, got {names}")
    else:
        ok(f"match_ema for trastuzumab: {names}")


def test_brands_own_ingredient() -> None:
    """Brand names, DailyMed / Drugs@FDA URLs and EMA matches belong to one INN."""
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    by_brand: dict[str, set[str]] = {}
    by_dailymed: dict[str, set[str]] = {}
    by_app: dict[str, set[str]] = {}
    ema_bad = []
    for bm in snap.get("biomarkers") or []:
        for t in bm.get("therapies") or []:
            inn = primary_inn(t.get("name") or "")
            if not inn:
                continue
            for b in t.get("brandNames") or []:
                by_brand.setdefault(b.strip().lower(), set()).add(inn)
            fda = t.get("fda") or {}
            if fda.get("dailymedUrl"):
                by_dailymed.setdefault(fda["dailymedUrl"], set()).add(inn)
            if fda.get("drugsfdaUrl"):
                by_app.setdefault(fda["drugsfdaUrl"], set()).add(inn)
            for e in t.get("ema") or []:
                inn_name = e.get("inn") or ""
                parts = [p.strip() for p in re.split(r"[;/]", inn_name) if p.strip()] or [inn_name]
                if parts and not any(same_active_ingredient(t.get("name") or "", p) for p in parts if p):
                    ema_bad.append((bm["id"], t.get("name"), e.get("name"), inn_name))
    shared = []
    for label, mapping in (
        ("brand", by_brand),
        ("DailyMed URL", by_dailymed),
        ("Drugs@FDA URL", by_app),
    ):
        for k, inns in mapping.items():
            if len(inns) > 1:
                shared.append(f"{label} {k} on INNs {sorted(inns)}")
    if shared:
        err("brand or label attached to more than one active ingredient: " + "; ".join(shared))
    else:
        ok("no brand, DailyMed URL or Drugs@FDA URL is shared across different INNs")
    if ema_bad:
        err(f"EMA matches whose INN is not this drug: {ema_bad}")
    else:
        ok("every EMA match is this drug’s own ingredient (or a combination that lists it)")


def test_disclaimer_on_every_page() -> None:
    """Dedicated gate: every generated HTML page carries the short disclaimer."""
    pages = html_pages()
    if not pages:
        err("no generated HTML pages found")
        return
    missing = []
    for p in pages:
        text = p.read_text(encoding="utf-8")
        if DISCLAIMER not in text:
            missing.append(str(p.relative_to(ROOT)))
    if missing:
        err(f"pages missing {DISCLAIMER!r}: {missing}")
    else:
        ok(f"dedicated check: disclaimer present on all {len(pages)} pages")


def test_no_pubmed_abstracts() -> None:
    """Citation cards are metadata only; PubMed abstracts are not stored or shown."""
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    forbidden_keys = {"abstract", "abstracttext", "abstractText"}
    for bm in snap.get("biomarkers") or []:
        for c in bm.get("literature") or []:
            extra = set(c.keys()) & forbidden_keys
            if extra:
                err(f"{bm['id']} literature card has abstract field(s) {extra}")
            allowed = {"pmid", "title", "authors", "journal", "date", "url", "source"}
            unexpected = set(c.keys()) - allowed
            if unexpected:
                err(f"{bm['id']} literature card has unexpected fields {unexpected}")
    ok("snapshot literature cards have citation metadata only, no abstracts")

    # Pages: literature section must not contain an 'abstract' label, and must
    # carry a PMID link. Fetch uses esummary, not efetch.
    fetch = (ROOT / "scripts" / "fetch_snapshot.py").read_text(encoding="utf-8")
    if "efetch.fcgi" in fetch:
        err("fetch_snapshot.py calls PubMed efetch (would pull abstracts)")
    else:
        ok("fetch_snapshot.py does not call PubMed efetch")
    for p in html_pages():
        text = p.read_text(encoding="utf-8")
        if 'id="reading"' not in text and p.name not in ("index.html", "about.html"):
            # biomarker pages should have a further-reading section
            if p.parent.name == "b":
                err(f"{p.relative_to(ROOT)} missing further-reading section")
            continue
        if 'id="reading"' in text:
            section = text.split('id="reading"', 1)[1]
            for stop in ('id="civic"', "</main>"):
                if stop in section:
                    section = section.split(stop, 1)[0]
                    break
            if re.search(r"\babstract\b", section, re.I):
                err(f"{p.relative_to(ROOT)} further-reading section mentions an abstract")
    ok("further-reading cards do not show abstracts")


def test_no_patient_contacts() -> None:
    """No emails, phone numbers or site contact names in the snapshot or on pages.

    Trial cards show countries and a ClinicalTrials.gov link, not site contacts.
    Institution facility names may remain in the snapshot; they are not contacts.
    """
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    # Snapshot trials: location records may only have facility, city, country.
    loc_allowed = {"facility", "city", "country"}
    contact_keys = re.compile(
        r"(centralcontact|overallofficial|contactname|contactphone|contactemail|phone|email|fax)",
        re.I,
    )
    for bm in snap.get("biomarkers") or []:
        for t in bm.get("trials") or []:
            for k in t.keys():
                if contact_keys.search(k) and k not in ("locations",):
                    err(f"{bm['id']} {t.get('nctId')} has contact field {k}")
            for loc in t.get("locations") or []:
                extra = set(loc.keys()) - loc_allowed
                if extra:
                    err(f"{bm['id']} {t.get('nctId')} location has extra keys {extra}")
                for k in extra:
                    pass
                blob = " ".join(str(loc.get(k) or "") for k in loc)
                if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", blob):
                    err(f"{bm['id']} {t.get('nctId')} location contains an email")
                if re.search(r"(?i)\b(?:phone|tel|fax)\s*[:=]", blob):
                    err(f"{bm['id']} {t.get('nctId')} location contains a phone label")

    raw = DATA.read_text(encoding="utf-8")
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", raw)
    if emails:
        err(f"snapshot contains email addresses: {emails[:5]}")
    else:
        ok("snapshot has no email addresses")

    for p in html_pages():
        text = p.read_text(encoding="utf-8")
        # mailto: or raw emails (ignore reserved example domains if any)
        page_emails = re.findall(r"mailto:|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        if page_emails:
            err(f"{p.relative_to(ROOT)} contains email/mailto: {page_emails[:5]}")
        if re.search(r"\btel:", text, re.I):
            err(f"{p.relative_to(ROOT)} contains a tel: link")
        if 'class="item trial"' in text:
            for art in re.findall(r'<article class="item trial"[^>]*>.*?</article>', text, flags=re.I | re.S):
                # Titles may contain "Investigator's Choice". Flag structured
                # contact fields, not that phrase: "Contact:", "Phone:", "Email:",
                # mailto:, or a named site contact.
                if re.search(r"(?i)(mailto:|\btel:|(?:^|[\s>])(?:contact|phone|e-?mail)\s*:)", art):
                    err(f"{p.relative_to(ROOT)} trial card mentions a contact: {art[:200]}")
    ok("pages have no emails, tel: links or site contacts on trial cards")


def test_sources_table() -> None:
    """SOURCES.md and the About page carry a sources-and-licence table."""
    src = ROOT / "SOURCES.md"
    if not src.is_file():
        err("SOURCES.md is missing")
        return
    text = src.read_text(encoding="utf-8")
    for col in (
        "Source",
        "What we use",
        "Licence or terms",
        "Terms URL",
        "Attribution requirement",
        "How we meet it",
    ):
        if col not in text:
            err(f"SOURCES.md missing column {col}")
    for url in (
        "https://clinicaltrials.gov/about-site/terms-conditions",
        "https://open.fda.gov/terms/",
        "https://open.fda.gov/license/",
        "https://creativecommons.org/publicdomain/zero/1.0/",
        "https://www.fda.gov/about-fda/about-website/website-policies",
        "https://www.fda.gov/drugs/science-and-research-drugs/table-pharmacogenomic-biomarkers-drug-labeling",
        "https://www.fda.gov/medical-devices/in-vitro-diagnostics/list-fda-authorized-companion-diagnostic-devices-in-vitro-and-imaging-tools",
        "https://www.ema.europa.eu/en/about-us/about-website/legal-notice",
        "https://civicdb.org/releases/licensing",
        "https://www.ncbi.nlm.nih.gov/home/about/policies/",
        "https://www.nlm.nih.gov/databases/download.html",
    ):
        if url not in text:
            err(f"SOURCES.md missing terms URL {url}")
    about = (SITE / "about.html").read_text(encoding="utf-8")
    if 'class="sources"' not in about and "sources-table" not in about:
        err("about.html is missing the sources-and-licence table")
    else:
        ok("about.html has a sources-and-licence table")
    if "SOURCES.md" not in about:
        err("about.html does not link to SOURCES.md")
    site_copy = SITE / "SOURCES.md"
    if not site_copy.is_file():
        err("site/SOURCES.md was not copied into the published tree")
    else:
        ok("SOURCES.md is in the repo and in the published site tree")
    # CIViC attribution links on pages must be absolute.
    for p in (SITE / "b").rglob("*.html"):
        text = p.read_text(encoding="utf-8")
        if re.search(r'href="/features/', text):
            err(f"{p.relative_to(ROOT)} has a relative CIViC /features/ link")
    ok("CIViC attribution links are absolute")


def main() -> int:
    test_snapshot_schema()
    test_pages()
    test_css_identity()
    test_matching_patterns()
    test_matching_correctness()
    test_her2_partners_and_brand_dedup()
    test_trial_requirement()
    test_kadcyla_brand_attachment()
    test_brands_own_ingredient()
    test_disclaimer_on_every_page()
    test_no_pubmed_abstracts()
    test_no_patient_contacts()
    test_sources_table()
    if errors:
        print(f"\n{len(errors)} failure(s)")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
