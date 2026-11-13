#!/usr/bin/env python3
"""Write committed plain-language files from the current snapshot.

Run this by hand when the snapshot changes and the source_hash check
fails. Review the resulting JSON before committing. This script is
not called at site-build time, so a weekly snapshot PR will fail
until the plain text is regenerated and reviewed.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from categories import (  # noqa: E402
    MAINSTREAM,
    ON_THE_EDGE,
    TRIALS,
    companion_diagnostics,
    leftover_civic,
    on_the_edge_assertions,
    option_id,
    trial_options,
)
from withdrawn import (  # noqa: E402
    display_mainstream,
    withdrawn_therapies,
)
from matching import relevant_excerpt  # noqa: E402
from plain import (  # noqa: E402
    BIOMARKER_IDS,
    PLAIN_DIR,
    home_source_hash,
    source_hash,
    validate_all,
)

PARIS = ZoneInfo("Europe/Paris")

# ---------------------------------------------------------------------------
# Hand-written intros. Every factual clause is taken from the cited
# snapshot field. The CIViC typo "amplfied" is not reused. The KRAS
# gene summary's claim that RAS inhibitors "have not been successful"
# is not reused: this snapshot itself lists FDA-approved KRAS G12C
# drugs, so that sentence would be misleading.
# ---------------------------------------------------------------------------

INTROS: dict[str, dict] = {
    "EGFR": {
        "what": [
            "EGFR is a gene.",
            "Changes in this gene can help some cancers grow, including some lung, brain and breast cancers.",
        ],
        "test_report": (
            "If a test report mentions EGFR, it is noting a finding about this gene. "
            "That note is not a diagnosis, and it is not a decision about treatment."
        ),
        "source_ids": ["civic-gene:EGFR", "biomarker:EGFR", "summary:EGFR", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:EGFR"],
    },
    "ALK": {
        "what": [
            "ALK is a gene.",
            "Changes in ALK — extra copies, joins with another gene, or mutations — can help some lung cancers grow.",
        ],
        "test_report": (
            "If a test report mentions ALK, it is noting a finding about this gene. "
            "That note is not a diagnosis, and it is not a decision about treatment."
        ),
        "source_ids": ["civic-gene:ALK", "biomarker:ALK", "summary:ALK", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:ALK"],
    },
    "BRAF-V600E": {
        "what": [
            "BRAF V600E is a change in the BRAF gene.",
            "This change is the most common BRAF change in many cancers, and it can switch the gene on.",
        ],
        "test_report": (
            "If a test report mentions BRAF V600E, it is noting this gene change. "
            "That note is not a diagnosis, and it is not a decision about treatment."
        ),
        "source_ids": ["civic-gene:BRAF", "biomarker:BRAF-V600E", "summary:BRAF-V600E", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:BRAF-V600E"],
    },
    "KRAS-G12C": {
        "what": [
            "KRAS G12C is a change in the KRAS gene, which belongs to a family of genes called RAS.",
            "Changes at this spot in RAS genes are often seen in several cancers.",
        ],
        "test_report": (
            "If a test report mentions KRAS G12C, it is noting this gene change. "
            "That note is not a diagnosis, and it is not a decision about treatment."
        ),
        "source_ids": ["civic-gene:KRAS", "biomarker:KRAS-G12C", "summary:KRAS-G12C", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:KRAS-G12C"],
    },
    "HER2": {
        "what": [
            "HER2, also called ERBB2, is a gene.",
            "The public summary in this snapshot says extra HER2 is found in 20 to 30 percent of invasive breast cancers.",
        ],
        "test_report": (
            "If a test report mentions HER2, it is noting a finding about this gene. "
            "That note is not a diagnosis, and it is not a decision about treatment."
        ),
        "source_ids": ["civic-gene:ERBB2", "biomarker:HER2", "summary:HER2", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:HER2"],
    },
    "NTRK": {
        "what": [
            "NTRK is a group of three genes: NTRK1, NTRK2 and NTRK3.",
            "This page is about when one of these genes joins onto another gene. This snapshot has no public gene summary for them.",
        ],
        "test_report": (
            "If a test report mentions an NTRK fusion, it is noting a finding about NTRK1, NTRK2 or NTRK3. "
            "That note is not a diagnosis, and it is not a decision about treatment."
        ),
        "source_ids": ["biomarker:NTRK", "summary:NTRK", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:NTRK"],
    },
    "MSI-H-dMMR": {
        "what": [
            "MSI-H and dMMR are test findings about how a tumour repairs its DNA.",
            "The public summary in this snapshot is only about MLH1, one gene in that repair system, and says inherited changes in MLH1 can cause Lynch syndrome.",
        ],
        "test_report": (
            "If a test report mentions MSI-H or dMMR, it is noting that finding. "
            "That note is not a diagnosis, and it is not a decision about treatment."
        ),
        "source_ids": ["civic-gene:MLH1", "biomarker:MSI-H-dMMR", "summary:MSI-H-dMMR", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:MSI-H-dMMR"],
    },
}

HOME_INTRO = {
    "what": [
        "This site maps a short list of tumour gene findings to approved drugs and recruiting trials, from public sources only.",
        "It is general information. It is not medical advice, a diagnosis or a treatment recommendation.",
    ],
    "how": (
        "Pick a gene finding. You will see a decision tree: cancer type, then the gene change, then when a drug is used. "
        "Tags are Mainstream, Trials, or On the edge. Order is not a ranking. Talk to your oncologist."
    ),
}

# ---------------------------------------------------------------------------
# Short everyday option lines, about 25 words. Connecting words are ours.
# Route words (pill, capsule, infusion) only if the label names a form.
# "Daily" only if the excerpt says daily. Dates only from EMA records.
# ---------------------------------------------------------------------------

CLASS_RE = re.compile(
    r"(?:is|are)\s+(a|an)\s+([^.]{3,160}?)\s+indicated",
    re.I,
)
PHASE_LABEL = {
    "PHASE1": "phase 1",
    "PHASE2": "phase 2",
    "PHASE3": "phase 3",
    "PHASE4": "phase 4",
    "EARLY_PHASE1": "early phase 1",
    "NA": "NA",
}


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?", text or ""))


def _unique_brands(therapy: dict) -> list[str]:
    name = (therapy.get("name") or "").strip().lower()
    out = []
    seen = {name}
    for b in therapy.get("brandNames") or []:
        b = (b or "").strip()
        if not b:
            continue
        k = b.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(b)
    cleaned, lowers = [], set()
    for b in out:
        k = b.lower()
        if k in lowers:
            continue
        siblings = [x for x in out if x.lower() == k]
        pick = next((x for x in siblings if not x.isupper()), siblings[0])
        cleaned.append(pick)
        lowers.add(k)
    return cleaned


def _route(excerpt: str) -> str:
    """Everyday form/route, only if the label names it. Never guess 'daily'."""
    t = excerpt or ""
    if re.search(r"\btablets?\b", t, re.I):
        return "pill"
    if re.search(r"\bcapsules?\b", t, re.I):
        return "capsule"
    if re.search(r"\bintravenous(?:ly)?\b|\binfusion\b", t, re.I):
        return "infusion"
    if re.search(r"\bsubcutaneous(?:ly)?\b", t, re.I):
        return "injection under the skin"
    if re.search(r"\binjection\b", t, re.I):
        return "injection"
    if re.search(r"\borally\b|\boral use\b|\boral\b", t, re.I):
        return "pill"
    return ""


def _a(word: str) -> str:
    return "an" if (word or "")[:1].lower() in "aeiou" else "a"


def _kind_phrase(excerpt: str, route: str, biomarker_id: str) -> str:
    m = CLASS_RE.search(excerpt or "")
    body = (m.group(2).strip().lower() if m else "")
    low = (excerpt or "").lower()
    gene = {
        "EGFR": "EGFR",
        "ALK": "ALK",
        "BRAF-V600E": "BRAF",
        "KRAS-G12C": "KRAS",
        "HER2": "HER2",
        "NTRK": "NTRK",
        "MSI-H-dMMR": "",
    }.get(biomarker_id, "")
    blocks = (
        "kinase inhibitor" in body or "kinase inhibitor" in low
        or "inhibitor of the ras" in body or "antagonist" in body
        or "antagonist" in low
    )
    if blocks:
        if route and gene:
            return f"{_a(route)} {route} that blocks the {gene} signal"
        if gene:
            return "a drug that blocks the " + gene + " signal"
        if route:
            return f"{_a(route)} {route} that blocks a growth signal"
        return "a drug that blocks a growth signal"
    if "antibody" in body or "antibody" in low:
        base = "a lab-made antibody"
        if "conjugate" in body or "conjugate" in low:
            base = "a lab-made antibody linked to a drug"
        if route:
            base += f", given as {_a(route)} {route}"
        return base
    if route:
        return f"{_a(route)} {route}"
    return ""


def _cancer_short(text: str) -> str:
    from tree import cancers_in
    cs = cancers_in(text)
    # Prefer a single everyday name.
    if "lung cancer" in cs:
        return "advanced lung cancer"
    if "bowel cancer" in cs:
        return "advanced bowel cancer"
    if "head and neck cancer" in cs:
        return "head and neck cancer"
    if "breast cancer" in cs:
        return "breast cancer"
    if "melanoma (skin cancer)" in cs:
        return "melanoma (a skin cancer)"
    if "thyroid cancer" in cs:
        return "thyroid cancer"
    if "stomach cancer" in cs:
        return "stomach cancer"
    if "cancer of the womb" in cs:
        return "cancer of the womb"
    if "solid tumours (several cancer types)" in cs:
        return "several types of solid tumour"
    if cs:
        return cs[0]
    return ""


def _mutation_short(text: str, biomarker_id: str) -> str:
    from tree import mutations_in
    ms = mutations_in(text, biomarker_id)
    # Drop generic if specific exists — mutations_in already does this for EGFR.
    if not ms:
        return ""
    nice = {
        "EGFR exon 20 insertion": "an EGFR exon 20 insertion",
        "EGFR exon 19 deletion or L858R": "an EGFR exon 19 deletion or L858R change",
        "EGFR T790M": "an EGFR T790M change",
        "EGFR mutations the label calls non-resistant": "certain EGFR mutations",
        "EGFR gene changes the label lists as non-resistant": "certain EGFR mutations",
        "EGFR mutation (subtype not further named)": "an EGFR mutation",
        "EGFR gene change (no more precise subtype in the text)": "an EGFR mutation",
        "ALK fusion or ALK-positive": "an ALK change",
        "BRAF V600E": "a BRAF V600E change",
        "BRAF V600K": "a BRAF V600K change",
        "BRAF V600": "a BRAF V600 change",
        "KRAS G12C": "a KRAS G12C change",
        "HER2-positive": "HER2-positive disease",
        "HER2-low": "HER2-low disease",
        "HER2 mutation": "a HER2 mutation",
        "NTRK fusion": "an NTRK fusion",
        "MSI-H or dMMR": "an MSI-H or dMMR finding",
        "KRAS wild-type (no KRAS change)": "no KRAS gene change",
    }
    return nice.get(ms[0], ms[0])


def _ema_year(therapy: dict) -> tuple[str, str]:
    """(name, year) of the earliest authorised EMA record with a date.

    Using the first record in the list would pick a later biosimilar
    (for example Herwenda in 2023) over the original (Herceptin in 2000).
    The year itself comes from the authorisationDate field.
    """
    found = []
    for e in therapy.get("ema") or []:
        if (e.get("status") or "").lower() != "authorised":
            continue
        date = (e.get("authorisationDate") or "").strip()
        name = (e.get("name") or "").strip()
        if not date:
            continue
        m = re.search(r"(19|20)\d{2}", date)
        if m:
            found.append((int(m.group(0)), name, m.group(0)))
    if not found:
        return "", ""
    found.sort()
    return found[0][1], found[0][2]


def therapy_line(biomarker: dict, therapy: dict) -> dict:
    bid = biomarker["id"]
    name = (therapy.get("name") or "").strip()
    brands = _unique_brands(therapy)
    head = f"{name} ({', '.join(brands)})" if brands else name
    excerpt = therapy.get("indicationsExcerpt") or ""
    from matching import relevant_excerpt
    rel = relevant_excerpt(excerpt, bid, n=520) if excerpt else excerpt
    route = _route(excerpt)
    kind = _kind_phrase(excerpt, route, bid)
    cancer = _cancer_short(rel or excerpt)
    mut = _mutation_short(rel or excerpt, bid)
    ema_name, year = _ema_year(therapy)

    bits = [f"{head}:"]
    if kind:
        bits[0] += f" {kind}."
    else:
        bits[0] += " a drug named on the FDA label in this snapshot."
    use = "Approved"
    if cancer:
        use += f" for {cancer}"
    if mut:
        use += f" with {mut}"
    if not cancer and not mut:
        use += " for a use named on the FDA label"
    use += "."
    bits.append(use)
    if year:
        bits.append(f"Authorised in Europe since {year}.")
    text = " ".join(bits)
    # If over the soft cap, drop the Europe clause first, then shorten use.
    if word_count(text) > 25 and year:
        text = " ".join(bits[:2])
    if word_count(text) > 28:
        # Last-resort trim of the use clause.
        short_use = "Approved for a use named on the FDA label."
        text = bits[0] + " " + short_use
        if year and word_count(text + f" Authorised in Europe since {year}.") <= 28:
            text = text + f" Authorised in Europe since {year}."
    fda = therapy.get("fda") or {}
    url = fda.get("dailymedUrl") or fda.get("drugsfdaUrl") or ""
    if not url:
        for c in therapy.get("citations") or []:
            if c.get("url"):
                url = c["url"]
                break
    return {
        "id": option_id(MAINSTREAM, therapy),
        "category": MAINSTREAM,
        "text": text,
        "sources": [
            {
                "id": f"therapy:{bid}:{name}",
                "url": url,
                "label": "FDA drug label / EMA record",
            }
        ],
    }


def withdrawn_line(biomarker: dict, therapy: dict, entry: dict) -> dict:
    bid = biomarker["id"]
    name = (therapy.get("name") or "").strip()
    brands = _unique_brands(therapy)
    # Prefer Exkivity as the brand if the catalog names it.
    head = f"{name} ({', '.join(brands)})" if brands else name
    if not brands and "Exkivity" in (entry.get("names") or []):
        head = f"{name} (Exkivity)"
    date = entry.get("effective_date") or ""
    year = ""
    if date:
        m = re.search(r"(19|20)\d{2}", date)
        year = m.group(0) if m else date
    # "15 July 2024" — 15 and 2024 are in 2024-07-15? "15" is in "2024-07-15"? 
    # 2024-07-15 contains 2024, 07, 15. "15" appears. "July" does not.
    # Use 15/07/2024 or "2024-07-15" as in the catalog, or "since 2024".
    if year:
        text = (
            f"{head}: withdrawn from the US market. "
            f"The FDA withdrew approval in {year}."
        )
    else:
        text = f"{head}: withdrawn from the US market, according to the FDA."
    url = ""
    for s in entry.get("sources") or []:
        if s.get("url"):
            url = s["url"]
            break
    return {
        "id": f"withdrawn:{name}",
        "category": "withdrawn",
        "text": text,
        "sources": [
            {
                "id": f"withdrawn:{entry.get('id')}",
                "url": url,
                "label": (entry.get("sources") or [{}])[0].get("label") or "Withdrawal record",
            }
        ],
    }


def _phase_phrase(phases: list) -> str:
    if not phases:
        return ""
    labels = [PHASE_LABEL.get(p, p) for p in phases]
    return " / ".join(labels)


def _short_trial_title(title: str) -> str:
    """Keep a short everyday title; do not invent drugs or numbers."""
    t = (title or "").strip()
    # Drop leading "A Study of " / "Study of "
    t = re.sub(r"^(?:a\s+)?(?:phase\s+\w+\s+)?(?:study of|trial of)\s+", "", t, flags=re.I)
    # Truncate at a clause boundary under ~18 words.
    words = t.split()
    if len(words) > 16:
        t = " ".join(words[:14]).rstrip(",;:") + "…"
    return t


def trial_line(trial: dict) -> dict:
    nct = (trial.get("nctId") or "").strip()
    title = _short_trial_title(trial.get("title") or "")
    phase = _phase_phrase(trial.get("phases") or [])
    n_countries = len(trial.get("countries") or [])
    parts = [nct]
    if title:
        parts[0] += f": {title}."
    else:
        parts[0] += "."
    mid = "A recruiting study"
    if phase:
        mid += f" ({phase})"
    mid += "."
    parts.append(mid)
    if n_countries:
        noun = "country" if n_countries == 1 else "countries"
        parts.append(f"Sites in {n_countries} {noun}.")
    return {
        "id": option_id(TRIALS, trial),
        "category": TRIALS,
        "text": " ".join(parts),
        "sources": [
            {
                "id": f"trial:{nct}",
                "url": trial.get("url") or "",
                "label": "ClinicalTrials.gov",
            }
        ],
    }


def edge_line(assertion: dict) -> dict:
    aid = assertion.get("id")
    th = ", ".join(assertion.get("therapies") or []) or "a named drug"
    disease = assertion.get("disease") or ""
    mp = assertion.get("molecularProfile") or ""
    # Everyday, no ampLevel / TIER / CIViC codes in the visible text.
    # "early evidence" is our category wording; status is a source word.
    status = assertion.get("status") or ""
    bits = [f"{th}: early evidence"]
    extra = []
    if mp:
        extra.append(mp)
    if disease:
        extra.append(disease)
    if extra:
        bits[0] += " for " + ", ".join(extra)
    bits[0] += "."
    if status:
        bits.append(f"The public record lists this as {status}.")
    bits.append("This is not an FDA approval.")
    text = " ".join(bits)
    if word_count(text) > 28:
        text = f"{th}: early evidence, not an FDA approval."
        if status and word_count(text + f" Listed as {status}.") <= 28:
            text += f" Listed as {status}."
    return {
        "id": option_id(ON_THE_EDGE, assertion),
        "category": ON_THE_EDGE,
        "text": text,
        "sources": [
            {
                "id": f"civic:{aid}",
                "url": assertion.get("url") or "",
                "label": "Public evidence record",
            }
        ],
    }


def cdx_line(cdx: dict) -> dict:
    diag = cdx["diagnostic"]
    ind = cdx["indication"]
    sample = cdx.get("sampleType") or ""
    # Everyday sample words.
    sample_nice = sample
    low = (sample or "").lower()
    if low == "tissue":
        sample_nice = "a tissue sample"
    elif low == "plasma":
        sample_nice = "a blood (plasma) sample"
    elif "tissue or plasma" in low or "tissue / plasma" in low:
        sample_nice = "a tissue or blood (plasma) sample"
    cancer = _cancer_short(ind)
    text = f"{diag} is an FDA companion test"
    if cancer:
        text += f" for {cancer}"
    text += "."
    if sample_nice:
        text += f" It uses {sample_nice}."
    return {
        "id": option_id("cdx", cdx),
        "category": "cdx",
        "text": text,
        "sources": [
            {
                "id": f"cdx:{diag}|{ind}",
                "url": cdx.get("url") or "",
                "label": "FDA companion test list",
            }
        ],
    }


def _source_label(sid: str) -> str:
    if sid.startswith("civic-gene:"):
        return "CIViC gene summary"
    if sid.startswith("summary:"):
        return "CIViC gene summary"
    if sid.startswith("biomarker:"):
        return "This snapshot’s biomarker record"
    if sid == "method:categories":
        return "How this page is built"
    if sid == "method:home":
        return "This explorer’s method"
    if sid.startswith("therapy:"):
        return "FDA drug label / EMA record"
    if sid.startswith("trial:"):
        return "ClinicalTrials.gov"
    if sid.startswith("cdx:"):
        return "FDA companion diagnostic list"
    if sid.startswith("civic:"):
        return "CIViC assertion"
    return sid


def _refs_from_ids(ids: list[str], index_urls: dict[str, str]) -> list[dict]:
    refs = []
    for sid in ids:
        refs.append({"id": sid, "url": index_urls.get(sid, ""), "label": _source_label(sid)})
    return refs


def generate_biomarker(snap: dict, biomarker: dict, generated_at: str) -> dict:
    bid = biomarker["id"]
    intro_spec = INTROS[bid]
    # Attach URLs from summary sources / civic genes where we have them.
    url_by_id: dict[str, str] = {}
    for src in biomarker.get("summarySources") or []:
        if src.get("url"):
            url_by_id["summary:" + bid] = src["url"]
            url_by_id["civic-gene:" + (biomarker.get("name") or "")] = src["url"]
    for g in (biomarker.get("civic") or {}).get("genes") or []:
        if g.get("url"):
            url_by_id[f"civic-gene:{g.get('name')}"] = g["url"]

    lines = []
    for c in companion_diagnostics(biomarker):
        lines.append(cdx_line(c))
    for t in display_mainstream(biomarker):
        lines.append(therapy_line(biomarker, t))
    for rec in withdrawn_therapies(biomarker):
        lines.append(withdrawn_line(biomarker, rec["therapy"], rec["entry"]))
    for t in trial_options(biomarker):
        lines.append(trial_line(t))
    for a in on_the_edge_assertions(biomarker):
        lines.append(edge_line(a))

    return {
        "biomarker_id": bid,
        "generated_at": generated_at,
        "source_hash": source_hash(snap, biomarker),
        "intro": {
            "what": intro_spec["what"],
            "test_report": intro_spec["test_report"],
            "sources": _refs_from_ids(intro_spec["source_ids"], url_by_id),
            "test_report_sources": _refs_from_ids(
                intro_spec["test_report_source_ids"], url_by_id
            ),
        },
        "lines": lines,
    }


def generate_home(snap: dict, generated_at: str) -> dict:
    return {
        "generated_at": generated_at,
        "source_hash": home_source_hash(snap),
        "intro": {
            "what": HOME_INTRO["what"],
            "how": HOME_INTRO["how"],
            "sources": [{"id": "method:home", "url": "", "label": "This explorer's method"}],
        },
        "lines": [
            {
                "id": "home:how",
                "text": HOME_INTRO["how"],
                "sources": [{"id": "method:home", "url": "", "label": "This explorer's method"}],
            }
        ],
    }


def generate_glossary() -> dict:
    # No unsourced statistics. "20-30%" belongs on the HER2 page, not here.
    return {
        "generated_at": datetime.now(PARIS).isoformat(timespec="seconds"),
        "terms": [
            {
                "term": "Biomarker",
                "text": "A measurable feature of a tumour, such as a gene change, that can be used as a selection criterion for a therapy or a trial.",
            },
            {
                "term": "Mutation",
                "text": "A change in the DNA sequence of a gene.",
            },
            {
                "term": "TKI (tyrosine kinase inhibitor)",
                "text": "A type of targeted drug. The letters stand for tyrosine kinase inhibitor. The FDA labels in this snapshot sometimes describe a drug as a kinase inhibitor.",
            },
            {
                "term": "NSCLC",
                "text": "Non-small cell lung cancer, a type of lung cancer named in many of the FDA labels in this snapshot.",
            },
            {
                "term": "FDA",
                "text": "The U.S. Food and Drug Administration, which approves drugs and some tests in the United States. This site uses FDA labels, an FDA table of gene findings and drugs, and the companion-test list.",
            },
            {
                "term": "EMA",
                "text": "The European Medicines Agency, which authorises medicines in the European Union. This site adds an EMA match when one is found.",
            },
            {
                "term": "Companion diagnostic",
                "text": "A test on the FDA’s list of authorised companion diagnostic devices, used to identify people who may be considered for a corresponding therapy.",
            },
            {
                "term": "CIViC",
                "text": "A public, volunteer-curated cancer knowledgebase released under a public-domain dedication. Its statements are not regulatory approvals.",
            },
            {
                "term": "Fusion",
                "text": "When parts of two genes join and form an abnormal gene. Reports may mention an ALK fusion or an NTRK fusion.",
            },
            {
                "term": "Exon",
                "text": "A numbered segment of a gene. A report may mention a change in a specific exon.",
            },
            {
                "term": "Recruiting",
                "text": "A clinical trial whose ClinicalTrials.gov record in this snapshot lists the status as recruiting, meaning it was listed as enrolling participants at the time of that record.",
            },
            {
                "term": "Indication",
                "text": "The use listed on a drug’s official label: what the drug was approved for, in which disease, and with which test or conditions, as written in the FDA label.",
            },
        ],
    }


def main() -> int:
    data_path = ROOT / "data" / "snapshot.json"
    snap = json.loads(data_path.read_text(encoding="utf-8"))
    generated_at = datetime.now(PARIS).isoformat(timespec="seconds")
    PLAIN_DIR.mkdir(parents=True, exist_ok=True)

    (PLAIN_DIR / "glossary.json").write_text(
        json.dumps(generate_glossary(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (PLAIN_DIR / "home.json").write_text(
        json.dumps(generate_home(snap, generated_at), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for b in snap.get("biomarkers") or []:
        doc = generate_biomarker(snap, b, generated_at)
        path = PLAIN_DIR / f"{b['id']}.json"
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(doc['lines'])} lines)")

    errors = validate_all(snap)
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} errors):", file=sys.stderr)
        for e in errors:
            print(" ", e, file=sys.stderr)
        return 1
    print("validation PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
