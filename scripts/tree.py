#!/usr/bin/env python3
"""Decision tree: cancer type → gene-change subtype → when it is used.

Built only from FDA label excerpts and trial condition/title fields,
by deterministic patterns documented below and on the page. Nothing
is assigned by hand. Unknown branches are labelled 'label does not say'
(therapies) or 'trial record does not say' (trials).

A therapy or trial can appear in more than one leaf if its source
names more than one use. Within a leaf, options are alphabetical.
That order is not a ranking.
"""
from __future__ import annotations

import re
from typing import Iterable

from labels import combinations_in, indication_units, indications, normalize  # noqa: E402

# Everyday cancer-type labels, with the source patterns that map to them.
# Longer, more specific patterns are tested first.
CANCER_TYPES: list[tuple[str, list[str]]] = [
    ("lung cancer", [
        r"non[- ]small cell lung", r"\bNSCLC\b", r"non-small-cell lung",
        r"lung adenocarcinoma", r"lung cancer", r"carcinoma, non-small-cell lung",
        r"carcinoma, small cell lung", r"\bSCLC\b", r"small cell lung",
    ]),
    ("bowel cancer", [
        r"colorectal", r"\bmCRC\b", r"\bCRC\b", r"colon cancer", r"rectal cancer",
        r"colon neoplasm",
    ]),
    ("lymphoma", [
        r"anaplastic large cell lymphoma",
        r"(?<!anaplastic\s)lymphoma",
        r"\bALCL\b",
    ]),
    ("head and neck cancer", [
        r"head and neck", r"\bHNSCC\b", r"squamous cell carcinoma of the head",
    ]),
    ("breast cancer", [r"breast cancer", r"breast carcinoma", r"breast neoplasm"]),
    ("melanoma (skin cancer)", [r"\bmelanoma\b"]),
    ("thyroid cancer", [r"thyroid"]),
    ("stomach cancer", [
        r"gastric", r"gastroesophageal", r"\bGEJ\b", r"stomach",
    ]),
    # Everyday name is already "cancer of the womb". The label abbreviation
    # "EC" (as in Dostarlimab's "recurrent or advanced EC") is the same cancer.
    ("cancer of the womb", [
        r"endometrial", r"endometrium",
        r"\bEC\b",
    ]),
    ("bile duct cancer", [
        r"cholangiocarcinoma", r"bile duct",
        r"biliary tract", r"\bBTC\b",
    ]),
    ("inflammatory myofibroblastic tumour", [
        r"inflammatory myofibroblastic tumou?r",
        r"\bIMT\b",
    ]),
    ("Erdheim-Chester disease", [
        r"erdheim[\s\-]*chester",
        r"\bECD\b",
    ]),
    ("kidney cancer", [r"renal cell", r"kidney cancer"]),
    ("bladder cancer", [r"bladder", r"urothelial"]),
    ("pancreatic cancer", [r"pancreatic", r"pancreas"]),
    ("brain tumour", [r"glioma", r"glioblastoma", r"astrocytoma", r"brain"]),
    ("cervical cancer", [r"cervical cancer", r"cervix"]),
    ("liver cancer", [r"hepatocellular", r"\bHCC\b", r"liver cancer"]),
    ("ovarian cancer", [r"ovarian", r"ovary"]),
    ("prostate cancer", [r"prostate"]),
    ("solid tumours (several cancer types)", [
        r"solid tumors", r"solid tumours", r"solid tumor",
    ]),
]

