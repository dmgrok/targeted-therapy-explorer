#!/usr/bin/env python3
"""Load, hash and validate committed plain-language text.

Plain text is written from snapshot fields, stored under data/plain/,
and rendered at build time. It is never generated in the browser.

Validation (a failing check fails the build):
  * every plain line has at least one source reference that resolves
    to a record in the snapshot
  * every number, date and drug name in a plain line appears in the
    cited source text from the snapshot
  * the committed source_hash matches a hash of the current snapshot
    subset, so a weekly snapshot PR is flagged when the sources moved
    rather than silently pairing new data with old text
  * every Mainstream therapy, requiring trial, On-the-edge assertion
    and companion diagnostic has a plain line, and every option line
    maps to a current option
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from categories import (
    MAINSTREAM,
    ON_THE_EDGE,
    TRIALS,
    all_option_ids,
    companion_diagnostics,
    leftover_civic,
    mainstream_therapies,
    on_the_edge_assertions,
    trial_options,
)

ROOT = Path(__file__).resolve().parents[1]
PLAIN_DIR = ROOT / "data" / "plain"

BIOMARKER_IDS = [
    "EGFR",
    "ALK",
    "BRAF-V600E",
    "KRAS-G12C",
    "HER2",
    "NTRK",
    "MSI-H-dMMR",
]

# Digit runs, including those inside dates (2022-11-11, 25/07/2013)
# and codes (L858R, G12C, NCT05498428).
NUMBER_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")

# Date-like tokens we require to appear verbatim, or as the source's
# original numeric form (handled by NUMBER_RE for 25/07/2013).
DATE_RE = re.compile(
    r"\b\d{4}-\d{2}(?:-\d{2})?\b"  # ISO
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"  # 25/07/2013
)


WORD_LIMIT = 28  # "about 25 words"; fail a little above that ("25ish").
TRIAL_LINE_PREFIXES = ("trial:",)

# Route words may appear in a plain line only when the cited source names
# a matching dosage form or schedule.
ROUTE_CLAIMS = {
    "pill": (r"\btablets?\b", r"\bpills?\b", r"\borally\b", r"\boral use\b", r"\bfor oral\b"),
    "capsule": (r"\bcapsules?\b",),
    "infusion": (r"\binfusion\b", r"\bintravenous(?:ly)?\b"),
    "daily": (r"\bdaily\b", r"\bonce a day\b", r"\bevery day\b"),
}


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", text or ""))


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _withdrawn_payload() -> dict:
    try:
        from withdrawn import load_catalog
        return load_catalog()
    except FileNotFoundError:
        return {}


def source_payload(snap: dict, biomarker: dict) -> dict:
    """Snapshot subset whose change should stale this biomarker's plain text."""
    therapies = []
    for t in mainstream_therapies(biomarker):
        therapies.append(
            {
                "name": t.get("name"),
                "brandNames": t.get("brandNames") or [],
                "genericNames": t.get("genericNames") or [],
                "indicationsExcerpt": t.get("indicationsExcerpt") or "",
                "fda": t.get("fda") or {},
                "ema": t.get("ema") or [],
                "companionDiagnostics": t.get("companionDiagnostics") or [],
                "citations": t.get("citations") or [],
                "relation": t.get("relation"),
                "relationReason": t.get("relationReason"),
                "relationEvidence": t.get("relationEvidence") or "",
            }
        )
    trials = []
    for t in trial_options(biomarker):
        trials.append(
            {
                "nctId": t.get("nctId"),
                "title": t.get("title"),
                "status": t.get("status"),
                "phases": t.get("phases") or [],
                "conditions": t.get("conditions") or [],
                "interventions": t.get("interventions") or [],
                "countries": t.get("countries") or [],
                "startDate": t.get("startDate"),
                "url": t.get("url"),
            }
        )
    civic = biomarker.get("civic") or {}
    return {
        "snapshotDate": snap.get("snapshotDate"),
        "id": biomarker.get("id"),
        "name": biomarker.get("name"),
        "fullName": biomarker.get("fullName"),
        "summary": biomarker.get("summary"),
        "summarySources": biomarker.get("summarySources") or [],
        "therapies": therapies,
        "trials": trials,
        "civicGenes": civic.get("genes") or [],
        "civicAssertions": civic.get("assertions") or [],
        "literature": biomarker.get("literature") or [],
        "cdx": companion_diagnostics(biomarker),
        "edgeIds": [a.get("id") for a in on_the_edge_assertions(biomarker)],
        "withdrawn": _withdrawn_payload(),
    }


