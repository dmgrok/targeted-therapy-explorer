#!/usr/bin/env python3
"""Classify whether a therapy actually targets a biomarker.

A therapy *targets* a biomarker only when the label indication, the FDA
pharmacogenomic-biomarker table, or an FDA companion-diagnostic row ties the
drug to that biomarker as a *selection criterion* (for example "whose tumors
have EGFR exon 19 deletions", or a PGx labeling section of Indications and
Usage in which the biomarker is the selection criterion).

Mentions that are exclusions ("no EGFR or ALK genomic tumor aberrations"),
opposite-status indications ("HER2-negative"), or incidental ("biomarker
mentioned in the label") are kept in the snapshot with a relation other than
"targets", and must not be rendered on the pages.

This module is deliberately text-driven: it does not hard-code drug names.
"""
from __future__ import annotations

import re
import unicodedata

# Relations stored on each therapy in the snapshot.
TARGETS = "targets"
MENTIONED = "mentioned"  # mentioned in the label / tables, not a selection criterion
EXCLUSION = "exclusion"  # mentioned as a negative / opposite-status criterion

# Patterns that identify the biomarker in running text (label, CDx, PGx).
# Longer, more specific forms come first.
BIOMARKER_PATTERNS: dict[str, list[str]] = {
    "EGFR": [
        r"epidermal growth factor receptor(?:\s*\(\s*EGFR\s*\))?",
        r"EGF receptor",
        r"\bEGFR\b",
    ],
    "ALK": [
        r"anaplastic lymphoma kinase(?:\s*\(\s*ALK\s*\))?",
        r"\bALK\b",
    ],
    "BRAF-V600E": [
        r"\bBRAF(?:\s*V600[A-Z]?)?\b",
        r"\bV600E\b",
        r"\bV600K\b",
        r"\bV600\b",
    ],
    "KRAS-G12C": [
        r"\bKRAS(?:\s*G12C)?\b",
        r"\bG12C\b",
        r"\bRAS\b",
    ],
    "HER2": [
        r"human epidermal growth factor receptor\s*2(?:\s*\(\s*HER-?2\s*\))?",
        r"\bHER-?2(?:/neu)?\b",
        r"\bERBB[- ]?2\b",
    ],
    "NTRK": [
        r"neurotrophic (?:tyrosine )?receptor tyrosine kinase",
        r"neurotrophic tyrosine receptor kinase",
        r"\bNTRK\d?\b",
        r"\bTRK\b",
    ],
    "MSI-H-dMMR": [
        r"microsatellite instability(?:\s*[-–]?\s*high)?",
        r"\bMSI(?:\s*[-–]?\s*H(?:igh)?)?\b",
        r"mismatch[- ]repair(?:\s+deficien(?:t|cy))?",
        r"\bdMMR\b",
        r"\bMMR\b",
        r"MMR[- ]deficien(?:t|cy)",
    ],
}

# For variant-specific pages, positive selection must mention the variant
# (or an accepted equivalent), not just the gene, and not its wild type.
VARIANT_POSITIVE: dict[str, list[str]] = {
    "BRAF-V600E": [r"\bV600E\b", r"\bV600K\b", r"\bV600\b"],
    "KRAS-G12C": [r"\bG12C\b"],
}

# Punctuation skipped when looking immediately left or right of a mention
# (so "(HER2)-negative" and "( NTRK ) gene fusion" are read correctly).
_EDGE = r"[\s\-\u2013\u2014()[\]{},;:\"'\u201c\u201d\u2019]*"

# Modifiers that can sit between "no" / "without" and the biomarker.
_NEG_MOD = r"(?:known|detectable|sensiti[sz]ing|activating|actionable|genomic|documented|evident)"

