#!/usr/bin/env python3
"""Deterministic option categories for biomarker pages.

Rules are implemented from existing snapshot fields. They are never
assigned by hand. An item is placed in at most one category.

Display order inside a category is alphabetical (by therapy name, NCT
id, or assertion id). That order does not mean one option is better
than another.
"""
from __future__ import annotations

from typing import Iterable

from matching import targeting_therapies
from trial_matching import requiring_trials

MAINSTREAM = "mainstream"
TRIALS = "trials"
ON_THE_EDGE = "on-the-edge"

# AMP levels treated as the highest evidence recorded in this snapshot.
# Lower, recorded levels are "on the edge". A missing ampLevel is not
# placed in this category, because the snapshot does not tell us the level.
HIGHEST_AMP = "TIER_I_LEVEL_A"

CATEGORY_DEFS: list[dict] = [
    {
        "id": MAINSTREAM,
        "label": "Mainstream",
        "short": "FDA-approved for this biomarker, in this snapshot.",
        "rule": (
            "A therapy is Mainstream when the existing targeting_therapies() "
            "rule includes it: the FDA label indication, the FDA "
            "pharmacogenomic-biomarker table, or an FDA companion-diagnostic "
            "row ties the drug to this biomarker as a selection criterion."
        ),
    },
    {
        "id": TRIALS,
        "label": "Trials",
        "short": "A recruiting study that requires this biomarker.",
        "rule": (
            "A study is in Trials when the existing requiring_trials() rule "
            "includes it: it is a recruiting ClinicalTrials.gov record whose "
            "condition or eligibility inclusion criteria require this "
            "biomarker as a selection criterion."
        ),
    },
    {
        "id": ON_THE_EDGE,
        "label": "On the edge",
        "short": "Early evidence, not an FDA approval in this snapshot.",
        "rule": (
            "A CIViC assertion is On the edge when all of these hold: it is "
            "PREDICTIVE (it names a therapy effect), it names at least one "
            "therapy, and its ampLevel is present and is not TIER_I_LEVEL_A. "
            "TIER_I_LEVEL_A is the highest evidence level recorded on CIViC "
            "assertions in this snapshot; lower recorded levels (for example "
            "TIER_II_LEVEL_C or TIER_II_LEVEL_D) are treated as earlier "
            "evidence. Assertions with no ampLevel are not placed here. "
            "Status (ACCEPTED or SUBMITTED) is shown, not used as a filter. "
            "Diagnostic, prognostic or oncogenic assertions, and "
            "TIER_I_LEVEL_A predictive assertions about a Mainstream therapy, "
            "stay in Sources rather than as a separate option."
        ),
    },
]

ORDER_NOTE = (
    "Options are grouped by category, then listed alphabetically. "
    "That order does not mean one option is better than another."
)

AI_NOTE = (
    "Plain-language lines were written from the cited snapshot data, "
    "committed in the repository for review, and built into these pages. "
    "They are not generated in your browser."
)


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _therapy_name_keys(therapy: dict) -> set[str]:
    names = [therapy.get("name") or ""]
    names.extend(therapy.get("brandNames") or [])
    names.extend(therapy.get("genericNames") or [])
    return {_norm(n) for n in names if n and _norm(n)}


def mainstream_therapies(biomarker: dict) -> list[dict]:
    """Therapies in the Mainstream category, alphabetical by display name."""
    items = list(targeting_therapies(biomarker))
    items.sort(key=lambda t: _norm(t.get("name") or ""))
    return items


def trial_options(biomarker: dict) -> list[dict]:
    """Trials in the Trials category, alphabetical by NCT id."""
    items = list(requiring_trials(biomarker))
    items.sort(key=lambda t: (t.get("nctId") or "").upper())
    return items


def _is_on_the_edge(assertion: dict) -> bool:
    if (assertion.get("assertionType") or "") != "PREDICTIVE":
        return False
    therapies = [t for t in (assertion.get("therapies") or []) if t]
    if not therapies:
        return False
    amp = assertion.get("ampLevel")
    if not amp:
        return False
    if amp == HIGHEST_AMP:
        return False
    return True