def source_hash(snap: dict, biomarker: dict) -> str:
    return hashlib.sha256(_canon(source_payload(snap, biomarker)).encode("utf-8")).hexdigest()


def home_source_payload(snap: dict) -> dict:
    """Home-page plain text depends on the biomarker list and names."""
    return {
        "snapshotDate": snap.get("snapshotDate"),
        "biomarkers": [
            {
                "id": b.get("id"),
                "name": b.get("name"),
                "fullName": b.get("fullName"),
            }
            for b in (snap.get("biomarkers") or [])
        ],
    }


def home_source_hash(snap: dict) -> str:
    return hashlib.sha256(_canon(home_source_payload(snap)).encode("utf-8")).hexdigest()


def drug_catalog(snap: dict) -> list[str]:
    """Display names of drugs in the snapshot, longest first."""
    names: set[str] = set()
    for b in snap.get("biomarkers") or []:
        for t in b.get("therapies") or []:
            for n in (
                [t.get("name") or ""]
                + list(t.get("brandNames") or [])
                + list(t.get("genericNames") or [])
            ):
                n = (n or "").strip()
                if n and len(n) >= 3:
                    names.add(n)
            for e in t.get("ema") or []:
                for n in (e.get("name"), e.get("inn")):
                    n = (n or "").strip()
                    if n and len(n) >= 3:
                        names.add(n)
        for a in (b.get("civic") or {}).get("assertions") or []:
            for n in a.get("therapies") or []:
                n = (n or "").strip()
                if n and len(n) >= 3:
                    names.add(n)
    # Longest first so "ado-trastuzumab emtansine" wins over "trastuzumab".
    return sorted(names, key=lambda s: (-len(s), s.lower()))


def _name_pattern(catalog: list[str]) -> re.Pattern:
    parts = [re.escape(n) for n in catalog]
    # Word-ish boundaries: don't match a short name inside a longer word,
    # but do allow hyphens (fam-trastuzumab).
    return re.compile(
        r"(?<![A-Za-z0-9])(" + "|".join(parts) + r")(?![A-Za-z0-9])",
        re.I,
    )


def numbers_in(text: str) -> list[str]:
    return NUMBER_RE.findall(text or "")


def dates_in(text: str) -> list[str]:
    return [m.group(0) for m in DATE_RE.finditer(text or "")]


def drugs_in(text: str, catalog: list[str], pattern: re.Pattern | None = None) -> list[str]:
    if not text:
        return []
    pat = pattern or _name_pattern(catalog)
    found = []
    seen = set()
    for m in pat.finditer(text):
        key = m.group(0).lower()
        if key not in seen:
            seen.add(key)
            found.append(m.group(0))
    return found


def _appears(token: str, haystack: str) -> bool:
    """A claimed token must appear in the source text.

    Comparison is case-insensitive. Digit tokens may appear inside a
    larger token (L858R contains 858; PHASE2 contains 2; 25/07/2013
    contains 25, 07 and 2013).
    """
    if not token:
        return True
    h = haystack or ""
    if token in h:
        return True
    if token.lower() in h.lower():
        return True
    return False