# Gene-change / mutation subtypes. Order: more specific first.
# The label is everyday English; patterns match the source text.
MUTATION_SUBTYPES: list[tuple[str, list[str]]] = [
    ("EGFR exon 20 insertion", [
        r"exon\s*20\s+insertion", r"ex20ins", r"exon 20 ins",
    ]),
    ("EGFR exon 19 deletion or L858R", [
        r"exon\s*19\s+delet(?:ion|ions)(?:\s+or\s+exon\s*21\s*\(?\s*L858R)?",
        r"exon\s*19\s+deletion or exon\s*21\s+\(?L858R",
        r"exon\s*21\s*\(?\s*L858R", r"\bL858R\b", r"exon\s*19\s+delet",
    ]),
    ("EGFR T790M", [r"\bT790M\b"]),
    ("EGFR gene changes the label lists as non-resistant", [
        r"non[- ]resistant\s+.*EGFR", r"non[- ]resistant epidermal",
    ]),
    ("EGFR gene change (no more precise subtype in the text)", [
        r"EGFR[- ]mutat", r"EGFR-mutated", r"epidermal growth factor receptor \(EGFR\)[- ]mutat",
        r"EGFR mutation",
    ]),
    ("ALK fusion or ALK-positive", [
        r"ALK[- ]positive", r"ALK[- ]fusion", r"anaplastic lymphoma kinase \(ALK\)[- ]positive",
        r"ALK-rearrang",
    ]),
    ("BRAF V600E", [r"BRAF\s*V600E", r"V600E"]),
    ("BRAF V600K", [r"BRAF\s*V600K", r"V600K"]),
    ("BRAF V600", [r"BRAF\s*V600", r"\bV600\b"]),
    ("KRAS G12C", [r"KRAS\s*G12C", r"\bG12C\b"]),
    ("KRAS wild-type (no KRAS change)", [
        r"wild[- ]type\s+RAS", r"wild[- ]type\s+KRAS", r"KRAS wild",
        r"K-Ras wild", r"K[- ]Ras wild[- ]type", r"Ras wild[- ]type",
        r"RAS wild[- ]type",
    ]),
    ("HER2-positive", [
        r"HER2[- ]positive", r"HER-2[- ]positive", r"HER2\+", r"ERBB2[- ]positive",
        r"HER2-overexpress", r"HER2[- ]overexpress",
        r"overexpress(?:es|ing)?\s+(?:the\s+)?(?:human\s+)?(?:epidermal growth factor receptor 2|HER2)",
    ]),
    ("HER2-low", [r"HER2[- ]low", r"HER2-low"]),
    ("HER2 mutation", [r"HER2[- ]mutat", r"ERBB2[- ]mutat"]),
    ("NTRK fusion", [r"NTRK\s+fusion", r"NTRK gene fusion", r"neurotrophic.*fusion"]),
    ("MSI-H or dMMR", [
        r"microsatellite instability[- ]high", r"\bMSI[- ]?H\b",
        r"mismatch repair deficien", r"\bdMMR\b",
    ]),
]

WHEN_USED: list[tuple[str, list[str]]] = [
    ("after chemoradiation", [
        r"following concurrent or sequential platinum-based chemoradiation",
        r"following.{0,40}chemoradiation", r"after chemoradiation",
    ]),
    ("after surgery", [
        r"\badjuvant\b", r"following tumor resection", r"following surgical",
        r"after surgery", r"post[- ]operative",
    ]),
    ("as a first treatment", [
        r"first[- ]line", r"first line", r"1st[- ]line",
        r"previously untreated", r"treatment[- ]naive", r"treatment naive",
        r"initial treatment",
    ]),
    ("as maintenance", [r"\bmaintenance\b"]),
    ("after another drug", [
        r"previously treated", r"prior systemic", r"after prior",
        r"who have received prior", r"who have received at least",
        r"disease(?: has)? progressed", r"following disease progression",
        r"after progression", r"second(?:[- ]or[- ]greater)?[- ]line",
        r"after platinum", r"on or after platinum",
        r"prior EGFR[- ]directed", r"after failure",
        r"following combination treatment",
        r"received prior.*chemotherapy",
        r"progressed on or after",
        r"refractory",
        r"who have failed",
        r"has failed",
        r"for whom prior .{0,60} has failed",
        r"prior platinum[- ]based therapy has failed",
    ]),
]

LABEL_UNKNOWN_CANCER = "label does not say the cancer type"
LABEL_UNKNOWN_MUTATION = "label does not say the gene-change subtype"
LABEL_UNKNOWN_WHEN = "label does not say when it is used"
TRIAL_UNKNOWN_CANCER = "trial record does not say the cancer type"
TRIAL_UNKNOWN_MUTATION = "trial record does not say the gene-change subtype"
TRIAL_UNKNOWN_WHEN = "trial record does not say when it is used"

TREE_HOW = (
    "This tree is built by a fixed computer rule from the FDA label text "
    "and from trial condition and title fields in this snapshot, not by hand. "
    "For each option, the text is searched first for a cancer type (lung, "
    "bowel, head and neck, and others listed in the rule), then for a "
    "gene-change subtype the label or trial names (for example EGFR exon 19 "
    "deletion or L858R, exon 20 insertion, T790M), then for when the text "
    "says the drug or study is used (first treatment, after another drug, "
    "after surgery). If the text does not name one of these, that branch "
    "is labelled “label does not say” or “trial record does not say”. "
    "An option can appear in more than one branch if its source names more "
    "than one use. Options in a branch are listed alphabetically. That "
    "order is not a ranking."
)


def _search(text: str, patterns: list[str]) -> bool:
    if not text:
        return False
    t = normalize(text)
    for pat in patterns:
        if re.search(pat, t, flags=re.I):
            return True
    return False


def cancers_in(text: str) -> list[str]:
    found = []
    for label, pats in CANCER_TYPES:
        if _search(text, pats):
            found.append(label)
    return found


