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


# Aliases the label uses for the same everyday target name.
_TARGET_ALIASES = {
    "EGFR": "EGFR", "ERBB1": "EGFR", "HER1": "EGFR", "EGF": "EGFR",
    "HER2": "HER2", "HER-2": "HER2", "ERBB2": "HER2",
    "HER4": "HER4", "ERBB4": "HER4",
    "HER3": "HER3", "ERBB3": "HER3",
    "MET": "MET",
    "ALK": "ALK",
    "ROS1": "ROS1",
    "NTRK": "NTRK", "TRK": "NTRK", "TRKA": "NTRK", "TRKB": "NTRK", "TRKC": "NTRK",
    "BRAF": "BRAF", "MEK": "MEK", "KRAS": "KRAS", "VEGFR2": "VEGFR2", "RET": "RET",
}

# Opening clause that names what the drug itself inhibits or binds to.
# "family members, including EGFR" (Pertuzumab) is intentionally not an intro:
# those are heterodimer partners, not the drug's target.
_INHIBIT_INTRO = re.compile(
    r"(?:"
    r"kinase inhibitor of|"
    r"inhibitor of(?: the intracellular tyrosine kinase domains of both)?|"
    r"inhibitor of(?: the kinase activity of(?: the human EGFR family)?)?|"
    r"covalently binds to|"
    r"irreversibly binds to|"
    r"binds to(?: the extracellular domains of)?|"
    r"(?:EGF|MET|HER2|EGFR) receptor-directed|"
    r"directed against(?: the)?"
    r")\s+(.{0,360})",
    re.I,
)

_TARGET_TOKEN = re.compile(
    r"\b(EGFR|EGF|HER-?2|HER4|HER3|HER1|ERBB[1-4]|MET|ALK|ROS1|"
    r"NTRK|TRK[ABC]?|BRAF|MEK|KRAS|VEGFR2|RET)\b",
    re.I,
)


def _canonical_target(raw: str) -> str:
    key = (raw or "").upper().replace("HER-2", "HER2")
    return _TARGET_ALIASES.get(key, "")


def _inhibited_targets(t: str) -> list[str]:
    """Co-equal targets named in the opening 'inhibitor of' / 'binds to' clause.

    The first such clause only; cut at a sentence end or an 'In vitro'
    qualifier so a later 'including' family list is not read as a target.
    """
    for m in _INHIBIT_INTRO.finditer(t or ""):
        span = m.group(0)
        # Cut at a sentence end, an 'In vitro' qualifier, or 'including'
        # (a laundry list of other kinases, as in Crizotinib and Ensartinib
        # "inhibits other kinases including MET and ROS1").
        span = re.split(
            r"(?<=\.)\s+|\bIn vitro\b|\bincluding\b",
            span,
            maxsplit=1,
            flags=re.I,
        )[0]
        found: list[str] = []
        for tm in _TARGET_TOKEN.finditer(span):
            name = _canonical_target(tm.group(1))
            if name and name not in found:
                found.append(name)
        if found:
            return found
    return []


def _opening_class_targets(t: str) -> list[str]:
    """Target named in 'X is a HER2/neu receptor antagonist indicated'.

    This is the drug's stated class, and beats a later family-member
    mention (Pertuzumab: HER2 antagonist; mechanism then says it blocks
    heterodimerization with family members including EGFR).
    """
    m = re.search(
        r"\bis\s+(?:a|an)\s+(.{3,160}?)\s+(?:antagonist|inhibitor|antibody|conjugate)\s+indicated",
        t or "",
        re.I,
    )
    if not m:
        return []
    found: list[str] = []
    for tm in _TARGET_TOKEN.finditer(m.group(1)):
        name = _canonical_target(tm.group(1))
        if name and name not in found:
            found.append(name)
    return found


def _blocks_phrase(targets: list[str]) -> str:
    """Everyday 'blocks the X signal(s)' line. Two targets use 'and'
    ('blocks the EGFR and HER2 signals') to match the label's 'both'."""
    if not targets:
        return ""
    if len(targets) == 1:
        if targets[0] == "VEGFR2":
            return "that blocks a blood-vessel growth signal (VEGFR2)"
        if targets[0] == "MEK":
            return "that blocks a MEK signal"
        return f"that blocks the {targets[0]} signal"
    if len(targets) == 2:
        return f"that blocks the {targets[0]} and {targets[1]} signals"
    return (
        "that blocks the "
        + ", ".join(targets[:-1])
        + " and "
        + targets[-1]
        + " signals"
    )