def build_source_index(snap: dict, biomarker: dict) -> dict[str, dict]:
    """Map source id (and URL) to the snapshot text a claim can rest on."""
    idx: dict[str, dict] = {}

    def add(sid: str, url: str, text: str, label: str) -> None:
        rec = {"id": sid, "url": url or "", "text": text or "", "label": label}
        idx[sid] = rec
        if url:
            idx.setdefault(f"url:{url}", rec)

    bid = biomarker.get("id") or ""
    # Biomarker identity and CIViC gene summaries.
    ident_bits = [
        biomarker.get("id") or "",
        biomarker.get("name") or "",
        biomarker.get("fullName") or "",
        biomarker.get("summary") or "",
    ]
    add(
        f"biomarker:{bid}",
        "",
        "\n".join(ident_bits),
        f"{bid} biomarker record in this snapshot",
    )
    for src in biomarker.get("summarySources") or []:
        add(
            f"summary:{bid}",
            src.get("url") or "",
            "\n".join(ident_bits + [src.get("detail") or "", src.get("source") or ""]),
            src.get("source") or "Summary source",
        )
    civic = biomarker.get("civic") or {}
    for g in civic.get("genes") or []:
        gid = g.get("id")
        add(
            f"civic-gene:{g.get('name') or gid}",
            g.get("url") or "",
            "\n".join(
                [
                    g.get("name") or "",
                    g.get("description") or "",
                    str(g.get("id") or ""),
                    g.get("url") or "",
                ]
            ),
            f"CIViC gene summary for {g.get('name') or gid}",
        )
    for a in civic.get("assertions") or []:
        bits = [
            str(a.get("id") or ""),
            a.get("summary") or "",
            a.get("assertionType") or "",
            a.get("significance") or "",
            a.get("ampLevel") or "",
            a.get("status") or "",
            a.get("disease") or "",
            a.get("molecularProfile") or "",
            " ".join(a.get("therapies") or []),
            a.get("url") or "",
        ]
        add(
            f"civic:{a.get('id')}",
            a.get("url") or "",
            "\n".join(bits),
            f"CIViC assertion {a.get('id')}",
        )
    for t in mainstream_therapies(biomarker):
        name = t.get("name") or ""
        bits = [
            name,
            " ".join(t.get("brandNames") or []),
            " ".join(t.get("genericNames") or []),
            t.get("indicationsExcerpt") or "",
            t.get("relationEvidence") or "",
            t.get("relationReason") or "",
            json.dumps(t.get("fda") or {}, ensure_ascii=False),
            json.dumps(t.get("ema") or [], ensure_ascii=False),
            json.dumps(t.get("companionDiagnostics") or [], ensure_ascii=False),
            json.dumps(t.get("citations") or [], ensure_ascii=False),
        ]
        # Also flatten EMA dates and names explicitly.
        for e in t.get("ema") or []:
            bits.extend(
                [
                    e.get("name") or "",
                    e.get("inn") or "",
                    e.get("status") or "",
                    e.get("authorisationDate") or "",
                    e.get("url") or "",
                ]
            )
        fda = t.get("fda") or {}
        url = (
            fda.get("dailymedUrl")
            or fda.get("drugsfdaUrl")
            or ""
        )
        for c in t.get("citations") or []:
            if c.get("url") and not url:
                url = c["url"]
        add(
            f"therapy:{bid}:{name}",
            url,
            "\n".join(bits),
            f"FDA / EMA record for {name}",
        )
        for c in t.get("citations") or []:
            if c.get("url"):
                add(
                    f"cite:{bid}:{name}:{c.get('source')}",
                    c.get("url") or "",
                    "\n".join(bits + [c.get("source") or "", c.get("detail") or ""]),
                    c.get("source") or "Citation",
                )
    for t in trial_options(biomarker):
        nct = t.get("nctId") or ""
        src = t.get("source") or {}
        if isinstance(src, dict):
            src_text = " ".join(str(v) for v in src.values())
        else:
            src_text = str(src)
        bits = [
            nct,
            t.get("title") or "",
            t.get("status") or "",
            " ".join(t.get("phases") or []),
            " ".join(t.get("conditions") or []),
            " ".join(t.get("interventions") or []),
            " ".join(t.get("countries") or []),
            f"{len(t.get('countries') or [])} countries",
            f"{len(t.get('countries') or [])} country",
            t.get("startDate") or "",
            t.get("url") or "",
            src_text,
            t.get("requirementReason") or "",
            t.get("requirementEvidence") or "",
        ]
        add(
            f"trial:{nct}",
            t.get("url") or "",
            "\n".join(bits),
            f"ClinicalTrials.gov {nct}",
        )
    for c in companion_diagnostics(biomarker):
        bits = [
            c.get("diagnostic") or "",
            c.get("indication") or "",
            c.get("sampleType") or "",
            c.get("url") or "",
            c.get("viaTherapy") or "",
            "FDA",
            "companion diagnostic",
        ]
        add(
            f"cdx:{c.get('diagnostic')}|{c.get('indication')}",
            c.get("url") or "",
            "\n".join(bits),
            "FDA companion diagnostic",
        )
    # Site-level method statements (for "what a test report means",
    # category wording, and the home intro). These texts are the
    # explorer's own method, already implemented in code.
    add(
        "method:categories",
        "",
        (
            "Mainstream Trials On the edge "
            "FDA-approved for this biomarker "
            "recruiting ClinicalTrials.gov "
            "selection criterion "
            "companion diagnostic "
            "pharmacogenomic "
            "CIViC PREDICTIVE ampLevel TIER_I_LEVEL_A "
            "TIER_II_LEVEL_C TIER_II_LEVEL_D "
            "Not medical advice. Talk to your oncologist. "
            "plain-language committed snapshot "
            "not generated in your browser "
            "Options are grouped by category, then listed alphabetically. "
            "That order does not mean one option is better than another. "
            "This page lists public FDA companion diagnostics "
            "therapies and trials in this snapshot that use this biomarker "
            "as a selection criterion. "
            "That mention is not a diagnosis or a treatment decision "
            "on its own. "
            "A test report that mentions this biomarker is recording a "
            "finding about it."
        ),
        "Category and method rules in this repository",
    )

    # Whole-product withdrawal records (committed catalog, opened sources).
    try:
        from withdrawn import load_catalog
        catalog = load_catalog()
    except Exception:
        catalog = {"entries": []}
    for entry in list(catalog.get("entries") or []) + list(catalog.get("indication_level_noted") or []):
        bits = [
            entry.get("id") or "",
            " ".join(entry.get("names") or []),
            entry.get("effective_date") or entry.get("withdrawal_date") or "",
            entry.get("status") or "",
            entry.get("indication") or "",
            json.dumps(entry, ensure_ascii=False),
        ]
        url = ""
        for s in entry.get("sources") or []:
            if s.get("url"):
                url = s["url"]
                bits.extend([s.get("label") or "", s.get("url") or "", s.get("date") or "", s.get("detail") or ""])
        if not url and isinstance(entry.get("source"), dict):
            url = entry["source"].get("url") or ""
            bits.append(json.dumps(entry["source"], ensure_ascii=False))
        add(
            f"withdrawn:{entry.get('id')}",
            url,
            "\n".join(bits),
            "Withdrawal record",
        )
        add(
            "method:withdrawn",
            "",
            "\n".join(bits),
            "Withdrawal catalog",
        )

    return idx