# Left-hand context that turns a mention into an exclusion / opposite status.
_NEG_LEFT = re.compile(
    r"(?:"
    r"\bno(?:t)?"
    r"(?:\s+" + _NEG_MOD + r")*"
    r"|\bwithout(?:\s+(?:a|an|" + _NEG_MOD + r"))*"
    r"|\babsence\s+of"
    r"|\blacking"
    r"|\bnegative\s+for"
    r"|\bfree\s+of"
    r"|\bwild[\s-]*type(?:\s+(?:in\s+both|for))?"
    r"|\bdo(?:es)?\s+not\s+have"
    r"|\bhave\s+not"
    r"|\bhad\s+no"
    r"|\bwho\s+do(?:es)?\s+not"
    r"|\bpatients?\s+without"
    r")"
    r"(?:\s+(?:an?|any|the))?"
    r"(?:\s+(?:egfr|alk|ros1|braf|kras|nras|her-?2|erbb2|ntrk|msi|mmr|ras|mutations?|rearrangements?|aberrations?|alterations?|fusions?|genomic|tumou?r|or|and|,))*"
    + _EDGE + r"$",
    re.I,
)

# Right-hand context: "HER2-negative", "(HER2)-negative", "KRAS wild-type".
_NEG_RIGHT = re.compile(
    r"^" + _EDGE + r"(?:negative|neg\b|wild[\s-]*type|wt\b|unmutated)",
    re.I,
)

# "HER2-Megative" (known label misspelling of "Negative").
_NEG_RIGHT_TYPO = re.compile(r"^" + _EDGE + r"m?egative\b", re.I)

# Positive right-hand context.
_POS_RIGHT = re.compile(
    r"^" + _EDGE + r"(?:"
    r"positive|pos\b|\+"
    r"|low\b|ultralow|overexpress|amplif|mutat|mutant"
    r"|exon|fusion|alteration|rearrangement|deletion|insertion|duplication"
    r"|substitution|activating|tkd|kinase domain"
    r"|antagonist|inhibitor|directed|targeting|targeted"
    r"|receptor-directed|expression"
    r"|gene(?:\s+fusion)?"
    r"|pharmdx|mutation test|companion"
    r")",
    re.I,
)

# Positive left-hand context. "with" only allows a short optional qualifier.
_POS_LEFT = re.compile(
    r"(?:"
    r"whose\s+tumou?rs?\s+(?:have|harboru?r|express|overexpress|with)"
    r"|tumou?rs?\s+(?:that\s+)?(?:have|harboru?r|with|express)"
    r"|harboru?ring"
    r"|\bwith(?:\s+(?:an?|documented|known|detectable|activating|non-resistant))*"
    r"|presence\s+of"
    r"|select(?:ed|ion)?\s+(?:patients?\s+)?(?:for\s+)?(?:therapy\s+)?(?:based\s+on)?"
    r"|(?:egf|her-?2|erbb)\s+receptor(?:-|\s+)?directed"
    r"|bispecific\s+"
    r")"
    + _EDGE + r"$",
    re.I,
)

# A drug described as an "X antagonist / inhibitor / directed antibody".
_MOLECULE_ROLE = re.compile(
    r"(?:antagonist|inhibitor|directed(?:\s+antibody)?|targeted(?:\s+antibody)?"
    r"|receptor-directed|kinase inhibitor|blocking\s+antibody)\b",
    re.I,
)

_LISTED_AS = re.compile(r"biomarker listed as\s*[\"\u201c\u201d]?\s*$", re.I)

# MSI-H and dMMR already encode the positive status in the name.
_MSI_STATUS = re.compile(
    r"MSI(?:\s*[-–]?\s*H(?:igh)?)?|dMMR|microsatellite instability|mismatch[- ]repair deficien",
    re.I,
)


