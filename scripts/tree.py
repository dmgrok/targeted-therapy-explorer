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
    ("cancer of the womb", [r"endometrial", r"endometrium"]),
    ("bile duct cancer", [r"cholangiocarcinoma", r"bile duct"]),
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
    ("EGFR mutations the label calls non-resistant", [
        r"non[- ]resistant\s+.*EGFR", r"non[- ]resistant epidermal",
    ]),
    ("EGFR mutation (subtype not further named)", [
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
    ]),
    ("HER2-positive", [
        r"HER2[- ]positive", r"HER-2[- ]positive", r"HER2\+", r"ERBB2[- ]positive",
        r"HER2-overexpress", r"HER2[- ]overexpress",
        r"overexpress(?:ing)?\s+(?:human\s+)?(?:epidermal growth factor receptor 2|HER2)",
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
    ("after surgery", [
        r"\badjuvant\b", r"following tumor resection", r"following surgical",
        r"after surgery", r"post[- ]operative",
    ]),
    ("as a first treatment", [
        r"first[- ]line", r"first line", r"1st[- ]line",
        r"previously untreated", r"treatment[- ]naive", r"treatment naive",
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
    for pat in patterns:
        if re.search(pat, text, flags=re.I):
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
        if _search(text, pats):
            found.append(label)
    # If a more specific EGFR subtype was found, drop the generic one.
    specific = [m for m in found if m.startswith("EGFR") and "not further named" not in m]
    if specific:
        found = [m for m in found if "not further named" not in m]
    return found


def whens_in(text: str) -> list[str]:
    found = []
    for label, pats in WHEN_USED:
        if _search(text, pats):
            found.append(label)
    return found


def _clauses(text: str) -> list[str]:
    """Split a label excerpt into rough indication clauses."""
    if not text:
        return []
    t = text.replace("\u2022", "\n").replace("•", "\n")
    t = re.sub(r"\s+", " ", t)
    parts = re.split(r"(?:;\s+|\n+|\(\s*\d+(?:\.\d+)?\s*\))", t)
    parts = [p.strip(" .;,-") for p in parts if p and len(p.strip()) > 12]
    return parts or [text]


def therapy_branches(therapy: dict, biomarker_id: str) -> list[tuple[str, str, str]]:
    """Unique (cancer, mutation, when) triples from the FDA excerpt."""
    text = therapy.get("indicationsExcerpt") or therapy.get("relationEvidence") or ""
    clauses = _clauses(text)
    # Also consider the full text as a fallback clause so a mention that
    # only appears as a header is not lost.
    if text and text not in clauses:
        clauses.append(text)
    triples: set[tuple[str, str, str]] = set()
    # Inherit cancer/mutation from earlier clauses when a short clause
    # only names the "when".
    inherit_c, inherit_m = [], []
    for cl in clauses:
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
    if not triples:
        triples.add((LABEL_UNKNOWN_CANCER, LABEL_UNKNOWN_MUTATION, LABEL_UNKNOWN_WHEN))
    return sorted(triples)


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