def mutations_in(text: str, biomarker_id: str = "") -> list[str]:
    found = []
    for label, pats in MUTATION_SUBTYPES:
        if _search(normalize(text), pats):
            found.append(label)
    # Prefer a named EGFR subtype over "no more precise subtype" and over
    # "non-resistant" when the same text also names exon 19 / L858R / T790M
    # / exon 20 (as Afatinib's detailed indication does).
    named = [
        m for m in found
        if m.startswith("EGFR")
        and "no more precise" not in m
        and "non-resistant" not in m
    ]
    if named:
        found = [m for m in found if "no more precise" not in m and "non-resistant" not in m]
    elif any("no more precise" in m for m in found):
        found = [m for m in found if "no more precise" not in m or not named]
    return found


def whens_in(text: str) -> list[str]:
    found = []
    for label, pats in WHEN_USED:
        if _search(text, pats):
            found.append(label)
    return found


def _is_limitation(text: str) -> bool:
    return bool(
        re.search(
            r"limitations of use|not indicated for|not recommended for|"
            r"safety and efficacy.{0,80}not (?:been )?established|"
            r"were not established|has not been established|"
            r"use has not been established",
            text or "",
            re.I,
        )
    ) and not re.search(r"is indicated", text or "", re.I)



# An indication that continues after a Limitations of Use sentence,
# as in Lapatinib's highlights: capecitabine, then a Limitation, then
# "letrozole for the treatment…". Section-numbered indications (1.2 …)
# are not matched here; those already split on their own.
_CONTINUATION_IND = re.compile(
    r"(?:^|\.\s+)("
    r"[A-Za-z][A-Za-z0-9\-]{1,40}"
    r"(?:\s+[A-Za-z][A-Za-z0-9\-]{0,40}){0,2}"
    r"\s+for the treatment\b[\s\S]*)",
    re.I,
)


def _combo_preamble(text: str) -> str:
    m = re.search(r"(.*?)\bin combination with:?", text or "", re.I)
    return (m.group(0).strip() if m else "")



def _trim_trailing_limitations(body: str) -> str:
    """Drop trailing sentences that only qualify or limit a use."""
    sents = re.split(r"(?<=\.)\s+", (body or "").strip())
    kept = []
    for s in sents:
        if re.search(
            r"has not been compared|has not been established|"
            r"not indicated for|not recommended for|"
            r"safety and efficacy.{0,80}not (?:been )?established|"
            r"^Limitations of Use\b",
            s,
            re.I,
        ):
            break
        kept.append(s)
    return " ".join(kept).strip(" .;,-")


def _indication_after_limitation(text: str, preamble: str = "") -> str:
    """Keep an indication that follows a Limitations of Use sentence.

    Some labels put a Limitations sentence between two partners of the
    same "in combination with:" list. Splitting on "Limitations of Use:"
    and keeping only the head, or dropping the whole Limitations
    paragraph, silently drops that later indication.
    """
    mlim = re.search(r"Limitations of Use\s*:", text or "", re.I)
    rest = text[mlim.end():] if mlim else (text or "")
    if re.match(r"\s*\d+\.\d+", rest):
        return ""
    m = _CONTINUATION_IND.search(rest)
    if not m:
        return ""
    body = m.group(1).strip(" .;,-")
    if not body or len(body) < 12:
        return ""
    if re.match(r"\d+\.\d+", body):
        return ""
    body = _trim_trailing_limitations(body)
    if not body:
        return ""
    if preamble:
        return f"{preamble} {body}".strip()
    return body


