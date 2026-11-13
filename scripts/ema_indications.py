#!/usr/bin/env python3
"""Indication-level EU approval phrasing from data/ema_indications.json.

The 'Approved where, and since when' Europe part is matched to the
leaf's cancer, gene-change subtype and when-used, against the current
EPAR therapeutic indication and against later 'Extension of indication'
procedures. A year is the Commission Decision year of a matching
extension, or the marketing-authorisation year when the indication is
shown to be original. A date is never inferred.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from tree import (  # noqa: E402
    LABEL_UNKNOWN_CANCER,
    LABEL_UNKNOWN_MUTATION,
    LABEL_UNKNOWN_WHEN,
    cancers_in,
    mutations_in,
    whens_in,
)

V600_FAMILY = {"BRAF V600", "BRAF V600E", "BRAF V600K"}
EGFR_ACTIVATING = {
    "EGFR exon 19 deletion or L858R",
    "EGFR gene changes the label lists as non-resistant",
    "EGFR gene change (no more precise subtype in the text)",
}
# 'after surgery' / 'after chemoradiation' / 'as maintenance' are
# specific settings. A general metastatic EU unit (no when named)
# does not cover them.
SPECIFIC_WHENS = {"after surgery", "after chemoradiation", "as maintenance"}

RESTRICTION = re.compile(
    r"restriction of the indication|"
    r"modification of the indication to limit|"
    r"to limit (?:the )?(?:maintenance |indication )|"
    r"limit maintenance",
    re.I,
)
COMBO_OR_AGE_ADD = re.compile(
    r"\b(?:add(?:ition)?(?: of)?(?: a)?(?: new)?(?: therapeutic)?"
    r"(?: indication)?(?: for)?(?: the)?(?: use)?(?: in)? combination|"
    r"to include the combination|"
    r"in combination of |"
    r"use in combination|"
    r"adolescents aged|"
    r"patients from \d+ month|"
    r"paediatric patients|"
    r"to patients from)",
    re.I,
)


def tidy_procedural_desc(desc: str) -> str:
    """Join hyphen-broken words. Do not delete citation phrases: on
    two-column PDFs they are interleaved with the indication wording.
    """
    d = desc or ""
    # Footnotes sometimes sit between "first-" and "line".
    d = re.sub(
        r"first-\s*(?:\d[^.]{0,600}?)?\s*line treatment",
        "first-line treatment",
        d,
        flags=re.I,
    )
    d = re.sub(r"first-\s+line", "first-line", d)
    d = re.sub(r"(\w+)-\s+(\w+)", r"\1-\2", d)
    d = re.sub(r"\s+", " ", d)
    return d.strip()


def eu_cancers_in(text: str) -> list[str]:
    """Cancer types in EU wording; mask 'Regulation (EC)' so the EC
    abbreviation cannot be read as endometrial cancer.
    """
    masked = re.sub(
        r"Regulation\s*\(EC\)|Commission Regulation\s*\(EC\)|\(EC\)\s*No",
        " ",
        text or "",
        flags=re.I,
    )
    return cancers_in(masked)


def eu_whens_in(text: str) -> list[str]:
    """When-used labels for EU wording, without changing the FDA tree rules.

    Masks 'after … first-line chemotherapy', which would otherwise fire
    the 'first-line' pattern, and recognises TKI-naïve and 'progressed
    on or following' wording common on EPARs.
    """
    masked = re.sub(
        r"(?:after|following|post)(?:\s+\d+\s+cycles of)?"
        r"(?:\s+standard)?(?:\s+platinum(?:-based)?)?\s+first[- ]line",
        " PRIOR_LINE ",
        text or "",
        flags=re.I,
    )
    found = list(whens_in(masked))
    if re.search(r"TKI[- ]na[iïí]ve|EGFR TKI[- ]na", text or "", re.I):
        if "as a first treatment" not in found:
            found.append("as a first treatment")
    if re.search(
        r"has progressed|that has progressed|progressed on or following|"
        r"progressing on or after|following prior|after failure of|"
        r"previously treated",
        text or "",
        re.I,
    ):
        if "after another drug" not in found:
            found.append("after another drug")
    # Jemperli 2023: "primary advanced or recurrent … candidates for
    # systemic therapy" is the first-line wording, without the words
    # "first-line". Do not apply if the same unit also describes
    # progression after prior therapy.
    if (
        "as a first treatment" not in found
        and re.search(r"candidates for systemic therapy", text or "", re.I)
        and not re.search(r"progressed|previously treated|after failure", text or "", re.I)
    ):
        found.append("as a first treatment")
    return found


@lru_cache(maxsize=1)
def _catalog() -> dict:
    path = ROOT / "data" / "ema_indications.json"
    if not path.is_file():
        return {"products": [], "by_name": {}, "by_url": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    by_name = {}
    by_url = {}
    by_slug = {}
    for p in data.get("products") or []:
        by_name[(p.get("name") or "").strip().lower()] = p
        url = (p.get("url") or "").rstrip("/")
        if url:
            by_url[url] = p
        if p.get("slug"):
            by_slug[p["slug"].lower()] = p
    data["by_name"] = by_name
    data["by_url"] = by_url
    data["by_slug"] = by_slug
    return data


def _unknown(label: str) -> bool:
    return (not label) or ("does not say" in (label or ""))


def split_indication_units(text: str) -> list[str]:
    """Split a current Therapeutic indication field into use units."""
    if not text:
        return []
    t = text.strip()
    # Split on a sentence end, including list items that start with "the ".
    parts = re.split(r"(?<=\.)\s+(?=(?:[A-Z]|the\s))", t)
    # Also split Tyverb-style "; in combination" / "; for patients" lists.
    finer: list[str] = []
    for p in parts:
        bits = re.split(
            r";\s+(?=(?:in combination|for (?:the |patients|post-)|"
            r"locally|the treatment|treatment of))",
            p,
        )
        finer.extend(b.strip() for b in bits if b.strip())
    # Merge a short heading (no "indicated") with the next unit.
    units: list[str] = []
    buf = ""
    for s in finer:
        heading = "indicated" not in s.lower() and len(s) < 90
        if heading:
            buf = (buf + " " + s).strip()
            continue
        units.append((buf + " " + s).strip() if buf else s)
        buf = ""
    if buf:
        if units:
            units[-1] = (units[-1] + " " + buf).strip()
        else:
            units.append(buf)
    # Xalkori-style lists: "The first line treatment of … The treatment of …"
    # with no sentence period between items.
    expanded: list[str] = []
    for u in (units or [t]):
        bits = re.split(
            r"(?=\bThe (?:first[- ]line )?treatment of\b)",
            u,
        )
        bits = [b.strip() for b in bits if b.strip()]
        expanded.extend(bits if len(bits) > 1 else [u])
    return expanded or [t]


def mutation_compatible(eu_muts: list[str], eu_text: str, leaf_mut: str) -> bool:
    if _unknown(leaf_mut):
        return True
    if leaf_mut in eu_muts:
        return True
    if "BRAF V600" in eu_muts and leaf_mut in V600_FAMILY:
        return True
    if leaf_mut == "BRAF V600" and any(m in eu_muts for m in V600_FAMILY):
        return True
    eu_has_t790m = "EGFR T790M" in eu_muts
    eu_has_ex20 = "EGFR exon 20 insertion" in eu_muts
    if eu_has_t790m and leaf_mut == "EGFR T790M":
        return True
    # "activating EGFR mutations" is a parent of exon 19 / L858R and of
    # an unspecified EGFR gene change, not of T790M or exon 20 insertion.
    eu_activating = bool(
        re.search(r"activating\s+(?:EGFR|epidermal)", eu_text, re.I)
        or re.search(r"EGFR\s+activating", eu_text, re.I)
        or "EGFR gene change (no more precise subtype in the text)" in eu_muts
        or "EGFR gene changes the label lists as non-resistant" in eu_muts
    )
    if eu_activating and not eu_has_t790m and not eu_has_ex20:
        if leaf_mut in EGFR_ACTIVATING:
            return True
    return False


def when_compatible(eu_whens: list[str], leaf_when: str) -> bool:
    if leaf_when == "__general__":
        # Only units/extensions that are themselves general (no
        # adjuvant / chemoradiation / maintenance when).
        if any(w in SPECIFIC_WHENS for w in eu_whens):
            return False
        return True
    if _unknown(leaf_when):
        return True
    if not eu_whens:
        # A general metastatic / advanced unit is not adjuvant or
        # post-chemoradiation.
        if leaf_when in SPECIFIC_WHENS:
            return False
        return True
    return leaf_when in eu_whens


def cancer_compatible(eu_cancers: list[str], leaf_cancer: str) -> bool:
    if _unknown(leaf_cancer):
        return True
    if leaf_cancer in eu_cancers:
        return True
    return False



# Leaf mutation family → tokens that identify a *different* biomarker
# in EU wording. A ROS1-only unit must not match an ALK leaf.
_LEAF_FAMILY = {
    "EGFR exon 20 insertion": "EGFR",
    "EGFR exon 19 deletion or L858R": "EGFR",
    "EGFR T790M": "EGFR",
    "EGFR gene changes the label lists as non-resistant": "EGFR",
    "EGFR gene change (no more precise subtype in the text)": "EGFR",
    "ALK fusion or ALK-positive": "ALK",
    "BRAF V600E": "BRAF",
    "BRAF V600K": "BRAF",
    "BRAF V600": "BRAF",
    "KRAS G12C": "KRAS",
    "KRAS wild-type (no KRAS change)": "KRAS",
    "HER2-positive": "HER2",
    "HER2-low": "HER2",
    "HER2 mutation": "HER2",
    "NTRK fusion": "NTRK",
    "MSI-H or dMMR": "MSI",
}
_FAMILY_PATTERNS = {
    "EGFR": r"\bEGFR\b|epidermal growth factor receptor",
    "ALK": r"\bALK\b|anaplastic lymphoma kinase",
    "ROS1": r"\bROS1\b",
    "BRAF": r"\bBRAF\b",
    "KRAS": r"\bKRAS\b|\bK-Ras\b|\bRAS\b",
    "HER2": r"\bHER2\b|\bHER-2\b|\bERBB2\b",
    "NTRK": r"\bNTRK\b|neurotrophic",
    "MSI": r"\bMSI\b|microsatellite|\bdMMR\b|mismatch repair",
    "RET": r"\bRET\b",
    "MET": r"\bMET\b",
    "NTRK_ONLY": r"\bNTRK\b",
}


def _conflicting_biomarker(text: str, leaf_mut: str) -> bool:
    """True when the EU unit names a different biomarker and not the leaf's."""
    if _unknown(leaf_mut):
        return False
    family = _LEAF_FAMILY.get(leaf_mut)
    named = []
    for fam, pat in _FAMILY_PATTERNS.items():
        if fam == "NTRK_ONLY":
            continue
        if re.search(pat, text or "", re.I):
            named.append(fam)
    if not named:
        return False
    if family and family in named:
        return False
    # Named something else (e.g. ROS1) and not the leaf family.
    return True