def resolve_sources(refs: list, index: dict) -> tuple[list[dict], list[str]]:
    """Resolve each source ref to a snapshot record. Returns (hits, errors)."""
    hits = []
    errors = []
    for ref in refs or []:
        sid = (ref.get("id") or "").strip()
        url = (ref.get("url") or "").strip()
        rec = None
        if sid and sid in index:
            rec = index[sid]
        elif url and f"url:{url}" in index:
            rec = index[f"url:{url}"]
        if rec is None:
            errors.append(f"source does not resolve: id={sid!r} url={url!r}")
            continue
        hits.append(rec)
    return hits, errors


def combined_source_text(hits: list[dict]) -> str:
    return "\n".join(h.get("text") or "" for h in hits)


def check_line(
    line: dict,
    index: dict,
    catalog: list[str],
    name_pat: re.Pattern,
    where: str,
) -> list[str]:
    errors = []
    text = line.get("text") or ""
    if not text.strip():
        errors.append(f"{where}: empty plain text")
        return errors
    refs = line.get("sources") or []
    if not refs:
        errors.append(f"{where}: no source references")
        return errors
    hits, res_err = resolve_sources(refs, index)
    errors.extend(f"{where}: {e}" for e in res_err)
    if not hits:
        return errors
    hay = combined_source_text(hits)
    for n in numbers_in(text):
        if not _appears(n, hay):
            errors.append(
                f"{where}: number {n!r} in {text!r} is not in the cited source"
            )
    for d in dates_in(text):
        if not _appears(d, hay):
            errors.append(
                f"{where}: date {d!r} in {text!r} is not in the cited source"
            )
    for drug in drugs_in(text, catalog, name_pat):
        if not _appears(drug, hay):
            errors.append(
                f"{where}: drug name {drug!r} in {text!r} is not in the cited source"
            )
    # Route / schedule claims: only if the label (or cited source) names them.
    low = text.lower()
    for claim, pats in ROUTE_CLAIMS.items():
        if re.search(r"\b" + re.escape(claim) + r"\b", low):
            if not any(re.search(p, hay, re.I) for p in pats):
                errors.append(
                    f"{where}: claimed {claim!r} in {text!r} but the cited source "
                    "does not name a matching dosage form or schedule"
                )
    # Word-count gate for option lines (not trial title lines, not the test-report sentence).
    lid = (line.get("id") or "")
    cat = (line.get("category") or "")
    skip_wc = (
        cat == "trials"
        or lid.startswith("trial:")
        or "test_report" in where
        or lid.startswith("home:")
    )
    if not skip_wc:
        n = word_count(text)
        if n > WORD_LIMIT:
            errors.append(
                f"{where}: {n} words (limit {WORD_LIMIT}, target about 25) in {text!r}"
            )
    return errors