def _clauses(text: str) -> list[str]:
    """Split a full Indications and Usage section into indication clauses.

    Numbered subsections (1.1, 1.2, …) are preferred over the opening
    highlights list, which otherwise merges every use into one blob and
    produces a cross-product of mutations and 'when' values. A numbered
    subsection that holds two 'is indicated' sentences is split so that
    (for example) ramucirumab with erlotinib is not mixed with ramucirumab
    with docetaxel.
    """
    if not text:
        return []
    t = normalize(text)
    t = t.replace("\u2022", "\n").replace("•", "\n")
    t = re.sub(r"(?<!\d)(\d+\.\d+\s+[A-Z(])", r"\n\1", t)
    t = re.sub(r"Limitations of Use\s*:", "\nLimitations of Use: ", t, flags=re.I)
    t = re.sub(r"(?<=\.)\s+(?=Vectibix is indicated)", "\n", t)
    t = re.sub(r"(?<=\.)\s+(?=Vectibix, in combination)", "\n", t)
    t = re.sub(r"(?<=\.)\s+(?=ERBITUX is indicated)", "\n", t)
    t = re.sub(r"\s+(?=As first-line therapy)", "\n", t)
    t = re.sub(r"\s+(?=As monotherapy)", "\n", t)
    t = re.sub(r"(?<=\.)\s+(?=(?:Metastatic Colorectal|RAS Wild-Type|KRAS G12C))", "\n", t)
    raw = [p.strip(" .;,-") for p in re.split(r"\n+", t) if p and len(p.strip()) > 12]
    # Prefer detailed numbered sections over the highlights preamble.
    has_detailed = any(re.match(r"\d+\.\d+\s", p) for p in raw)
    parts: list[str] = []
    in_detailed = not has_detailed
    last_preamble = ""
    for p in raw:
        if re.match(r"\d+\.\d+\s", p):
            in_detailed = True
        if has_detailed and not in_detailed:
            continue
        if re.match(r"1\s+INDICATIONS AND USAGE\b", p, re.I) and has_detailed:
            continue
        is_lim_para = bool(re.match(r"Limitations of Use\s*:", p, re.I)) or (
            _is_limitation(p) and re.search(r"Limitations of Use\s*:", p, re.I)
        )
        # Only indication clauses (not Limitations paragraphs) may refresh
        # the "in combination with:" preamble; otherwise the limitation
        # sentence itself is prepended and swallows the next partner.
        if _combo_preamble(p) and not is_lim_para:
            last_preamble = _combo_preamble(p)
        if is_lim_para:
            cont = _indication_after_limitation(p, last_preamble)
            if not cont:
                continue
            p = cont
        elif re.search(r"Limitations of Use\s*:", p, re.I):
            head = re.split(
                r"Limitations of Use\s*:", p, maxsplit=1, flags=re.I
            )[0].strip(" .;,-")
            # Preamble from the head (a real indication), not from the
            # Limitations sentence that follows it.
            head_pre = _combo_preamble(head) or last_preamble
            if _combo_preamble(head):
                last_preamble = _combo_preamble(head)
            cont = _indication_after_limitation(p, head_pre)
            if len(head) >= 12:
                parts.append(head)
            if cont and cont != head:
                parts.append(cont)
            continue
        elif _is_limitation(p):
            continue
        if len(p) < 12:
            continue
        parts.append(p)
    # Split a section that contains more than one 'is indicated'.
    out: list[str] = []
    for p in parts:
        bits = re.split(
            r"(?<=\.)\s+(?=(?:[A-Z][A-Za-z0-9®™ \-]{1,40})(?:is indicated|, in combination|, as a single))",
            p,
        )
        out.extend(b.strip() for b in bits if b and len(b.strip()) > 12)
    detailed = [
        c for c in out
        if re.search(r"is indicated", c, re.I)
        and not re.match(r"1\s+INDICATIONS AND USAGE\b", c, re.I)
    ]
    if detailed:
        out = [
            c for c in out
            if not re.match(r"1\s+INDICATIONS AND USAGE\b", c, re.I)
        ]
    return out or ([normalize(text)] if text else [])


def _selection_language(text: str, biomarker_id: str) -> bool:
    """True when a clause selects patients by this gene finding."""
    t = normalize(text)
    if biomarker_id == "EGFR":
        return bool(
            re.search(
                r"EGFR\s+exon|exon\s*19|exon\s*21\s*\(?L858R|\bL858R\b|\bT790M\b|"
                r"EGFR[- ]mutat|EGFR mutation|EGFR Mutation-Positive|"
                r"non[- ]resistant.{0,80}EGFR|"
                r"epidermal growth factor receptor\s*\(EGFR\)\s*(?:exon|mutat)|"
                r"non[- ]resistant epidermal",
                t,
                re.I,
            )
        )
    if biomarker_id == "ALK":
        return bool(re.search(r"\bALK[- ]positive\b|ALK[- ]fusion|ALK-rearrang|anaplastic lymphoma kinase", t, re.I))
    if biomarker_id == "BRAF-V600E":
        return bool(re.search(r"BRAF\s*V600|\bV600E\b", t, re.I))
    if biomarker_id == "KRAS-G12C":
        return bool(re.search(r"KRAS\s*G12C|\bG12C\b", t, re.I))
    if biomarker_id == "HER2":
        return bool(re.search(r"HER2[- ]positive|HER2[- ]low|HER2[- ]mutat|HER-2|ERBB2|HER2-overexpress|overexpress(?:es|ing)?\s+(?:the\s+)?(?:human\s+)?(?:epidermal growth factor receptor 2|HER2)", t, re.I))
    if biomarker_id == "NTRK":
        return bool(re.search(r"\bNTRK|neurotrophic", t, re.I))
    if biomarker_id == "MSI-H-dMMR":
        return bool(re.search(r"MSI[- ]?H|dMMR|microsatellite instability|mismatch repair deficien", t, re.I))
    return False