def unit_matches(text: str, triple: tuple[str, str, str]) -> bool:
    """True if this EU wording covers the leaf's cancer, mutation and when."""
    if not text or not triple:
        return False
    cancer, mutation, when = triple
    text = tidy_procedural_desc(text)
    eu_cancers = eu_cancers_in(text)
    eu_muts = mutations_in(text)
    eu_whens = eu_whens_in(tidy_procedural_desc(text))
    if not cancer_compatible(eu_cancers, cancer):
        return False
    if not mutation_compatible(eu_muts, text, mutation):
        # An EU unit that names no biomarker still covers the cancer
        # (all-comers), unless it names a conflicting mutation.
        if eu_muts:
            return False
        # No mutation named: allow, cancer already matched.
    if _conflicting_biomarker(text, mutation):
        return False
    if not when_compatible(eu_whens, when):
        return False
    return True


def _is_restriction(desc: str) -> bool:
    return bool(RESTRICTION.search(desc or ""))


def _products_for(therapy: dict) -> list[dict]:
    """Authorised EMA products for this therapy, in catalog form."""
    cat = _catalog()
    found = []
    seen = set()
    for e in therapy.get("ema") or []:
        if (e.get("status") or "").lower() != "authorised":
            continue
        url = (e.get("url") or "").rstrip("/")
        name = (e.get("name") or "").strip().lower()
        p = cat["by_url"].get(url) or cat["by_name"].get(name)
        if p and id(p) not in seen:
            seen.add(id(p))
            found.append(p)
    return found