def on_the_edge_assertions(biomarker: dict) -> list[dict]:
    """CIViC assertions in the On the edge category, alphabetical."""
    civic = biomarker.get("civic") or {}
    items = [a for a in (civic.get("assertions") or []) if _is_on_the_edge(a)]
    items.sort(
        key=lambda a: (
            _norm(", ".join(a.get("therapies") or [])),
            _norm(a.get("molecularProfile") or ""),
            str(a.get("id") or ""),
        )
    )
    return items


def civic_for_therapy(biomarker: dict, therapy: dict) -> list[dict]:
    """CIViC assertions (any level) that name this therapy. For Sources."""
    keys = _therapy_name_keys(therapy)
    out = []
    for a in (biomarker.get("civic") or {}).get("assertions") or []:
        names = {_norm(n) for n in (a.get("therapies") or []) if n}
        if names & keys:
            out.append(a)
    return out


def leftover_civic(biomarker: dict) -> dict:
    """Gene summaries plus assertions that are not an On the edge option.

    TIER_I_LEVEL_A predictive assertions that name a Mainstream therapy
    are also returned here if the caller wants a full raw dump; the
    renderer attaches those to the therapy's Sources and can skip them
    in the leftover block.
    """
    civic = biomarker.get("civic") or {}
    edge_ids = {a.get("id") for a in on_the_edge_assertions(biomarker)}
    leftover = [
        a
        for a in (civic.get("assertions") or [])
        if a.get("id") not in edge_ids
    ]
    return {
        "genes": list(civic.get("genes") or []),
        "assertions": leftover,
    }


def companion_diagnostics(biomarker: dict) -> list[dict]:
    """Unique FDA companion diagnostics from Mainstream therapies.

    Deduped on (diagnostic, indication), sorted alphabetically.
    Sample type, when present, is the substring of indication after
    the last ' - ' or ' – ' (as already stored in the snapshot).
    """
    seen: set[tuple[str, str]] = set()
    items: list[dict] = []
    for t in mainstream_therapies(biomarker):
        for c in t.get("companionDiagnostics") or []:
            diag = (c.get("diagnostic") or "").strip()
            ind = (c.get("indication") or "").strip()
            key = (diag, ind)
            if not diag or key in seen:
                continue
            seen.add(key)
            sample = sample_type_from_indication(ind)
            items.append(
                {
                    "diagnostic": diag,
                    "indication": ind,
                    "sampleType": sample,
                    "url": c.get("url") or "",
                    "viaTherapy": t.get("name") or "",
                }
            )
    items.sort(key=lambda c: (_norm(c["diagnostic"]), _norm(c["indication"])))
    return items


def sample_type_from_indication(indication: str) -> str:
    """Sample type sitting after ' - ' in the FDA CDx indication column."""
    text = indication or ""
    for sep in (" – ", " - ", " –", " -"):
        if sep in text:
            tail = text.rsplit(sep, 1)[-1].strip()
            if tail and tail != text.strip():
                return tail
    return ""


def category_counts(biomarker: dict) -> dict[str, int]:
    return {
        MAINSTREAM: len(mainstream_therapies(biomarker)),
        TRIALS: len(trial_options(biomarker)),
        ON_THE_EDGE: len(on_the_edge_assertions(biomarker)),
    }


def option_id(kind: str, record: dict) -> str:
    """Stable id for a plain-text line, unique within a biomarker."""
    if kind == MAINSTREAM:
        return f"therapy:{(record.get('name') or '').strip()}"
    if kind == TRIALS:
        return f"trial:{(record.get('nctId') or '').strip()}"
    if kind == ON_THE_EDGE:
        return f"civic:{record.get('id')}"
    if kind == "cdx":
        diag = (record.get("diagnostic") or "").strip()
        ind = (record.get("indication") or "").strip()
        return f"cdx:{diag}|{ind}"
    raise ValueError(f"unknown kind {kind}")


def all_option_ids(biomarker: dict) -> list[str]:
    ids = [option_id(MAINSTREAM, t) for t in mainstream_therapies(biomarker)]
    ids += [option_id(TRIALS, t) for t in trial_options(biomarker)]
    ids += [option_id(ON_THE_EDGE, a) for a in on_the_edge_assertions(biomarker)]
    ids += [option_id("cdx", c) for c in companion_diagnostics(biomarker)]
    return ids