def load_plain(biomarker_id: str) -> dict:
    path = PLAIN_DIR / f"{biomarker_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing plain text {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_home_plain() -> dict:
    path = PLAIN_DIR / "home.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing plain text {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_glossary() -> dict:
    path = PLAIN_DIR / "glossary.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing glossary {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_biomarker(snap: dict, biomarker: dict, catalog: list[str], name_pat: re.Pattern) -> list[str]:
    bid = biomarker["id"]
    errors: list[str] = []
    try:
        data = load_plain(bid)
    except FileNotFoundError as e:
        return [str(e)]
    expected_hash = source_hash(snap, biomarker)
    got_hash = data.get("source_hash") or ""
    if got_hash != expected_hash:
        errors.append(
            f"{bid}: source_hash is stale "
            f"(committed {got_hash[:16]}…, current {expected_hash[:16]}…). "
            "Regenerate data/plain/{bid}.json from the new snapshot; "
            "do not silently pair new data with old text."
        )
    if not data.get("generated_at"):
        errors.append(f"{bid}: missing generated_at")
    index = build_source_index(snap, biomarker)

    # Intro lines.
    intro = data.get("intro") or {}
    what = intro.get("what") or []
    if len(what) != 2:
        errors.append(f"{bid}: intro.what must be exactly 2 sentences, got {len(what)}")
    for i, sent in enumerate(what):
        fake = {"text": sent, "sources": intro.get("sources") or []}
        errors.extend(check_line(fake, index, catalog, name_pat, f"{bid} intro.what[{i}]"))
    report = intro.get("test_report") or ""
    fake = {"text": report, "sources": intro.get("test_report_sources") or intro.get("sources") or []}
    errors.extend(check_line(fake, index, catalog, name_pat, f"{bid} intro.test_report"))

    lines = data.get("lines") or []
    by_id = {}
    for i, line in enumerate(lines):
        lid = (line.get("id") or "").strip()
        if not lid:
            errors.append(f"{bid} lines[{i}]: missing id")
            continue
        if lid in by_id:
            errors.append(f"{bid}: duplicate line id {lid}")
        by_id[lid] = line
        errors.extend(check_line(line, index, catalog, name_pat, f"{bid} {lid}"))

    expected = set(all_option_ids(biomarker))
    got = set(by_id)
    missing = expected - got
    extra = got - expected
    if missing:
        errors.append(f"{bid}: plain text missing lines for {sorted(missing)}")
    if extra:
        errors.append(f"{bid}: plain text has leftover lines {sorted(extra)}")
    return errors