def _extensions_complete(product: dict) -> bool:
    """True if we can treat the parsed extension list as complete.

    Remainder (original) indications only receive the marketing-
    authorisation year when this is true. An under-count must not
    assign the first-authorisation year to a later indication.
    """
    parsed = product.get("n_extension_parsed") or 0
    index = product.get("n_extension_index") or 0
    ci6 = product.get("n_CI6_index") or 0
    if index == 0 and ci6 == 0:
        return True
    return parsed >= index


def _ma_year_applies(
    product: dict,
    triple: tuple[str, str, str],
    matched_units: list[str],
    matching_additions: list[dict],
) -> bool:
    """True when the original MA year can be used for this leaf.

    The MA year is used when the indication is shown to be original:
    no later extensions at all, or a complete parse in which a matching
    current-TI unit is not one that an extension first introduced as a
    new cancer or a new when-used (a later combination or age extension
    of the same cancer and when does not replace the original year).
    """
    if not product.get("ma_year"):
        return False
    if not _extensions_complete(product):
        return False
    additions = [
        e
        for e in (product.get("extensions") or [])
        if not _is_restriction(e.get("description") or "")
    ]
    if not additions:
        return True
    # A matching TI unit is original if no addition introduced this
    # cancer + when as a new population.
    for unit in matched_units:
        unit_introduced = False
        # Compare extensions to this unit's own when, not the leaf's.
        # An unknown-when leaf matches every when; using it here would
        # treat a later first-line extension as introducing a remainder
        # monotherapy unit.
        unit_whens = eu_whens_in(tidy_procedural_desc(unit))
        # A general unit (no when) must not inherit the leaf's
        # "label does not say when", which would match every extension
        # for this cancer. Use a sentinel that only matches general
        # (non-adjuvant, non-chemoradiation) EU wording.
        unit_when = unit_whens[0] if unit_whens else "__general__"
        unit_triple = (triple[0], triple[1], unit_when)
        for ext in additions:
            desc = ext.get("description") or ""
            if not unit_matches(desc, unit_triple) and not _same_cancer_when(unit, desc):
                continue
            # Combination or age extension of an already-authorised
            # cancer+when: the monotherapy / adult use was original.
            # A combination or age extension of an already-authorised
            # monotherapy / adult use does not replace the original year.
            # Only apply that shortcut when the current TI unit itself
            # still describes monotherapy (or adult use being extended).
            # A new indication that arrives already as a combination
            # (Tafinlar lung, Xalkori IMT) is introduced by the extension.
            if COMBO_OR_AGE_ADD.search(desc) and _same_cancer_when(unit, desc):
                ext_whens = eu_whens_in(tidy_procedural_desc(desc))
                unit_whens = eu_whens_in(tidy_procedural_desc(unit))
                if ext_whens and not any(w in unit_whens for w in ext_whens):
                    if unit_triple[2] in ext_whens:
                        unit_introduced = True
                        break
                if re.search(
                    r"as monotherapy or in combination|as monotherapy",
                    unit,
                    re.I,
                ):
                    continue
                if re.search(
                    r"adolescents aged|to patients from",
                    desc,
                    re.I,
                ) and re.search(r"\badults\b", unit, re.I):
                    continue
            # Extension covers this unit's use as a new indication.
            if unit_matches(desc, unit_triple):
                unit_introduced = True
                break
        if not unit_introduced:
            return True
    return False


