#!/usr/bin/env python3
"""Decide whether a recruiting trial requires a given biomarker.

A trial is listed under a biomarker only when its condition(s) or
eligibility *inclusion* criteria require that biomarker as a selection
criterion (for example "EGFR mutation", "EGFR exon 19/L858R",
"HER2-positive", or a condition that names the biomarker). A mention
only in exclusions, in interventions, or in free-text keywords is not
enough; neither is "EGFR wild-type", "without EGFR", "eGFR" (kidney
function), "human epidermal growth factor receptor 2" for EGFR, or a
HER2-negative-only population (including the "HR+/HER2-" shorthand).

Excluded trials stay in the snapshot, flagged, and are not rendered.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Allow running as a script next to matching.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from matching import (  # noqa: E402
    normalize,
    _EDGE,
    _NEG_LEFT,
    _NEG_RIGHT,
    _NEG_RIGHT_TYPO,
    _coordinated_exclusion,
    _wild_type_applies,
    VARIANT_POSITIVE,
    _MSI_STATUS,
)

# Trial-oriented mention patterns. EGFR is not case-insensitive "egfr" so that
# kidney-function "eGFR" does not count; "epidermal growth factor receptor 2"
# (HER2) is also not an EGFR mention.
_TRIAL_PATTERNS: dict[str, list[tuple[str, int]]] = {
    # (pattern, flags)
    "EGFR": [
        (r"\bEGFRvIII\b", re.I),
        (r"\bEGFR\b", 0),  # case-sensitive: EGFR, not eGFR
        (r"epidermal growth factor receptor(?!\s*2\b)(?!\s*\(\s*HER-?2)", re.I),
        (r"\bEGF receptor\b", re.I),
    ],
    "ALK": [(r"anaplastic lymphoma kinase(?:\s*\(\s*ALK\s*\))?", re.I), (r"\bALK\b", re.I)],
    "BRAF-V600E": [(r"\bBRAF(?:\s*V600[A-Z]?)?\b", re.I), (r"\bV600E\b", re.I), (r"\bV600K\b", re.I), (r"\bV600\b", re.I)],
    "KRAS-G12C": [(r"\bKRAS(?:\s*G12C)?\b", re.I), (r"\bG12C\b", re.I)],
    "HER2": [
        (r"human epidermal growth factor receptor\s*2(?:\s*\(\s*HER-?2\s*\))?", re.I),
        (r"\bHER-?2(?:/neu)?\b", re.I),
        (r"\bERBB[- ]?2\b", re.I),
    ],
    "NTRK": [
        (r"neurotrophic (?:tyrosine )?receptor tyrosine kinase", re.I),
        (r"neurotrophic tyrosine receptor kinase", re.I),
        (r"\bNTRK\d?\b", re.I),
        (r"\bTRK(?:\s+fusion)?\b", re.I),
    ],
    "MSI-H-dMMR": [
        (r"microsatellite instability(?:\s*[-–]?\s*high)?", re.I),
        (r"\bMSI(?:\s*[-–]?\s*H(?:igh)?)?\b", re.I),
        (r"mismatch[- ]repair(?:\s+deficien(?:t|cy))?", re.I),
        (r"\bdMMR\b", re.I),
        (r"\bMMR\b", re.I),
        (r"MMR[- ]deficien(?:t|cy)", re.I),
    ],
}

# Mentions of the *drug class* ("prior anti-EGFR therapy", "EGFR TKI") are not
# a patient-selection requirement by themselves.
_DRUG_CLASS_RIGHT = re.compile(
    r"^" + _EDGE + r"(?:"
    r"(?:-|\s)?(?:tkis?|inhibitors?|targeted(?:\s+therap(?:y|ies))?|targeting(?:\s+agents?)?"
    r"|direct(?:ed|ing)(?:\s+(?:agents?|therap(?:y|ies)|antibodies))?"
    r"|antibodies|agents?|blockers?|vaccines?|therapy|therapies|treatment)"
    r"|-(?:tki|inhibitor|directed|targeted)"
    r")\b",
    re.I,
)
_DRUG_CLASS_LEFT = re.compile(
    r"(?:anti[- ]|prior(?:\s+\w+){0,4}\s+|previous(?:\s+\w+){0,4}\s+|failed\s+|received\s+)?"
    r"(?:anti[- ])$"
    , re.I,
)
# "prior anti-EGFR" / "previous EGFR TKI"
_PRIOR_THERAPY_LEFT = re.compile(
    r"(?:prior|previous|failed|received|treated\s+with|treatment\s+with|naive\s+to|naïve\s+to|"
    r"progress(?:ed|ion)\s+on|exposure\s+to|intolerant\s+to)"
    r"(?:\s+\w+){0,6}" + _EDGE + r"$",
    re.I,
)

_TRIAL_POS_LEFT = re.compile(
    r"(?:"
    r"harbou?ring|harbour?ing"
    r"|express(?:ing|es|ed)?"
    r"|overexpress(?:ing|es|ed|ion)?"
    r"|carry(?:ing)?|bearing|having|have|has|had"
    r"|documented|confirmed|known|detectable|activating|sensiti[sz]ing"
    r"|must\s+(?:have|be|harbor|harbour|express|show|demonstrate)"
    r"|required\s+to\s+have"
    r"|positi(?:ve|vity)\s+(?:for\s+)?"
    r"|tumou?rs?\s+(?:that\s+)?(?:have|harbou?r|express|with)"
    r"|whose\s+tumou?rs?"
    r"|patients?\s+with"
    r"|participants?\s+with"
    r"|subjects?\s+with"
    r"|presence\s+of"
    r"|including(?:\s+those\s+with)?"
    r"|with(?:\s+(?:an?|documented|known|detectable|activating|sensiti[sz]ing|common))*"
    r"|for(?:\s+(?:the\s+treatment\s+of|patients?\s+with|participants?\s+with))?"
    r")"
    + _EDGE + r"$",
    re.I,
)

_TRIAL_POS_RIGHT = re.compile(
    r"^" + _EDGE + r"(?:"
    r"positive|pos\b|\+"
    r"|low\b|ultralow|overexpress|amplif|mutat|mutant|mutated"
    r"|exon|fusion|alteration|altered|rearrangement|rearranged|deletion|insertion|duplication"
    r"|substitution|activating|tkd|kinase domain|alternations?"
    r"|expression|expressing|status"  # status handled specially below
    r"|gene(?:\s+fusion)?"
    r"|vIII|C797S|T790M|L858R|G12C|V600"
    r")",
    re.I,
)

_STATUS_ONLY = re.compile(
    r"^" + _EDGE + r"(?:activating\s+|sensiti[sz]ing\s+)?(?:mutation\s+)?status\b",
    re.I,
)

# "tissue available for EGFR and PD-L1 testing" is not a selection criterion.
_TESTING_LEFT = re.compile(
    r"(?:available|submitted|sent|provided|obtained|collected|used|required)\s+for\s*$",
    re.I,
)
_TESTING_RIGHT = re.compile(
    r"(?:immunohistochemical\s+|IHC\s+|genomic\s+|molecular\s+)?test(?:ing|s|ed)?\b",
    re.I,
)

# "participants who have EGFR mutations must have received prior osimertinib"
# is a prior-therapy clause for a subset, not enrollment limited to the biomarker.
_CONDITIONAL_PRIOR = re.compile(
    r"must\s+have\s+(?:received|been\s+treated|progress(?:ed|ion)|failed)",
    re.I,
)

# "HER2-" shorthand (HR+/HER2- Breast Cancer) means HER2-negative.
_HER2_SHORTHAND_NEG = re.compile(
    r"^"
    + _EDGE
    + r"(?!\s*(?:positive|pos\b|low\b|ultralow|overexpress|amplif|mutat|mutant|"
    r"directed|targeted|express(?:ing|ion)|enriched|\+))"
    r"(?:\s|$|[,\];/)]|breast|ductal|early|advanced|metastatic|locally|"
    r"tumou?rs?|cancers?|neoplasms?|carcinomas?)",
    re.I,
)

_NOT_ELIGIBLE = re.compile(
    r"(?:are|is|will\s+be)?\s*(?:not\s+eligible|excluded|an?\s+exclusion|ineligible)"
    r"|\bmust\s+not\s+have"
    r"|\bdo(?:es)?\s+not\s+harbor",
    re.I,
)

_EXCL_HEAD = re.compile(
    r"(?im)^(?:\s*)(?:(?:key|main|important|other)\s+)?exclusion\s+criteria\b"
    r"|^(?:\s*)exclusions?\s*:"
    r"|^(?:\s*)exclusion\s+criteria\s+for\b"
)

def split_eligibility(text: str) -> tuple[str, str]:
    raw = text or ""
    m = _EXCL_HEAD.search(raw)
    if m:
        return raw[:m.start()], raw[m.start():]
    # Fallback: a mid-paragraph "Exclusion Criteria"
    m = re.search(r"(?i)\b(?:key\s+)?exclusion\s+criteria\b", raw)
    if m:
        return raw[:m.start()], raw[m.start():]
    return raw, ""


def _is_egfr_gfr(norm: str, start: int, end: int, matched: str) -> bool:
    if matched in ("eGFR", "Egfr") or (len(matched) == 4 and matched[0] in "eE" and matched[1:] == "GFR" and matched != "EGFR"):
        return True
    ctx = norm[max(0, start - 50): end + 50]
    if re.search(r"estimated\s+glomerular|glomerular\s+filtration|\bmL\s*/\s*min", ctx, re.I):
        # only if the match looks like eGFR
        if re.search(r"eGFR|estimated", matched + ctx, re.I) and "epidermal" not in ctx.lower():
            return True
    return False


def _is_her2_full_name_as_egfr(norm: str, start: int, end: int) -> bool:
    left = norm[max(0, start - 20):start]
    right = norm[end:end + 24]
    if re.search(r"human\s+$", left, re.I) and re.search(r"^\s*2\b|^\s*\(\s*HER-?2", right, re.I):
        return True
    if re.search(r"^\s*2\b", right, re.I) and re.search(r"epidermal growth factor receptor$", norm[start:end], re.I):
        return True
    return False


def iter_trial_mentions(text: str, biomarker_id: str):
    norm = normalize(text)
    pats = _TRIAL_PATTERNS.get(biomarker_id) or [(re.escape(biomarker_id), re.I)]
    spans = []
    for p, flags in pats:
        for m in re.finditer(p, norm, flags):
            if biomarker_id == "EGFR":
                if _is_egfr_gfr(norm, m.start(), m.end(), m.group(0)):
                    continue
                if _is_her2_full_name_as_egfr(norm, m.start(), m.end()):
                    continue
            spans.append((m.start(), m.end(), m.group(0)))
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept = []
    for s, e, g in spans:
        if any(s >= ks and e <= ke and (s, e) != (ks, ke) for ks, ke, _ in kept):
            continue
        kept.append((s, e, g))
    for s, e, g in kept:
        yield s, e, g, norm


def _is_drug_class(left: str, right: str) -> bool:
    if _DRUG_CLASS_RIGHT.search(right) or _DRUG_CLASS_LEFT.search(left):
        return True
    if _PRIOR_THERAPY_LEFT.search(left) and _DRUG_CLASS_RIGHT.search(right):
        return True
    if _PRIOR_THERAPY_LEFT.search(left) and re.search(r"anti[- ]$", left, re.I):
        return True
    # "prior anti-EGFR therapy": left ends with "prior anti-", right starts with " therapy"
    if re.search(r"anti[- ]$", left, re.I):
        return True
    if re.search(r"(?:prior|previous|naive\s+to|naïve\s+to).{0,40}anti[- ]?$", left, re.I):
        return True
    return False


def _trial_polarity(biomarker_id: str, left: str, right: str, matched: str, wider_right: str) -> str:
    # Opposite-status first.
    if _NEG_RIGHT.search(right) or _NEG_RIGHT_TYPO.search(right):
        return "negative"
    if _NEG_LEFT.search(left) or _coordinated_exclusion(left):
        return "negative"
    if _wild_type_applies(biomarker_id, left, right, matched):
        return "negative"
    if re.search(r"\bnot\b" + _EDGE + r"(?:microsatellite|msi|mismatch|dmmr|mmr)?", left, re.I):
        if re.search(r"\bnot\b.{0,60}$", left, re.I):
            return "negative"
    if biomarker_id == "MSI-H-dMMR" and re.search(
        r"proficient|\bpMMR\b|\bMSS\b|microsatellite\s+stable|not\s+microsatellite|not\s+msi",
        left + matched + right, re.I,
    ) and not re.search(r"deficien|MSI(?:\s*[-–]?\s*H)|dMMR|instability-high", matched, re.I):
        return "negative"
    if biomarker_id == "HER2" and _HER2_SHORTHAND_NEG.search(right):
        return "negative"
    # "participants with EGFR mutations are not eligible"
    if _NOT_ELIGIBLE.search(wider_right[:160]):
        return "negative"
    if _TESTING_LEFT.search(left) and _TESTING_RIGHT.search(wider_right):
        return "testing-only"
    if _CONDITIONAL_PRIOR.search(wider_right[:180]) and re.search(
        r"(?:who\s+have|patients?\s+with|participants?\s+with|tumou?rs?\s+with)\s*$",
        left, re.I,
    ):
        return "conditional-prior"
    # Drug-class / prior-therapy mentions are not a selection requirement.
    if _is_drug_class(left, right):
        return "drug-class"
    # "EGFR mutation status must be known" is not a requirement for the mutation.
    if _STATUS_ONLY.search(right) and not re.search(r"positive|mutant|mutated|overexpress|amplif", right, re.I):
        return "status-only"
    variant_pats = VARIANT_POSITIVE.get(biomarker_id)
    if variant_pats:
        ctx = left + matched + right
        if not any(re.search(p, ctx, re.I) for p in variant_pats):
            return "unclear"
    if biomarker_id == "MSI-H-dMMR" and _MSI_STATUS.search(matched):
        # proficient already handled
        if re.search(r"proficient|\bpMMR\b|\bMSS\b", left + matched + right, re.I) and not re.search(
            r"deficien|MSI-H|dMMR|high", matched, re.I
        ):
            return "negative"
        return "positive"
    if _TRIAL_POS_RIGHT.search(right) or _TRIAL_POS_LEFT.search(left):
        # "status" alone already filtered
        if _STATUS_ONLY.search(right) and not re.search(r"positive|mutant|mutated", right, re.I):
            return "status-only"
        return "positive"
    return "unclear"


def analyse_trial_text(text: str, biomarker_id: str) -> dict:
    positives, negatives, other = [], [], []
    for start, end, matched, norm in iter_trial_mentions(text, biomarker_id):
        left = norm[max(0, start - 140):start]
        right = norm[end:end + 100]
        wider_right = norm[end:end + 200]
        pol = _trial_polarity(biomarker_id, left, right, matched, wider_right)
        rec = {"matched": matched, "polarity": pol, "left": left[-90:], "right": right[:90],
               "evidence": (left[-80:] + matched + right[:80]).strip()}
        if pol == "positive":
            positives.append(rec)
        elif pol == "negative":
            negatives.append(rec)
        else:
            other.append(rec)
    return {"positives": positives, "negatives": negatives, "other": other,
            "has_mention": bool(positives or negatives or other)}


REQUIRES = "requires"
EXCLUSION = "exclusion"
NOT_REQUIRED = "not-required"


def condition_names_biomarker(conditions: list, biomarker_id: str) -> dict | None:
    """A condition field that names the biomarker as the population, not opposite-status."""
    for cond in conditions or []:
        a = analyse_trial_text(cond, biomarker_id)
        if a["positives"]:
            return a["positives"][0]
        if a["negatives"] and not a["positives"]:
            continue
        # Unclear/other mention still "names" the biomarker (e.g. "EGFR/HER2 Exon 20
        # Insertion Mutation") unless it is a drug-class or status-only or eGFR.
        named = [r for r in a["other"] if r["polarity"] not in (
            "drug-class", "status-only", "testing-only", "conditional-prior"
        )]
        if named and re.search(
            r"mutat|mutant|exon|fusion|positiv|amplif|overexpress|rearrang|alter|"
            r"deficien|MSI|dMMR|insertion|deletion|V600|G12C|express",
            cond, re.I,
        ):
            return named[0]
        if a["other"] and not named:
            continue
    return None


def trial_requirement(biomarker_id: str, trial: dict, extra: dict | None = None) -> dict:
    extra = extra or {}
    title = trial.get("title") or extra.get("briefTitle") or ""
    official = extra.get("officialTitle") or trial.get("officialTitle") or ""
    conditions = trial.get("conditions") or extra.get("conditions") or []
    elig = extra.get("eligibilityCriteria") or trial.get("eligibilityCriteria") or ""
    inclusion, exclusion = split_eligibility(elig)

    # Do NOT use interventions or keywords as evidence.
    pop = " ".join(p for p in (title, official, " ".join(conditions)) if p)
    a_pop = analyse_trial_text(pop, biomarker_id)
    a_inc = analyse_trial_text(inclusion, biomarker_id)
    a_exc = analyse_trial_text(exclusion, biomarker_id)
    named = condition_names_biomarker(conditions, biomarker_id)

    positives = a_pop["positives"] + a_inc["positives"]
    if named and named.get("polarity") == "positive":
        positives = [named] + positives
    elif named and not positives and named.get('polarity') not in ('negative','testing-only','conditional-prior','drug-class','status-only'):
        # Condition names the biomarker (e.g. "EGFR-Mutant NSCLC" already positive;
        # "EGFR/HER2 Exon 20 Insertion Mutation" may be "unclear" polarity).
        # Only promote non-negative, non-drug-class names.
        positives = [dict(named, polarity="positive", via="condition-name")] + positives

    negatives = a_pop["negatives"] + a_inc["negatives"]

    if positives:
        ev = positives[0]
        return {
            "relation": REQUIRES,
            "reason": "condition-or-inclusion-requires",
            "evidence": ev.get("evidence") or ev.get("matched"),
        }
    if negatives:
        ev = negatives[0]
        return {
            "relation": EXCLUSION,
            "reason": "negative-or-wild-type-or-not-eligible",
            "evidence": ev.get("evidence") or ev.get("matched"),
        }
    # Exclusion-section mentions only, or drug-class / keywords, or nothing.
    if a_exc["has_mention"] and not (a_pop["has_mention"] or a_inc["has_mention"]):
        ev = (a_exc["positives"] or a_exc["negatives"] or a_exc["other"])[0]
        return {
            "relation": NOT_REQUIRED,
            "reason": "exclusion-section-only",
            "evidence": ev.get("evidence") or ev.get("matched"),
        }
    if a_pop["other"] or a_inc["other"]:
        ev = (a_pop["other"] or a_inc["other"])[0]
        return {
            "relation": NOT_REQUIRED,
            "reason": f"mention-not-a-requirement:{ev['polarity']}",
            "evidence": ev.get("evidence") or ev.get("matched"),
        }
    return {
        "relation": NOT_REQUIRED,
        "reason": "no-condition-or-inclusion-requirement",
        "evidence": "",
    }



def requiring_trials(biomarker: dict) -> list[dict]:
    """Trials that should be rendered for this biomarker."""
    bid = biomarker.get("id") or ""
    out = []
    for t in biomarker.get("trials") or []:
        rel = t.get("requirement")
        if rel is None:
            rel = trial_requirement(bid, t)["relation"]
        if rel == REQUIRES:
            out.append(t)
    return out


def annotate_trials(snap: dict, extra_by_nct: dict | None = None) -> dict:
    """Set requirement fields on every trial. Does not touch therapies.

    *extra_by_nct* maps NCT ID to official title / eligibility fetched
    for classification; those texts are used then discarded, so the
    snapshot only stores a short flag and evidence excerpt.
    """
    extra_by_nct = extra_by_nct or {}
    summary = {}
    for b in snap.get("biomarkers") or []:
        bid = b.get("id") or ""
        before = list(b.get("trials") or [])
        for t in before:
            extra = extra_by_nct.get(t.get("nctId") or "") or {}
            # Prefer eligibility already on the trial (weekly fetch).
            if t.get("eligibilityCriteria") and "eligibilityCriteria" not in extra:
                extra = {**extra, "eligibilityCriteria": t.get("eligibilityCriteria")}
            result = trial_requirement(bid, t, extra)
            t["requirement"] = result["relation"]
            t["requirementReason"] = result["reason"]
            t["requirementEvidence"] = (result.get("evidence") or "")[:280]
            # Do not persist bulky eligibility text.
            t.pop("eligibilityCriteria", None)
            t.pop("officialTitle", None)
        shown = requiring_trials(b)
        summary[bid] = {
            "before": len(before),
            "after": len(shown),
            "beforeFrance": sum(1 for t in before if "France" in (t.get("countries") or [])),
            "afterFrance": sum(1 for t in shown if "France" in (t.get("countries") or [])),
            "beforeSwitzerland": sum(1 for t in before if "Switzerland" in (t.get("countries") or [])),
            "afterSwitzerland": sum(1 for t in shown if "Switzerland" in (t.get("countries") or [])),
            "dropped": [t.get("nctId") for t in before if t.get("requirement") != REQUIRES],
            "kept": [t.get("nctId") for t in shown],
        }
    counts = snap.setdefault("counts", {})
    counts["trialsAll"] = sum(len(b.get("trials") or []) for b in snap.get("biomarkers") or [])
    counts["trials"] = sum(s["after"] for s in summary.values())
    return summary
