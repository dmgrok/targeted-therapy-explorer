#!/usr/bin/env python3
"""Full FDA Indications and Usage, committed in data/labels.json.

The weekly snapshot only stores a 420-character excerpt, which cut off
osimertinib's first-line use. The tree and plain lines use this full
text instead. Ligatures (ﬁ, ﬂ) are normalised so 'first-line' matches.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "data" / "labels.json"

# Unicode ligatures that appear in some SPL files and break "first-line".
_LIGATURES = {
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\u00a0": " ",
    "\u2013": "-",
    "\u2014": "-",
    "ﬁ": "fi",
    "ﬂ": "fl",
}


def normalize(text: str) -> str:
    t = text or ""
    for a, b in _LIGATURES.items():
        t = t.replace(a, b)
    return t


def load_labels() -> dict:
    if not LABELS.is_file():
        return {"entries": {}}
    return json.loads(LABELS.read_text(encoding="utf-8"))


def entry_for(therapy: dict, catalog: dict | None = None) -> dict | None:
    catalog = catalog if catalog is not None else load_labels()
    name = (therapy.get("name") or "").strip()
    return (catalog.get("entries") or {}).get(name)


def indications(therapy: dict, catalog: dict | None = None) -> str:
    """Full Indications and Usage, else the snapshot excerpt."""
    e = entry_for(therapy, catalog)
    if e and e.get("indications_and_usage"):
        return normalize(e["indications_and_usage"])
    return normalize(
        (therapy.get("indicationsExcerpt") or "")
        + " "
        + (therapy.get("relationEvidence") or "")
    )


def label_blob(therapy: dict, catalog: dict | None = None) -> str:
    """All committed label fields, for route / class / combination / fact gate."""
    e = entry_for(therapy, catalog)
    if not e:
        return indications(therapy, catalog)
    parts = [
        e.get("indications_and_usage") or "",
        e.get("dosage_forms_and_strengths") or "",
        e.get("dosage_and_administration") or "",
        e.get("description") or "",
        e.get("mechanism_of_action") or "",
        " ".join(e.get("route") or []),
        " ".join(e.get("brandNames") or []),
        " ".join(e.get("genericNames") or []),
    ]
    return normalize("\n".join(parts))


# Everyday route, only from named dosage form / route.
def route_phrase(blob: str) -> str:
    t = blob or ""
    if re.search(r"\btablets?\b", t, re.I):
        daily = bool(re.search(r"\bonce daily\b|\bdaily\b", t, re.I))
        return "a once-daily pill" if daily else "a pill"
    if re.search(r"\bcapsules?\b", t, re.I):
        daily = bool(re.search(r"\bonce daily\b|\bdaily\b", t, re.I))
        return "a once-daily capsule" if daily else "a capsule"
    if re.search(r"\bintravenous(?:ly)?\b|\binfusion\b|\bINTRAVENOUS\b", t, re.I):
        return "a drip into a vein"
    if re.search(r"\bsubcutaneous(?:ly)?\b", t, re.I):
        return "an injection under the skin"
    if re.search(r"\binjection\b", t, re.I):
        return "an injection"
    if re.search(r"\borally\b|\boral use\b|\bORAL\b|\bfor oral\b", t, re.I):
        return "a pill"
    return ""


def class_source(therapy: dict, catalog: dict | None = None) -> str:
    """Opening 'X is a Y indicated' line plus a short lead of description
    and mechanism. No sentence split: labels often put a period inside
    'EGFR (ErbB1).' or after a section number and that dropped the target.
    """
    e = entry_for(therapy, catalog)
    iu = (e.get("indications_and_usage") if e else "") or indications(therapy, catalog)
    lines = []
    m = re.search(
        r"((?:[A-Za-z][A-Za-z0-9®™ /\-]+)\s+is (?:a|an|a combination of) .{3,220}? indicated)",
        iu,
        re.I,
    )
    if m:
        lines.append(m.group(1))
    if e:
        for field in ("description", "mechanism_of_action"):
            raw = e.get(field) or ""
            raw = re.sub(
                r"^\s*\d+(?:\.\d+)?\s+(?:DESCRIPTION|Mechanism of Action)\s+",
                "",
                raw,
                flags=re.I,
            )
            lines.append(raw[:320])
    return normalize("\n".join(lines))


def _first_named_target(t: str) -> str:
    m = re.search(
        r"(?:kinase domains of|including|inhibitor of(?: the kinase activity of the human)?|"
        r"antagonist(?: indicated)?|directed(?: antibody)?|"
        r"activity (?:at clinically achievable concentrations )?against(?: multiple kinases including)?)\s+"
        r"(EGFR|ALK|HER2|BRAF|MEK|KRAS|NTRK|VEGFR2|ROS1|MET)",
        t or "",
        re.I,
    )
    return (m.group(1) if m else "").upper()


def class_phrase(blob: str, biomarker_id: str = "") -> str:
    """What the drug does, from the opening class line and first sentences.

    The page gene is never a fallback. A later family mention (HER2 in an
    EGFR-antagonist mechanism paragraph) is not in this source.
    """
    t = (blob or "").lower()

    def has(*pats: str) -> bool:
        return any(re.search(p, t, re.I) for p in pats)

    is_adc = has(r"antibody") and has(r"conjugate", r"deruxtecan", r"emtansine", r"trop-2")
    is_ab = has(r"\bantibody\b", r"bispecific", r"monoclonal")
    if is_adc:
        return "that is a lab-made antibody linked to a drug"
    if is_ab and has(r"\bPD-L1\b", r"\bPD-1\b", r"programmed death", r"\bCTLA-4\b"):
        return "that is a lab-made antibody"

    action = ""
    first = _first_named_target(t)
    # Prefer a named target in the opening class line or first mechanism clause.
    if has(r"\bvegfr2\b"):
        action = "that blocks a blood-vessel growth signal (VEGFR2)"
    elif has(r"\bMEK\b") and has(r"inhibitor", r"kinase"):
        action = "that blocks a MEK signal"
    elif has(r"\bPD-L1\b", r"\bPD-1\b", r"programmed death"):
        action = ""
    elif first in {"EGFR", "ALK", "HER2", "BRAF", "MEK", "KRAS", "NTRK", "VEGFR2"}:
        if first == "VEGFR2":
            action = "that blocks a blood-vessel growth signal (VEGFR2)"
        elif first == "MEK":
            action = "that blocks a MEK signal"
        else:
            action = f"that blocks the {first} signal"
    elif has(r"\bEGFR\b", r"EGF receptor") and has(
        r"antagonist", r"inhibitor", r"kinase", r"directed", r"binds", r"against"
    ):
        # Pan-HER inhibitors (afatinib, dacomitinib) name EGFR and HER2;
        # EGFR is the named indication target and comes first.
        action = "that blocks the EGFR signal"
    elif has(r"\bHER2\b", r"HER-2", r"HER2/neu", r"\bERBB2\b") and has(
        r"antagonist", r"inhibitor", r"kinase", r"antibody", r"directed", r"binds"
    ):
        action = "that blocks the HER2 signal"
    elif has(r"anaplastic lymphoma kinase", r"\bALK\b") and has(
        r"kinase", r"inhibitor", r"against"
    ):
        action = "that blocks the ALK signal"
    elif has(r"\bBRAF\b") and has(r"inhibitor", r"kinase"):
        action = "that blocks the BRAF signal"
    elif has(r"\bKRAS\b", r"\bRAS GTPase") and has(r"inhibitor", r"antagonist"):
        action = "that blocks the KRAS signal"
    elif has(r"\bNTRK\b", r"neurotrophic tyrosine", r"tropomyosin receptor kinase") and has(
        r"inhibitor", r"kinase"
    ):
        action = "that blocks the NTRK signal"
    elif has(r"kinase inhibitor", r"tyrosine kinase"):
        action = "that blocks a growth signal"

    if is_ab:
        body = "a lab-made antibody"
        if action:
            return f"that is {body} {action}"
        return f"that is {body}"
    return action


def what_it_is(therapy: dict, biomarker_id: str, catalog: dict | None = None) -> str:
    """Route plus what it does. Never a route alone."""
    blob = label_blob(therapy, catalog)
    route = route_phrase(blob)
    action = class_phrase(class_source(therapy, catalog), biomarker_id)
    antibody = "antibody" in (action or "")
    if antibody:
        body = action.replace("that is ", "")
        if route:
            return f"{body}, given as {route}"
        return body
    if route and action:
        return f"{route} {action}"
    if action:
        return f"a drug {action}"
    if route:
        return f"{route} described on the FDA label in this snapshot"
    return "a drug described on the FDA label in this snapshot"


# Combination partners named on the label for a clause.
_COMBO_PATS = [
    re.compile(
        r"in combination with\s+([^.;]{3,80}?)(?:"
        r",?\s+for\b|,?\s+the\s+(?:first|treatment|adjuvant)|"
        r",?\s+is indicated|\s+is indicated|,?\s+in adult|,?\s+in patients|"
        r"\s+\(\s*\d|\s*$)",
        re.I,
    ),
    re.compile(
        r",\s+in combination with\s+([^,.]{3,80}?),\s+is indicated",
        re.I,
    ),
    re.compile(
        r"as a single agent or in combination with\s+([^,.;]{3,60})",
        re.I,
    ),
]


def _clean_partner(p: str) -> str:
    p = re.sub(r"\s+", " ", (p or "").strip(" ,;"))
    p = re.split(r"[\[\(]", p, maxsplit=1)[0]  # drop [see Clinical Studies] and (1.1)
    p = p.replace("®", "").replace("™", "")
    p = re.sub(r"\s+", " ", p).strip(" ,;")
    p = re.split(
        r"\bfor the\b|\bindicated\b|\btreatment of\b|\bsee\b",
        p,
        maxsplit=1,
    )[0].strip(" ,;")
    return p


def combinations_in(text: str) -> list[str]:
    found = []
    seen = set()
    t = normalize(text)
    for pat in _COMBO_PATS:
        for m in pat.finditer(t):
            p = _clean_partner(m.group(1))
            if not p or len(p) > 80:
                continue
            k = p.lower()
            if k not in seen:
                seen.add(k)
                found.append(p)
    return found


def is_single_agent(text: str) -> bool:
    t = normalize(text)
    return bool(re.search(r"\bas a single agent\b|\sas monotherapy\b|\salone\b", t, re.I))


def combo_note(clause_texts: list[str]) -> str:
    """Everyday 'used together with' note from the clauses of one leaf.

    If every clause is combination-only, do not also imply a standalone use.
    If some clauses are single-agent and some are combination, say both.
    """
    combos = []
    any_single = False
    any_combo = False
    for cl in clause_texts:
        ps = combinations_in(cl)
        if ps:
            any_combo = True
            for p in ps:
                if p.lower() not in {c.lower() for c in combos}:
                    combos.append(p)
        if is_single_agent(cl) or (
            not ps and re.search(r"\bis indicated for\b|\bindicated for\b", cl, re.I)
            and "in combination with" not in cl.lower()
        ):
            # A clause with no "in combination with" that is an indication
            # is treated as a standalone use.
            if "in combination with" not in normalize(cl).lower():
                any_single = True
        if is_single_agent(cl):
            any_single = True
    if not combos:
        return ""
    partners = " and ".join(combos) if len(combos) <= 2 else ", ".join(combos[:-1]) + " and " + combos[-1]
    if any_single and any_combo:
        return f"Used alone, or together with {partners}."
    return f"Used together with {partners}."