def _mentions_biomarker(text: str, biomarker_id: str) -> bool:
    """A clause is used on this biomarker page only if it talks about the gene."""
    t = normalize(text)
    if biomarker_id == "EGFR":
        return bool(re.search(
            r"\bEGFR\b|epidermal growth factor receptor|exon\s*19|exon\s*20|L858R|T790M",
            t, re.I,
        ))
    if biomarker_id == "ALK":
        return bool(re.search(r"\bALK\b|anaplastic lymphoma kinase", t, re.I))
    if biomarker_id == "BRAF-V600E":
        return bool(re.search(r"\bBRAF\b|V600", t, re.I))
    if biomarker_id == "KRAS-G12C":
        return bool(re.search(r"\bKRAS\b|\bG12C\b", t, re.I))
    if biomarker_id == "HER2":
        return bool(re.search(r"\bHER2\b|\bERBB2\b|HER-2", t, re.I))
    if biomarker_id == "NTRK":
        return bool(re.search(r"\bNTRK|neurotrophic", t, re.I))
    if biomarker_id == "MSI-H-dMMR":
        return bool(re.search(r"MSI|dMMR|microsatellite|mismatch repair", t, re.I))
    return True


def _new_section(clause: str) -> bool:
    """True when a clause starts a new numbered indication (reset inherit)."""
    return bool(re.match(r"\s*\d+\.\d+", clause or ""))


def therapy_branches(therapy: dict, biomarker_id: str) -> list[tuple[str, str, str]]:
    """Unique (cancer, mutation, when) triples from the full FDA label.

    If any clause selects patients by this gene finding, only those
    clauses are used, so a gastric-cancer paragraph on a multi-use drug
    does not inherit an EGFR mutation. If no clause uses selection
    language (an EGFR-targeting antibody with no mutation requirement),
    every clause is used except those that select on a different gene.
    If a (cancer, mutation) pair already has a named 'when', a leftover
    'label does not say when' for that pair is dropped.
    """
    text = indications(therapy)
    if not text:
        text = normalize(therapy.get("indicationsExcerpt") or therapy.get("relationEvidence") or "")
    clauses = []
    for cl in _clauses(text):
        clauses.extend(indication_units(cl) or [cl])
    any_sel = any(_selection_language(cl, biomarker_id) for cl in clauses)
    triples: set[tuple[str, str, str]] = set()
    clause_map: dict[tuple[str, str, str], list[str]] = {}
    inherit_c, inherit_m = [], []
    for cl in clauses:
        if _new_section(cl):
            inherit_c, inherit_m = [], []
        if any_sel:
            if not _selection_language(cl, biomarker_id):
                inherit_c, inherit_m = [], []
                continue
        elif _selection_language(cl, "") is False and _other_gene_selection(cl, biomarker_id):
            inherit_c, inherit_m = [], []
            continue
        cs = cancers_in(cl) or inherit_c
        ms = mutations_in(cl, biomarker_id) or inherit_m
        ws = whens_in(cl)
        if cancers_in(cl):
            inherit_c = cancers_in(cl)
        if mutations_in(cl, biomarker_id):
            inherit_m = mutations_in(cl, biomarker_id)
        if not cs:
            cs = [LABEL_UNKNOWN_CANCER]
        if not ms:
            ms = [LABEL_UNKNOWN_MUTATION]
        if not ws:
            ws = [LABEL_UNKNOWN_WHEN]
        for c in cs:
            for m in ms:
                for w in ws:
                    triples.add((c, m, w))
                    clause_map.setdefault((c, m, w), []).append(cl)
    # Drop a 'does not say' value when the same other two axes already
    # have a named value, and drop a fully unknown leaf if any specific
    # leaf exists.
    def _unknown(s: str) -> bool:
        return "does not say" in (s or "")

    named_cm = {(c, m) for (c, m, w) in triples if not _unknown(w)}
    named_cw = {(c, w) for (c, m, w) in triples if not _unknown(m)}
    named_mw = {(m, w) for (c, m, w) in triples if not _unknown(c)}
    has_specific = any(not (_unknown(c) and _unknown(m) and _unknown(w)) for (c, m, w) in triples)

    def _clause_sig(cl: str) -> str:
        partners = combinations_in(cl)
        if partners:
            return "partners:" + " ".join(sorted(x.lower() for x in partners))
        return "text:" + re.sub(r"\s+", " ", (cl or "").lower())[:160]

    def _distinct_clauses(triple, others_axes):
        """True when this leaf's clauses are not already on a more specific leaf."""
        these = clause_map.get(triple, [])
        other = []
        for tr, cls in clause_map.items():
            if tr == triple:
                continue
            if others_axes(tr):
                other.extend(cls)
        other_sigs = {_clause_sig(cl) for cl in other}
        return any(_clause_sig(cl) not in other_sigs for cl in these)

    kept = set()
    for (c, m, w) in triples:
        if _unknown(w) and (c, m) in named_cm:
            if not _distinct_clauses(
                (c, m, w),
                lambda tr: tr[0] == c and tr[1] == m and not _unknown(tr[2]),
            ):
                continue
        if _unknown(m) and (c, w) in named_cw:
            if not _distinct_clauses(
                (c, m, w),
                lambda tr: tr[0] == c and tr[2] == w and not _unknown(tr[1]),
            ):
                continue
        if _unknown(c) and (m, w) in named_mw:
            if not _distinct_clauses(
                (c, m, w),
                lambda tr: tr[1] == m and tr[2] == w and not _unknown(tr[0]),
            ):
                continue
        if has_specific and _unknown(c) and _unknown(m) and _unknown(w):
            continue
        kept.add((c, m, w))
    triples = kept
    if not triples:
        triples.add((LABEL_UNKNOWN_CANCER, LABEL_UNKNOWN_MUTATION, LABEL_UNKNOWN_WHEN))
    therapy["_leaf_clauses"] = {
        f"{c}|{m}|{w}": clause_map.get((c, m, w), [])
        for (c, m, w) in triples
    }
    return sorted(triples)


