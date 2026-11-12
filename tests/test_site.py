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


def main() -> int:
    test_snapshot_schema()
    test_pages()
    test_css_identity()
    if errors:
        print(f"\n{len(errors)} failure(s)")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