def validate_home(snap: dict, catalog: list[str], name_pat: re.Pattern) -> list[str]:
    errors: list[str] = []
    try:
        data = load_home_plain()
    except FileNotFoundError as e:
        return [str(e)]
    expected = home_source_hash(snap)
    got = data.get("source_hash") or ""
    if got != expected:
        errors.append(
            f"home: source_hash is stale "
            f"(committed {got[:16]}…, current {expected[:16]}…). "
            "Regenerate data/plain/home.json."
        )
    # Home intro has no drug-specific claims; still check numbers/dates/drugs.
    # Build a tiny index from method + biomarker names.
    # Use EGFR's method source plus all biomarker identity records.
    # We'll construct a combined home index.
    idx: dict[str, dict] = {}
    text_bits = [
        "Targeted Therapy Explorer",
        "approved targeted therapies",
        "recruiting clinical trials",
        "biomarker",
        "Not medical advice. Talk to your oncologist.",
        "public sources",
        "FDA",
        "EMA",
        "ClinicalTrials.gov",
        "CIViC",
        "Mainstream",
        "Trials",
        "On the edge",
        "closed list",
        "EGFR",
        "ALK",
        "BRAF V600E",
        "KRAS G12C",
        "HER2",
        "NTRK",
        "MSI-H / dMMR",
        "snapshot",
    ]
    for b in snap.get("biomarkers") or []:
        text_bits.extend([b.get("id") or "", b.get("name") or "", b.get("fullName") or ""])
    idx["method:home"] = {
        "id": "method:home",
        "url": "",
        "text": "\n".join(text_bits),
        "label": "This explorer's method and biomarker list",
    }
    # Allow URL-less method refs.
    for line in data.get("lines") or []:
        errors.extend(check_line(line, idx, catalog, name_pat, f"home {line.get('id')}"))
    intro = data.get("intro") or {}
    for i, sent in enumerate(intro.get("what") or []):
        fake = {"text": sent, "sources": intro.get("sources") or [{"id": "method:home"}]}
        errors.extend(check_line(fake, idx, catalog, name_pat, f"home intro.what[{i}]"))
    return errors


def validate_glossary() -> list[str]:
    """Glossary is general wording. Reject empty terms; no invented numbers."""
    errors = []
    try:
        data = load_glossary()
    except FileNotFoundError as e:
        return [str(e)]
    terms = data.get("terms") or []
    if not terms:
        errors.append("glossary is empty")
    required = {"biomarker", "mutation", "tki", "nsclc"}
    got = {(t.get("term") or "").strip().lower() for t in terms}
    # Allow "TKI (tyrosine kinase inhibitor)" etc.
    got_folded = set()
    for t in terms:
        term = (t.get("term") or "").strip()
        if not term or not (t.get("text") or "").strip():
            errors.append(f"glossary: empty term or definition: {t}")
            continue
        got_folded.add(term.lower())
        got_folded.add(term.split("(")[0].strip().lower())
        # Numbers in a glossary definition need to be argued; flag them
        # so we do not slip in unsourced figures.
        nums = numbers_in(t.get("text") or "")
        allowed = set(t.get("allowed_numbers") or [])
        for n in nums:
            if n not in allowed:
                errors.append(
                    f"glossary {term!r}: unsourced number {n!r} "
                    "(list it in allowed_numbers only if it is defined in the text as a term, not a statistic)"
                )
    for r in required:
        if r not in got_folded:
            errors.append(f"glossary missing required term {r!r}")
    return errors


def validate_all(snap: dict) -> list[str]:
    catalog = drug_catalog(snap)
    name_pat = _name_pattern(catalog)
    errors: list[str] = []
    errors.extend(validate_glossary())
    errors.extend(validate_home(snap, catalog, name_pat))
    by_id = {b["id"]: b for b in snap.get("biomarkers") or []}
    for bid in BIOMARKER_IDS:
        b = by_id.get(bid)
        if not b:
            errors.append(f"snapshot missing biomarker {bid}")
            continue
        errors.extend(validate_biomarker(snap, b, catalog, name_pat))
    errors.extend(validate_withdrawn(snap))
    return errors


def validate_withdrawn(snap: dict) -> list[str]:
    """Whole-product withdrawals must not appear as Mainstream.

    Indication-level notes are reported, not treated as whole-product drops.
    A stale catalog entry (names match no snapshot therapy) fails the gate.
    """
    from withdrawn import (
        display_mainstream,
        is_withdrawn,
        report_catalog_against_snapshot,
    )

    errors: list[str] = []
    report = report_catalog_against_snapshot(snap)
    for sid in report.get("stale_entries") or []:
        errors.append(
            f"withdrawn catalog entry {sid} matches no therapy in this snapshot; "
            "update data/withdrawn.json"
        )
    for b in snap.get("biomarkers") or []:
        for t in display_mainstream(b):
            if is_withdrawn(t):
                errors.append(
                    f"{b['id']}: {t.get('name')} is a whole-product withdrawal "
                    "but is still in the displayed Mainstream list"
                )
    return errors


def line_by_id(data: dict, lid: str) -> dict | None:
    for line in data.get("lines") or []:
        if line.get("id") == lid:
            return line
    return None