def _same_cancer_when(a: str, b: str) -> bool:
    ca, wa = eu_cancers_in(a), eu_whens_in(tidy_procedural_desc(a))
    cb, wb = eu_cancers_in(b), eu_whens_in(tidy_procedural_desc(b))
    if not ca or not cb:
        return False
    if not any(c in cb for c in ca):
        return False
    # Both general (no when) or overlapping when.
    if not wa and not wb:
        return True
    if wa and wb and any(w in wb for w in wa):
        return True
    return False


def match_product(product: dict, triple: tuple[str, str, str]) -> tuple[str, int | None]:
    """Return ('year', y) | ('approved', None) | ('other', None) for one EPAR."""
    ti = product.get("therapeutic_indication") or ""
    units = split_indication_units(ti)
    matched_units = [u for u in units if unit_matches(u, triple)]
    if not matched_units:
        # Whole-TI fallback, only if splitting dropped a match.
        if unit_matches(ti, triple):
            matched_units = [ti]
        else:
            return ("other", None)

    years: list[int] = []
    matching_adds: list[dict] = []
    for ext in product.get("extensions") or []:
        desc = ext.get("description") or ""
        if _is_restriction(desc):
            continue
        if not unit_matches(desc, triple):
            continue
        matching_adds.append(ext)
        year = ext.get("year") or ""
        if year and year.isdigit():
            years.append(int(year))

    if _ma_year_applies(product, triple, matched_units, matching_adds):
        try:
            years.append(int(product["ma_year"]))
        except (TypeError, ValueError):
            pass

    if years:
        return ("year", min(years))
    # Indication is on the EU label, but no sourced year for this use.
    return ("approved", None)


def europe_phrase(therapy: dict, triple: tuple[str, str, str] | None) -> str:
    """Europe part of the approval cell, or '' if the drug has no EU MA."""
    products = _products_for(therapy)
    if not products:
        return ""
    if not triple:
        # Without leaf context we must not show a drug-level year.
        return "Europe: approved"

    results = [match_product(p, triple) for p in products]
    years = [y for (kind, y) in results if kind == "year" and y is not None]
    any_approved = any(kind == "approved" for kind, _ in results)
    if years and any_approved:
        # A matching product has the indication but no sourced year
        # (often the original, when the extension parse is incomplete).
        # Do not show a later biosimilar's MA year as the first year.
        return "Europe: approved"
    if years:
        return f"Europe since {min(years)}"
    if any_approved:
        return "Europe: approved"
    return "Europe: approved for other uses"


def europe_sources(therapy: dict) -> list[dict]:
    """EPAR URLs used for this therapy, for change-list reporting."""
    out = []
    for p in _products_for(therapy):
        out.append(
            {
                "name": p.get("name"),
                "url": p.get("url"),
                "current_pdf_url": p.get("current_pdf_url"),
                "archive_pdf_url": p.get("archive_pdf_url"),
            }
        )
    return out