def _other_gene_selection(text: str, biomarker_id: str) -> bool:
    """True when a clause clearly selects on a gene that is not this page."""
    t = normalize(text)
    other = {
        "EGFR": r"\bBRAF\s*V600|\bALK[- ]positive\b|KRAS\s*G12C|\bNTRK\s+fusion|HER2[- ]positive",
        "ALK": r"EGFR\s+exon|\bBRAF\s*V600|KRAS\s*G12C",
        "BRAF-V600E": r"EGFR\s+exon|\bALK[- ]positive\b|KRAS\s*G12C",
        "KRAS-G12C": r"EGFR\s+exon|\bBRAF\s*V600|\bALK[- ]positive\b",
        "HER2": r"EGFR\s+exon|\bBRAF\s*V600|KRAS\s*G12C",
        "NTRK": r"EGFR\s+exon|\bBRAF\s*V600|KRAS\s*G12C",
        "MSI-H-dMMR": r"EGFR\s+exon|\bBRAF\s*V600|KRAS\s*G12C",
    }.get(biomarker_id, "")
    return bool(other and re.search(other, t, re.I))


def leaf_clauses(therapy: dict, triple: tuple[str, str, str]) -> list[str]:
    c, m, w = triple
    stored = (therapy.get("_leaf_clauses") or {}).get(f"{c}|{m}|{w}") or []
    if stored:
        return stored
    # Fallback: whole indications text.
    return [indications(therapy)]


def is_unknown_leaf(triple: tuple[str, str, str]) -> bool:
    return all("does not say" in x for x in triple)


def trial_branches(trial: dict, biomarker_id: str) -> list[tuple[str, str, str]]:
    text = " ".join(
        [
            trial.get("title") or "",
            " ".join(trial.get("conditions") or []),
            " ".join(trial.get("interventions") or []),
            trial.get("requirementEvidence") or "",
        ]
    )
    cs = cancers_in(text) or [TRIAL_UNKNOWN_CANCER]
    ms = mutations_in(text, biomarker_id) or [TRIAL_UNKNOWN_MUTATION]
    ws = whens_in(text) or [TRIAL_UNKNOWN_WHEN]
    triples = [(c, m, w) for c in cs for m in ms for w in ws]
    return sorted(triples)


def trial_phase_label(trial: dict) -> str:
    phases = trial.get("phases") or []
    if not phases:
        return "phase not stated"
    labels = {
        "PHASE1": "phase 1",
        "PHASE2": "phase 2",
        "PHASE3": "phase 3",
        "PHASE4": "phase 4",
        "EARLY_PHASE1": "early phase 1",
        "NA": "phase listed as NA",
    }
    return " / ".join(labels.get(p, p) for p in phases)