def normalize(text: str) -> str:
    """Fold label punctuation and spacing so patterns can be applied uniformly."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", text)
    s = s.replace("\u00ad", "")  # soft hyphen
    for src, dst in (
        ("\u2010", "-"), ("\u2011", "-"), ("\u2012", "-"),
        ("\u2013", "-"), ("\u2014", "-"), ("\u2212", "-"),
        ("\u00a0", " "), ("\u202f", " "), ("\u2009", " "),
        ("\u2007", " "), ("\ufeff", ""),
    ):
        s = s.replace(src, dst)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _compiled_aliases(biomarker_id: str) -> list[re.Pattern]:
    pats = BIOMARKER_PATTERNS.get(biomarker_id) or [re.escape(biomarker_id)]
    return [re.compile(p, re.I) for p in pats]


def iter_mentions(text: str, biomarker_id: str):
    """Yield (start, end, matched_text, norm) for each biomarker mention.

    Shorter matches fully contained in a longer one (the "HER2" inside
    "human epidermal growth factor receptor 2 (HER2)") are dropped so
    polarity is decided once, on the full phrase.
    """
    norm = normalize(text)
    spans = []
    for cre in _compiled_aliases(biomarker_id):
        for m in cre.finditer(norm):
            spans.append((m.start(), m.end(), m.group(0)))
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept = []
    for s, e, g in spans:
        if any(s >= ks and e <= ke and (s, e) != (ks, ke) for ks, ke, _ in kept):
            continue
        kept.append((s, e, g))
    for s, e, g in kept:
        yield s, e, g, norm


def _window(s: str, start: int, end: int, left: int = 140, right: int = 80) -> tuple[str, str]:
    return s[max(0, start - left):start], s[end:end + right]


_COORD_ALLOWED = re.compile(
    r"(?:"
    r"no|not|without|known|detectable|sensiti[sz]ing|activating|actionable|documented|evident"
    r"|epidermal|growth|factor|receptor|anaplastic|lymphoma|kinase"
    r"|human|her-?2|erbb[- ]?2?|egfr|alk|braf|kras|nras|ras|ntrk|trk|msi|mmr|dmmr"
    r"|microsatellite|instability|mismatch|repair|high|deficient|proficient"
    r"|mutations?|rearrangements?|aberrations?|alterations?|fusions?|deletions?"
    r"|insertions?|substitutions?|genomic|tumou?r"
    r"|or|and|the|a|an|both|either|of|in"
    r")",
    re.I,
)


def _coordinated_exclusion(left: str) -> bool:
    """True when this mention is the second (or later) item in a 'no EGFR or ALK' list.

    Example left window: 'no known epidermal growth factor receptor (EGFR) mutations or '
    """
    starts = list(re.finditer(r"\b(?:no(?:t)?|without|absence\s+of)\b", left, re.I))
    if not starts:
        return False
    tail = left[starts[-1].start():]
    leftover = _COORD_ALLOWED.sub(" ", tail)
    leftover = re.sub(r"[\s,;:()\[\]\-\/]+", "", leftover)
    return leftover == ""


def _wild_type_applies(biomarker_id: str, left: str, right: str, matched: str) -> bool:
    """True only when 'wild-type' modifies *this* biomarker, not a neighbour."""
    if _NEG_RIGHT.search(right) and re.search(r"wild[\s-]*type", right, re.I):
        return True
    if re.search(r"wild[\s-]*type" + _EDGE + r"$", left, re.I):
        return True
    if biomarker_id == "KRAS-G12C":
        ctx = left + matched + right
        if re.search(r"wild[\s-]*type\s+RAS", ctx, re.I) and re.search(
            r"\b(?:KRAS|NRAS|RAS)\b", matched, re.I
        ):
            return True
        if re.search(r"wild[\s-]*type\s+in\s+both\s+KRAS", ctx, re.I):
            return True
    return False


def _mention_polarity(biomarker_id: str, left: str, right: str, matched: str) -> str:
    """Return 'positive', 'negative', or 'unclear' for a single mention."""
    # PGx boilerplate is not a selection criterion
    # ("Biomarker listed as “ERBB2(HER2)”" — the inner HER2 sits a
    # few characters after "listed as").
    if _LISTED_AS.search(left) or re.search(r"biomarker listed as.{0,40}$", left, re.I):
        return "unclear"

    # Opposite-status and exclusion constructions take precedence,
    # including "no sensitizing / no sensitising EGFR mutations".
    if _NEG_RIGHT.search(right) or _NEG_RIGHT_TYPO.search(right):
        return "negative"
    if _NEG_LEFT.search(left) or _coordinated_exclusion(left):
        return "negative"
    if _wild_type_applies(biomarker_id, left, right, matched):
        return "negative"
    # "not MSI-H" / "not microsatellite instability-high" / pMMR (proficient).
    if re.search(r"\bnot\b" + _EDGE + r"(?:microsatellite|msi|mismatch|dmmr|mmr)?", left, re.I):
        if re.search(r"\bnot\b.{0,60}$", left, re.I):
            return "negative"
    if biomarker_id == "MSI-H-dMMR" and re.search(
        r"proficient|\bpMMR\b|not\s+microsatellite|not\s+msi", left + matched + right, re.I
    ):
        return "negative"
    # Sequencing caveat, not a selection criterion:
    # "Patients with EGFR or ALK genomic tumor aberrations should have
    # disease progression on FDA-approved therapy for these aberrations."
    if re.search(
        r"should have (?:disease )?progress(?:ion|ed) on",
        right, re.I,
    ):
        return "unclear"
    # Prior-therapy list, not a selection criterion for this drug:
    # "and if appropriate, HER2/neu-targeted therapy."
    if re.search(r"if appropriate", left, re.I) and re.search(r"targeted therapy", right, re.I):
        return "unclear"

    # Variant-specific pages: a bare gene mention is not enough to be positive
    # unless the variant itself is in the immediate context.
    variant_pats = VARIANT_POSITIVE.get(biomarker_id)
    if variant_pats:
        ctx = left + matched + right
        if not any(re.search(p, ctx, re.I) for p in variant_pats):
            return "unclear"

    # MSI-H / dMMR: the status name itself is the selection criterion.
    if biomarker_id == "MSI-H-dMMR" and _MSI_STATUS.search(matched):
        return "positive"

    if _POS_RIGHT.search(right) or _POS_LEFT.search(left):
        return "positive"
    return "unclear"


def analyse_text(text: str, biomarker_id: str) -> dict:
    """Summarise polarities of every biomarker mention in *text*."""
    positives, negatives, unclear = [], [], []
    last_norm = ""
    for start, end, matched, norm in iter_mentions(text, biomarker_id):
        last_norm = norm
        left, right = _window(norm, start, end)
        pol = _mention_polarity(biomarker_id, left, right, matched)
        rec = {"matched": matched, "polarity": pol, "left": left[-80:], "right": right[:80]}
        if pol == "positive":
            positives.append(rec)
        elif pol == "negative":
            negatives.append(rec)
        else:
            unclear.append(rec)
    return {
        "positives": positives,
        "negatives": negatives,
        "unclear": unclear,
        "has_mention": bool(positives or negatives or unclear),
        "text": last_norm,
    }


def _cdx_has_required_variant(hay: str, biomarker_id: str) -> bool:
    """For variant-specific biomarkers, the CDx text must mention the variant."""
    pats = VARIANT_POSITIVE.get(biomarker_id)
    if not pats:
        return True
    return any(re.search(p, hay, re.I) for p in pats)


def _cdx_positive(therapy: dict, biomarker_id: str) -> bool:
    """True when a companion-diagnostic row ties the drug to this biomarker."""
    rows = therapy.get("companionDiagnostics") or []
    if not rows:
        return False
    for c in rows:
        hay = " ".join(
            str(c.get(k) or "")
            for k in ("diagnostic", "indication", "biomarker", "drug")
        )
        if not hay.strip():
            # Empty stored fields but a row exists: the snapshot attached
            # this CDx from the FDA table's biomarker column.
            continue
        if not _cdx_has_required_variant(hay, biomarker_id):
            continue
        analysis = analyse_text(hay, biomarker_id)
        if analysis["negatives"] and not analysis["positives"]:
            continue
        if analysis["positives"] or analysis["has_mention"]:
            # "Dako EGFR pharmDx Kit" mentions EGFR even if polarity is unclear.
            return True
    # A CDx already attached to this biomarker at snapshot time is positive
    # evidence even when the stored indication is a short disease name
    # ("NSCLC - Tissue") that does not repeat the biomarker.
    for c in rows:
        hay = " ".join(
            str(c.get(k) or "")
            for k in ("diagnostic", "indication", "biomarker", "drug")
        )
        if not _cdx_has_required_variant(hay, biomarker_id):
            continue
        analysis = analyse_text(hay, biomarker_id)
        if analysis["negatives"] and not analysis["positives"]:
            continue
        return True
    return False


def _pgx_selection(therapy: dict) -> bool:
    """PGx table lists a labeling section of Indications and Usage.

    Necessary but not sufficient: atezolizumab is listed under EGFR in
    Indications and Usage because the indication *excludes* EGFR aberrations.
    The indication text must still be examined.
    """
    fda = therapy.get("fda") or {}
    sections = normalize(fda.get("labelingSections") or "")
    return "indications and usage" in sections.lower()


def classify_relation(
    biomarker_id: str,
    therapy: dict,
    extra_text: str = "",
) -> dict:
    """Return {relation, reason, evidence} for one therapy / biomarker pair.

    *extra_text* may carry a longer Indications and Usage extract than the
    stored excerpt (used when the 420-character excerpt was cut off before
    the relevant clause).
    """
    excerpt = therapy.get("indicationsExcerpt") or ""
    cite_text = " ".join(
        str(c.get("detail") or "") for c in (therapy.get("citations") or [])
    )
    cdx_text = " ".join(
        f"{c.get('diagnostic') or ''} {c.get('indication') or ''}"
        for c in (therapy.get("companionDiagnostics") or [])
    )
    body = " ".join(t for t in (excerpt, extra_text, cite_text) if t)

    analysis = analyse_text(body, biomarker_id)
    cdx_ok = _cdx_positive(therapy, biomarker_id)
    cdx_analysis = analyse_text(cdx_text, biomarker_id)

    positives = analysis["positives"] + cdx_analysis["positives"]
    negatives = analysis["negatives"]

    if positives and not _only_negative_indication(analysis, biomarker_id):
        return {
            "relation": TARGETS,
            "reason": "label-or-cdx-selection",
            "evidence": (positives[0]["left"] + positives[0]["matched"] + positives[0]["right"])[:280],
        }

    # CDx is positive evidence, but it must not override a clearly negative
    # indication (for example a HER2-negative-only label that happens to
    # share a multi-gene panel CDx).
    if cdx_ok and not negatives:
        return {
            "relation": TARGETS,
            "reason": "companion-diagnostic",
            "evidence": (cdx_text or "FDA companion-diagnostic row for this biomarker")[:280],
        }

    if negatives and not positives:
        return {
            "relation": EXCLUSION,
            "reason": "negative-or-exclusion-mention",
            "evidence": (negatives[0]["left"] + negatives[0]["matched"] + negatives[0]["right"])[:280],
        }

    if analysis["has_mention"] or _pgx_selection(therapy):
        return {
            "relation": MENTIONED,
            "reason": "mentioned-in-label",
            "evidence": (body or (therapy.get("fda") or {}).get("labelingSections") or "")[:280],
        }

    return {
        "relation": MENTIONED,
        "reason": "no-selection-evidence",
        "evidence": "",
    }


def _only_negative_indication(analysis: dict, biomarker_id: str) -> bool:
    """True when every mention of the biomarker is a negative / opposite-status one."""
    if analysis["positives"] and analysis["negatives"]:
        return False
    return bool(analysis["negatives"]) and not analysis["positives"]


def is_her2_negative_only(therapy: dict, extra_text: str = "") -> bool:
    """True if the indication selects HER2-negative patients and has no HER2-positive / HER2-low / HER2-targeted selection."""
    text = " ".join(
        t for t in (therapy.get("indicationsExcerpt") or "", extra_text) if t
    )
    analysis = analyse_text(text, "HER2")
    if analysis["positives"]:
        return False
    return bool(analysis["negatives"])


def targeting_therapies(biomarker: dict) -> list[dict]:
    """Therapies that should be rendered for this biomarker."""
    out = []
    for t in biomarker.get("therapies") or []:
        rel = t.get("relation")
        if rel is None:
            rel = classify_relation(biomarker.get("id") or "", t)["relation"]
        if rel == TARGETS:
            out.append(t)
    return out


def annotate_biomarker(biomarker: dict, extra_texts: dict[str, str] | None = None) -> None:
    """Set relation / relationReason / relationEvidence on each therapy, in place."""
    extra_texts = extra_texts or {}
    bid = biomarker.get("id") or ""
    for t in biomarker.get("therapies") or []:
        extra = extra_texts.get((bid, t.get("name") or "")) or extra_texts.get(t.get("name") or "") or ""
        result = classify_relation(bid, t, extra_text=extra)
        t["relation"] = result["relation"]
        t["relationReason"] = result["reason"]
        t["relationEvidence"] = result["evidence"]


def annotate_snapshot(snap: dict, extra_texts: dict | None = None) -> dict:
    """Annotate every biomarker in a snapshot. Returns a per-biomarker summary."""
    summary = {}
    for b in snap.get("biomarkers") or []:
        before = len(b.get("therapies") or [])
        annotate_biomarker(b, extra_texts=extra_texts)
        shown = targeting_therapies(b)
        dropped = [t["name"] for t in (b.get("therapies") or []) if t.get("relation") != TARGETS]
        summary[b["id"]] = {
            "before": before,
            "after": len(shown),
            "dropped": dropped,
            "kept": [t["name"] for t in shown],
        }
    counts = snap.setdefault("counts", {})
    counts["therapiesAll"] = sum(
        len(b.get("therapies") or []) for b in snap.get("biomarkers") or []
    )
    counts["therapies"] = sum(s["after"] for s in summary.values())
    return summary


def relevant_excerpt(text: str, biomarker_id: str, n: int = 420) -> str:
    """A 420-character window around the first *positive* mention, if any.

    Used so a displayed excerpt actually shows the selection-criterion clause
    (for example ramucirumab's EGFR exon-19 indication, or a HER2-positive
    line rather than an earlier HER2-negative one) rather than only the
    opening of a long Indications and Usage section.
    """
    raw = normalize(text)
    if not raw:
        return ""
    scored = []
    for s, e, g, norm in iter_mentions(raw, biomarker_id):
        left, right = _window(norm, s, e)
        pol = _mention_polarity(biomarker_id, left, right, g)
        scored.append((pol, s, e, norm))
    prefer = [x for x in scored if x[0] == "positive"] or scored
    if not prefer:
        return raw if len(raw) <= n else raw[: n - 1].rstrip() + "\u2026"
    _, s, e, raw = prefer[0]
    mid = (s + e) // 2
    start = max(0, mid - n // 2)
    end = min(len(raw), start + n)
    # Keep the chosen mention inside the window.
    if s < start:
        start = s
        end = min(len(raw), start + n)
    if e > end:
        end = e
        start = max(0, end - n)
    # Prefer starting at a nearby sentence / bullet boundary.
    for sep in (". ", " \u2022 ", "; ", " \u2022"):
        cut = raw.rfind(sep, max(0, start - 80), start + 20)
        if cut != -1 and (e - (cut + len(sep))) < n:
            start = cut + len(sep)
            end = min(len(raw), start + n)
            if e > end:
                end = min(len(raw), e + 20)
                start = max(0, end - n)
            break
    chunk = raw[start:end]
    if end < len(raw):
        chunk = chunk.rstrip() + "\u2026"
    if start > 0:
        chunk = "\u2026" + chunk.lstrip()
    return chunk
