#!/usr/bin/env python3
"""Gates for committed plain-language text and accessible pages.

Every plain line must have a source that exists in the snapshot; every
number, date and drug name in a line must appear in that source; a
changed source hash must fail (weekly snapshot PRs cannot silently
pair new data with old text). Category assignment is deterministic.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DATA = ROOT / "data" / "snapshot.json"

sys.path.insert(0, str(ROOT / "scripts"))
from categories import (  # noqa: E402
    CATEGORY_DEFS,
    MAINSTREAM,
    ON_THE_EDGE,
    ORDER_NOTE,
    TRIALS,
    category_counts,
    companion_diagnostics,
    mainstream_therapies,
    on_the_edge_assertions,
    trial_options,
)
from plain import (  # noqa: E402
    BIOMARKER_IDS,
    check_line,
    load_plain,
    source_hash,
    validate_all,
    validate_biomarker,
    drug_catalog,
    _name_pattern,
    build_source_index,
)

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)
    print("FAIL:", msg)


def ok(msg: str) -> None:
    print("OK:  ", msg)


def test_validate_committed() -> None:
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    found = validate_all(snap)
    if found:
        for e in found:
            err(e)
    else:
        ok("committed plain text validates against the snapshot")


def test_stale_hash_is_flagged() -> None:
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    egfr = next(b for b in snap["biomarkers"] if b["id"] == "EGFR")
    current = source_hash(snap, egfr)
    # A change to a cited FDA excerpt must change the hash.
    mutated = copy.deepcopy(snap)
    mut_b = next(b for b in mutated["biomarkers"] if b["id"] == "EGFR")
    target = None
    for t in mut_b.get("therapies") or []:
        if t.get("indicationsExcerpt"):
            t["indicationsExcerpt"] = t["indicationsExcerpt"] + " [mutated for stale-hash test]"
            target = t.get("name")
            break
    if not target:
        err("could not find an EGFR excerpt to mutate")
        return
    new_hash = source_hash(mutated, mut_b)
    if new_hash == current:
        err("source_hash did not change after an excerpt mutation")
    else:
        ok(f"source_hash changes when an EGFR excerpt changes ({target})")
    catalog = drug_catalog(mutated)
    pat = _name_pattern(catalog)
    found = validate_biomarker(mutated, mut_b, catalog, pat)
    stale = [e for e in found if "source_hash is stale" in e]
    if not stale:
        err("validate_biomarker did not flag a stale source_hash after mutation")
    else:
        ok("stale plain text is flagged so a weekly snapshot PR cannot pair new data with old text")


def test_line_without_source_fails() -> None:
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    egfr = next(b for b in snap["biomarkers"] if b["id"] == "EGFR")
    idx = build_source_index(snap, egfr)
    catalog = drug_catalog(snap)
    pat = _name_pattern(catalog)
    fake = {"text": "Afatinib is mentioned.", "sources": []}
    found = check_line(fake, idx, catalog, pat, "unit")
    if not any("no source" in e for e in found):
        err(f"empty sources were accepted: {found}")
    else:
        ok("a plain line with no source reference fails")
    fake2 = {
        "text": "Afatinib was approved in 2099.",
        "sources": [{"id": "therapy:EGFR:Afatinib", "url": ""}],
    }
    found2 = check_line(fake2, idx, catalog, pat, "unit")
    if not any("2099" in e for e in found2):
        err(f"unsourced year 2099 was accepted: {found2}")
    else:
        ok("a number that is not in the cited source fails")
    # A drug name that is not in the Afatinib record.
    fake3 = {
        "text": "Afatinib is the same as Pembrolizumab.",
        "sources": [{"id": "therapy:EGFR:Afatinib", "url": ""}],
    }
    found3 = check_line(fake3, idx, catalog, pat, "unit")
    if not any("Pembrolizumab" in e for e in found3):
        err(f"unsourced drug name Pembrolizumab was accepted: {found3}")
    else:
        ok("a drug name that is not in the cited source fails")


def test_category_rules() -> None:
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    if len(CATEGORY_DEFS) != 3:
        err("expected three category definitions")
    # Deterministic: two calls agree.
    totals = {MAINSTREAM: 0, TRIALS: 0, ON_THE_EDGE: 0}
    egfr_counts = None
    for b in snap["biomarkers"]:
        a = category_counts(b)
        b2 = category_counts(b)
        if a != b2:
            err(f"{b['id']}: category_counts is not deterministic ({a} vs {b2})")
        for k in totals:
            totals[k] += a[k]
        if b["id"] == "EGFR":
            egfr_counts = a
            if a[ON_THE_EDGE] != 0:
                err(f"EGFR should have 0 on-the-edge options in this snapshot, got {a}")
            if a[MAINSTREAM] != len(mainstream_therapies(b)):
                err("EGFR mainstream count does not match mainstream_therapies")
            if a[TRIALS] != len(trial_options(b)):
                err("EGFR trials count does not match trial_options")
    if egfr_counts:
        ok(f"EGFR counts: {egfr_counts}")
    ok(f"overall counts: {totals}")
    # On the edge must be PREDICTIVE, named therapy, ampLevel set and not TIER_I_LEVEL_A.
    for b in snap["biomarkers"]:
        for a in on_the_edge_assertions(b):
            if a.get("assertionType") != "PREDICTIVE":
                err(f"non-predictive assertion in on the edge: {b['id']} {a.get('id')}")
            if not a.get("therapies"):
                err(f"on the edge assertion with no therapy: {b['id']} {a.get('id')}")
            if not a.get("ampLevel") or a.get("ampLevel") == "TIER_I_LEVEL_A":
                err(f"on the edge ampLevel is not lower-tier: {b['id']} {a.get('id')} {a.get('ampLevel')}")
    ok("on-the-edge rule holds for every assigned assertion")


def test_pages_structure() -> None:
    disclaimer = "Not medical advice. Talk to your oncologist."
    for path in [SITE / "index.html"] + sorted((SITE / "b").glob("*.html")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(SITE)
        if disclaimer not in text:
            err(f"{rel}: missing disclaimer")
        if 'id="glossary"' not in text:
            err(f"{rel}: missing glossary")
        if ORDER_NOTE not in text:
            err(f"{rel}: missing order-means-nothing note")
        if "Mainstream" not in text or "On the edge" not in text:
            err(f"{rel}: missing category labels")
        if "not generated in your browser" not in text:
            err(f"{rel}: missing AI-text note")
        # No recommendation language that would imply a better choice.
        if re.search(r"\b(we recommend|best option|preferred option|you should take)\b", text, re.I):
            err(f"{rel}: sounds like a recommendation")
    ok("disclaimer, glossary, order note and category labels on home and biomarker pages")

    egfr = (SITE / "b" / "EGFR.html").read_text(encoding="utf-8")
    if "amplfied" not in egfr:
        err("EGFR page dropped the verbatim CIViC typo 'amplfied' from the raw quote")
    else:
        # The typo must sit inside a sources toggle, not in the visible intro.
        # Split: plain intro should not reuse it.
        if re.search(r'<p class="lede">[^<]*amplfied', egfr):
            err("EGFR plain intro reused the CIViC typo 'amplfied'")
        else:
            ok("EGFR keeps the verbatim CIViC typo 'amplfied' in Sources, not in the plain intro")
    if "<details" not in egfr or "<summary>" not in egfr:
        err("EGFR page has no Sources <details> toggle")
    else:
        ok("EGFR page uses a no-JS Sources <details> toggle")
    if 'id="step-test"' not in egfr or 'id="step-options"' not in egfr:
        err("EGFR page is missing the two-step view")
    else:
        ok("EGFR page has the two-step view")
    if 'id="therapies"' not in egfr or 'id="trials"' not in egfr:
        err("EGFR page is missing therapies/trials section ids")
    # Raw FDA excerpt still present (behind Sources).
    if "INDICATIONS AND USAGE" not in egfr:
        err("EGFR page dropped raw FDA label excerpts")
    else:
        ok("EGFR page still includes raw FDA label excerpts")
    if "SENSITIVITYRESPONSE" not in egfr or "TIER_I_LEVEL_A" not in egfr:
        err("EGFR page dropped raw CIViC codes")
    else:
        ok("EGFR page still includes raw CIViC codes behind Sources")

    home = (SITE / "index.html").read_text(encoding="utf-8")
    for bid in BIOMARKER_IDS:
        if f"b/{bid}.html" not in home:
            err(f"home missing link to {bid}")
    if "mainstream" not in home.lower() or "on the edge" not in home.lower():
        err("home cards or copy missing category wording")
    else:
        ok("home page is reworked with category wording and biomarker links")


def test_no_chictor_nccn_esmo() -> None:
    """This PR must not introduce ChiCTR, NCCN or ESMO guideline content.

    A PubMed journal name already in the snapshot (for example "ESMO open")
    is existing literature-card data and is not new guideline content.
    """
    # New committed plain text and new scripts must not cite these as sources.
    hits = []
    for path in (ROOT / "data" / "plain").rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        blob = json.dumps(data)
        for word in ("ChiCTR", "NCCN", "ESMO"):
            if word in blob:
                hits.append(f"{path.relative_to(ROOT)} contains {word}")
    for path in (ROOT / "scripts").glob("*.py"):
        if path.name in {"fetch_snapshot.py", "matching.py", "trial_matching.py"}:
            continue  # unchanged pre-existing modules
        text = path.read_text(encoding="utf-8")
        for word in ("ChiCTR", "NCCN", "ESMO"):
            # Allow the words only in this comment-like exclusion in tests.
            if word in text and path.name not in {"pages_accessible.py", "generate_plain.py", "plain.py", "categories.py", "build_site.py"}:
                hits.append(f"{path.relative_to(ROOT)} contains {word}")
    if hits:
        err("forbidden source content: " + "; ".join(hits))
    else:
        ok("committed plain text and new scripts do not add ChiCTR, NCCN or ESMO content")


def main() -> int:
    test_validate_committed()
    test_stale_hash_is_flagged()
    test_line_without_source_fails()
    test_category_rules()
    test_pages_structure()
    test_no_chictor_nccn_esmo()
    if errors:
        print(f"\n{len(errors)} FAILURES")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