def _first_named_target(t: str) -> str:
    # Bare 'including' is not an intro: Pertuzumab "HER family members,
    # including EGFR" is not the drug's target. Multi-kinase 'activity
    # against multiple kinases including' stays.
    m = re.search(
        r"(?:kinase domains of|inhibitor of(?: the kinase activity of the human)?|"
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
    EGFR-antagonist mechanism paragraph, or EGFR in Pertuzumab's
    "HER family members, including EGFR") is not treated as a target.
    Co-equal targets the opening mechanism names ("both EGFR and HER2",
    "EGFR, HER2, and HER4", "EGFR and MET") are all listed.
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
    coequal = _inhibited_targets(t)
    # Prefer a named target in the opening class line or first mechanism clause.
    # When the label names two or more co-equal targets (Lapatinib "both
    # EGFR and HER2", Neratinib "EGFR, HER2, and HER4", Amivantamab
    # "EGFR and MET"), list them all. A single co-equal target is used
    # the same way as the older first-named-target path.
    if has(r"\bvegfr2\b"):
        action = "that blocks a blood-vessel growth signal (VEGFR2)"
    elif has(r"\bMEK\b") and has(r"inhibitor", r"kinase") and not coequal:
        action = "that blocks a MEK signal"
    elif has(r"\bPD-L1\b", r"\bPD-1\b", r"programmed death"):
        action = ""
    elif coequal:
        action = _blocks_phrase(coequal)
    elif _opening_class_targets(t):
        action = _blocks_phrase(_opening_class_targets(t))
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
        r"in combination with:?\s+([^.;]{3,80}?)(?:"
        r",?\s+for\b|,?\s+the\s+(?:first|treatment|adjuvant)|"
        r",?\s+is indicated|\s+is indicated|,?\s+in adult|,?\s+in patients|"
        r"\s+\(\s*\d|\s*$)",
        re.I,
    ),
    re.compile(
        r",\s+in combination with:?\s+([^,.]{3,80}?),\s+is indicated",
        re.I,
    ),
    re.compile(
        r"as a single agent or in combination with:?\s+([^,.;]{3,60})",
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



def indication_units(clause: str) -> list[str]:
    """Split one numbered indication into each combination or single-agent unit.

    Neighbouring "in combination with" phrases in the same section often
    belong to different uses (for example FOLFIRI as a first treatment,
    irinotecan after another drug). Each unit keeps the section heading
    (cancer type and gene finding) so tree rules still see them, but
    partners are then scoped to that unit alone.

    "As a single agent or in combination with X" is one unit, not two.
    """
    cl = (clause or "").strip()
    if not cl:
        return []
    starts: list[int] = []
    for m in re.finditer(
        r"\bin combination with\b|\bas a single[- ]agent\b|\bas monotherapy\b",
        cl,
        re.I,
    ):
        prefix = cl[max(0, m.start() - 40) : m.start()].lower()
        # "as a single agent or in combination with" is one unit.
        if m.group(0).lower().startswith("in combination") and re.search(
            r"\bor\s+$", prefix
        ):
            continue
        starts.append(m.start())
    if len(starts) <= 1:
        return [cl]
    preamble = cl[: starts[0]].strip(" ,.;:")
    units = []
    for i, s in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(cl)
        body = cl[s:end].strip(" ,.;:")
        if not body:
            continue
        unit = (preamble + " " + body).strip() if preamble else body
        if len(unit) > 12:
            units.append(unit)
    return units or [cl]


def partner_sets(clause_texts: list[str]) -> list[list[str]]:
    """One partner set per unit (each 'in combination with' phrase).

    Identical sets from a repeated highlights/full-text pair are kept once,
    so the visible note does not say "or with" the same partner twice.
    """
    sets = []
    seen: set[tuple[str, ...]] = set()
    for cl in clause_texts:
        ps = combinations_in(cl)
        if not ps:
            continue
        key = tuple(x.lower() for x in ps)
        if key in seen:
            continue
        seen.add(key)
        sets.append(ps)
    return sets


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
    # Partners collected from more than one unit are alternative uses,
    # not one simultaneous combination. Join those with "or with".
    sets = partner_sets(clause_texts)
    if len(sets) >= 2:
        phrases = []
        for s in sets:
            phrases.append(" and ".join(s) if len(s) <= 2 else ", ".join(s[:-1]) + " and " + s[-1])
        partners = phrases[0] + "".join(f", or with {p}" for p in phrases[1:])
    else:
        partners = " and ".join(combos) if len(combos) <= 2 else ", ".join(combos[:-1]) + " and " + combos[-1]
    if any_single and any_combo:
        return f"Used alone, or together with {partners}."
    return f"Used together with {partners}."