def build_tree(
    therapies: list[dict],
    trials: list[dict],
    edge: list[dict],
    withdrawn: list[dict],
    biomarker_id: str,
) -> list[dict]:
    """Nested list: cancer → mutation → when → options.

    Each option is {kind, record, sort_name}. Cancers, mutations and
    whens are sorted alphabetically, with 'does not say' branches last.
    """
    def _unk(s: str) -> bool:
        return "does not say" in s

    def _leaf_key(item: tuple) -> tuple:
        c, m, w = item[0], item[1], item[2]
        return (_unk(c), c.lower(), _unk(m), m.lower(), _unk(w), w.lower())

    rows = []
    for t in therapies:
        for triple in therapy_branches(t, biomarker_id):
            rows.append((*triple, "mainstream", t, t.get("name") or ""))
    for t in trials:
        for triple in trial_branches(t, biomarker_id):
            rows.append((*triple, "trials", t, t.get("nctId") or t.get("title") or ""))
    for a in edge:
        # On-the-edge: use disease + molecularProfile from CIViC as text.
        text = " ".join([
            a.get("disease") or "",
            a.get("molecularProfile") or "",
            a.get("summary") or "",
        ])
        cs = cancers_in(text) or [LABEL_UNKNOWN_CANCER]
        ms = mutations_in(text, biomarker_id) or [a.get("molecularProfile") or LABEL_UNKNOWN_MUTATION]
        ws = [LABEL_UNKNOWN_WHEN]
        name = ", ".join(a.get("therapies") or []) or f"CIViC {a.get('id')}"
        for c in cs:
            for m in ms:
                for w in ws:
                    rows.append((c, m, w, "on-the-edge", a, name))
    for wrec in withdrawn:
        t = wrec["therapy"] if isinstance(wrec, dict) and "therapy" in wrec else wrec
        for triple in therapy_branches(t, biomarker_id):
            rows.append((*triple, "withdrawn", wrec, t.get("name") or ""))

    # Nest.
    cancers: dict[str, dict] = {}
    for c, m, w, kind, rec, sort in rows:
        cancers.setdefault(c, {}).setdefault(m, {}).setdefault(w, []).append(
            {"kind": kind, "record": rec, "sort_name": sort}
        )
    for c in cancers:
        for m in cancers[c]:
            for w in cancers[c][m]:
                cancers[c][m][w].sort(key=lambda o: (o["sort_name"] or "").lower())

    def _sort_labels(labels: Iterable[str]) -> list[str]:
        return sorted(labels, key=lambda s: (_unk(s), s.lower()))

    tree = []
    for c in _sort_labels(cancers):
        muts = []
        for m in _sort_labels(cancers[c]):
            whens = []
            for w in _sort_labels(cancers[c][m]):
                opts = cancers[c][m][w]
                whens.append({"when": w, "options": opts, "count": len(opts)})
            n = sum(x["count"] for x in whens)
            muts.append({"mutation": m, "whens": whens, "count": n})
        n = sum(x["count"] for x in muts)
        tree.append({"cancer": c, "mutations": muts, "count": n})
    return tree


def trial_groups(trials: list[dict], biomarker_id: str) -> list[dict]:
    """Trials grouped by cancer type, then phase, alphabetical by NCT."""
    buckets: dict[tuple[str, str], list] = {}
    for t in trials:
        text = " ".join([t.get("title") or "", " ".join(t.get("conditions") or [])])
        cs = cancers_in(text) or [TRIAL_UNKNOWN_CANCER]
        phase = trial_phase_label(t)
        # A trial with two cancer types appears in both groups.
        for c in cs:
            buckets.setdefault((c, phase), []).append(t)
    for key in buckets:
        buckets[key].sort(key=lambda t: (t.get("nctId") or "").upper())
    groups = []
    for (c, phase), items in sorted(
        buckets.items(),
        key=lambda kv: ("does not say" in kv[0][0], kv[0][0].lower(), kv[0][1]),
    ):
        groups.append({"cancer": c, "phase": phase, "trials": items, "count": len(items)})
    return groups


def trial_count_summary(trials: list[dict], biomarker_id: str, fr: int, ch: int) -> str:
    """One upfront sentence of counts, everyday words, no jargon codes."""
    n = len(trials)
    groups = trial_groups(trials, biomarker_id)
    # Roll up by cancer.
    by_c: dict[str, dict] = {}
    for g in groups:
        by_c.setdefault(g["cancer"], {"n": 0, "phases": []})
        by_c[g["cancer"]]["n"] += g["count"]
        by_c[g["cancer"]]["phases"].append(f"{g['count']} {g['phase']}")
    bits = []
    for c, info in sorted(by_c.items(), key=lambda kv: ("does not say" in kv[0], kv[0].lower())):
        phases = ", ".join(info["phases"])
        bits.append(f"{info['n']} in {c} ({phases})")
    head = f"{n} recruiting " + ("study" if n == 1 else "studies")
    if bits:
        head += ": " + "; ".join(bits)
    head += f". {fr} with a site in France, {ch} with a site in Switzerland."
    return head

# One plain line per branch, shown on the mockup, explaining why it exists.
BRANCH_WHY: dict[str, str] = {
    "lung cancer": "The FDA label or the trial record names lung cancer (often as NSCLC, a type of lung cancer).",
    "bowel cancer": "The FDA label or the trial record names colorectal (bowel) cancer.",
    "head and neck cancer": "The FDA label or the trial record names head and neck cancer.",
    "breast cancer": "The FDA label or the trial record names breast cancer.",
    "brain tumour": "The FDA label or the trial record names a brain tumour.",
    "cancer of the womb": "The FDA label or the trial record names endometrial cancer (cancer of the womb).",
    "ovarian cancer": "The FDA label or the trial record names ovarian cancer.",
    "stomach cancer": "The FDA label or the trial record names stomach (gastric) or gastroesophageal cancer.",
    "thyroid cancer": "The FDA label or the trial record names thyroid cancer.",
    "bile duct cancer": "The FDA label or the trial record names bile duct cancer (cholangiocarcinoma) or biliary tract cancer.",
    "inflammatory myofibroblastic tumour": "The FDA label or the trial record names an inflammatory myofibroblastic tumour.",
    "Erdheim-Chester disease": "The FDA label or the trial record names Erdheim-Chester disease.",
    "kidney cancer": "The FDA label or the trial record names kidney (renal) cancer.",
    "bladder cancer": "The FDA label or the trial record names bladder or urothelial cancer.",
    "pancreatic cancer": "The FDA label or the trial record names pancreatic cancer.",
    "cervical cancer": "The FDA label or the trial record names cervical cancer.",
    "liver cancer": "The FDA label or the trial record names liver cancer.",
    "prostate cancer": "The FDA label or the trial record names prostate cancer.",
    "BRAF V600E": "The FDA label or the trial record names a BRAF V600E change.",
    "BRAF V600K": "The FDA label or the trial record names a BRAF V600K change.",
    "BRAF V600": "The FDA label or the trial record names a BRAF V600 change.",
    "HER2-low": "The record names HER2-low disease.",
    "solid tumours (several cancer types)": "The record names solid tumours, a group of several cancer types.",
    "melanoma (skin cancer)": "The FDA label or the trial record names melanoma, a skin cancer.",
    "lymphoma": "The FDA label or the trial record names a lymphoma.",
    "EGFR exon 19 deletion or L858R": "The FDA label names these two EGFR gene changes.",
    "EGFR exon 20 insertion": "The FDA label or the trial record names an EGFR exon 20 insertion (an extra piece of DNA in that part of the gene).",
    "EGFR T790M": "The FDA label names an EGFR T790M change, often after an earlier EGFR drug.",
    "EGFR gene changes the label lists as non-resistant": "The label uses the wording “non-resistant EGFR mutations” and does not only name one subtype in that clause.",
    "EGFR gene change (no more precise subtype in the text)": "The text says there is an EGFR gene change but does not name a more precise subtype.",
    "KRAS wild-type (no KRAS change)": "The label is for people whose KRAS gene has no change at the places the label names.",
    "KRAS G12C": "The FDA label or the trial record names a KRAS G12C change.",
    "HER2 mutation": "The record names a HER2 gene change.",
    "HER2-positive": "The record names HER2-positive disease.",
    "ALK fusion or ALK-positive": "The record names an ALK gene change or an ALK-positive test.",
    "NTRK fusion": "The record names an NTRK fusion (an NTRK gene joined to another gene).",
    "MSI-H or dMMR": "The record names an MSI-H or dMMR test finding.",
    "as a first treatment": "The label or trial record says this is used as a first treatment.",
    "after another drug": "The label or trial record says this is used after another drug, or after the disease has progressed.",
    "after surgery": "The label says this is used after surgery (adjuvant treatment).",
    "after chemoradiation": "The label says this is used after chemoradiation (chemotherapy given with radiotherapy).",
    "as maintenance": "The label says this is used as maintenance treatment.",
    "label does not say the cancer type": "The FDA label text in this snapshot does not name a cancer type that the tree rule recognises.",
    "label does not say the gene-change subtype": "The FDA label text does not name a gene-change subtype that the tree rule recognises.",
    "label does not say when it is used": "The FDA label text does not say whether this is a first treatment or used after another drug.",
    "trial record does not say the cancer type": "The trial record does not name a cancer type that the tree rule recognises.",
    "trial record does not say the gene-change subtype": "The trial record does not name a gene-change subtype that the tree rule recognises.",
    "trial record does not say when it is used": "The trial record does not say whether the study is a first treatment or is used after another drug.",
}


def branch_why(label: str) -> str:
    return BRANCH_WHY.get(label, "This branch exists because the label or trial record used this wording.")


def mainstream_completeness(biomarker: dict, therapies: list) -> list[str]:
    """Every Mainstream therapy must land in at least one leaf that is not
    only 'does not say' branches. Returns a list of failure messages.
    """
    errors = []
    bid = biomarker.get("id") or ""
    for t in therapies:
        branches = therapy_branches(t, bid)
        ok = [b for b in branches if not is_unknown_leaf(b) and "does not say" not in b[0]]
        # At least one leaf with a recognised cancer type.
        if not ok:
            errors.append(
                f"{bid}: {(t.get('name') or '?')} has no Mainstream leaf with a "
                f"recognised cancer type (branches={branches})"
            )
    return errors

