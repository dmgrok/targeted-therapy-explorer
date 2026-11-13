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
    mainstream_therapies,
    on_the_edge_assertions,
    option_id,
    trial_options,
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
            "EGFR, short for epidermal growth factor receptor, is a gene.",
            "Amplification and mutations of EGFR have been shown to be driving events in many cancer types, including non-small cell lung cancer, glioblastoma and basal-like breast cancers.",
        ],
        "test_report": (
            "If a test report mentions EGFR, it is recording a finding about this gene. "
            "This page lists public FDA companion diagnostics that look for EGFR, and the therapies and trials in this snapshot that use EGFR as a selection criterion. "
            "That mention is not a diagnosis or a treatment decision on its own."
        ),
        "source_ids": ["civic-gene:EGFR", "biomarker:EGFR", "summary:EGFR", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:EGFR"],
    },
    "ALK": {
        "what": [
            "ALK, short for anaplastic lymphoma kinase, is a gene.",
            "ALK amplifications, fusions and mutations have been shown to be driving events in non-small cell lung cancer.",
        ],
        "test_report": (
            "If a test report mentions ALK, it is recording a finding about this gene. "
            "This page lists public FDA companion diagnostics that look for ALK, and the therapies and trials in this snapshot that use ALK as a selection criterion. "
            "That mention is not a diagnosis or a treatment decision on its own."
        ),
        "source_ids": ["civic-gene:ALK", "biomarker:ALK", "summary:ALK", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:ALK"],
    },
    "BRAF-V600E": {
        "what": [
            "BRAF V600E is a substitution in the BRAF gene: the mutation of valine 600 to glutamic acid (V600E).",
            "BRAF mutations are found to be recurrent in many cancer types, and of these, V600E is the most prevalent. V600E has been determined to be an activating mutation.",
        ],
        "test_report": (
            "If a test report mentions BRAF V600E, it is recording a finding about this gene change. "
            "This page lists public FDA companion diagnostics that look for BRAF V600E, and the therapies and trials in this snapshot that use BRAF V600E as a selection criterion. "
            "That mention is not a diagnosis or a treatment decision on its own."
        ),
        "source_ids": ["civic-gene:BRAF", "biomarker:BRAF-V600E", "summary:BRAF-V600E", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:BRAF-V600E"],
    },
    "KRAS-G12C": {
        "what": [
            "KRAS G12C is a substitution in the KRAS gene, which belongs to the RAS family of proteins.",
            "Mutations in the RAS family of proteins are frequently observed across cancer types, and the amino acid positions that account for the overwhelming majority of these mutations are G12, G13 and Q61.",
        ],
        "test_report": (
            "If a test report mentions KRAS G12C, it is recording a finding about this gene change. "
            "This page lists public FDA companion diagnostics that look for KRAS G12C, and the therapies and trials in this snapshot that use KRAS G12C as a selection criterion. "
            "That mention is not a diagnosis or a treatment decision on its own."
        ),
        "source_ids": ["civic-gene:KRAS", "biomarker:KRAS-G12C", "summary:KRAS-G12C", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:KRAS-G12C"],
    },
    "HER2": {
        "what": [
            "HER2, also called ERBB2 or human epidermal growth factor receptor 2, is a gene.",
            "According to the CIViC gene summary in this snapshot, ERBB2 is amplified and/or overexpressed in 20-30% of invasive breast carcinomas.",
        ],
        "test_report": (
            "If a test report mentions HER2, it is recording a finding about this gene. "
            "This page lists public FDA companion diagnostics that look for HER2, and the therapies and trials in this snapshot that use HER2 as a selection criterion. "
            "That mention is not a diagnosis or a treatment decision on its own."
        ),
        "source_ids": ["civic-gene:ERBB2", "biomarker:HER2", "summary:HER2", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:HER2"],
    },
    "NTRK": {
        "what": [
            "NTRK stands for neurotrophic tyrosine receptor kinase.",
            "This page covers fusions involving NTRK1, NTRK2 or NTRK3, as named in this explorer's biomarker list. This snapshot does not include a CIViC gene summary for these genes.",
        ],
        "test_report": (
            "If a test report mentions an NTRK fusion, it is recording a finding about NTRK1, NTRK2 or NTRK3. "
            "This page lists public FDA companion diagnostics that look for NTRK, and the therapies and trials in this snapshot that use NTRK as a selection criterion. "
            "That mention is not a diagnosis or a treatment decision on its own."
        ),
        "source_ids": ["biomarker:NTRK", "summary:NTRK", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:NTRK"],
    },
    "MSI-H-dMMR": {
        "what": [
            "MSI-H / dMMR stands for microsatellite instability-high or mismatch-repair deficient.",
            "The CIViC summary in this snapshot is for MLH1, a tumor suppressor gene involved in DNA mismatch repair. Germline mutations in this gene are known to cause Lynch syndrome.",
        ],
        "test_report": (
            "If a test report mentions MSI-H or dMMR, it is recording a finding about microsatellite instability-high or mismatch-repair deficient status. "
            "This page lists public FDA companion diagnostics that look for MSI-H / dMMR, and the therapies and trials in this snapshot that use MSI-H / dMMR as a selection criterion. "
            "That mention is not a diagnosis or a treatment decision on its own."
        ),
        "source_ids": ["civic-gene:MLH1", "biomarker:MSI-H-dMMR", "summary:MSI-H-dMMR", "method:categories"],
        "test_report_source_ids": ["method:categories", "biomarker:MSI-H-dMMR"],
    },
}

HOME_INTRO = {
    "what": [
        "This site maps a closed list of tumour biomarkers to approved targeted therapies and recruiting clinical trials, using public sources only.",
        "It is general information. It is not medical advice, a diagnosis or a treatment recommendation, and it is not a medical device.",
    ],
    "how": (
        "Pick a biomarker to see today's options in this snapshot, tagged Mainstream (FDA-approved for that biomarker), "
        "Trials (recruiting studies that require it), or On the edge (earlier CIViC evidence). "
        "The order of options does not mean one is better than another. Talk to your oncologist."
    ),
}

# ---------------------------------------------------------------------------
# Therapy line composition. Connecting words are ours; every number,
# date and drug name comes from the therapy record.
# ---------------------------------------------------------------------------

CLASS_RE = re.compile(
    r"(?:is|are)\s+(a|an)\s+([^.]{3,160}?)\s+indicated",
    re.I,
)
ROUTE_RES = [
    (re.compile(r"\btablets\b", re.I), "tablets"),
    (re.compile(r"\bcapsules\b", re.I), "capsules"),
    (re.compile(r"\borally\b", re.I), "orally"),
    (re.compile(r"\bintravenously\b", re.I), "intravenously"),
    (re.compile(r"\bintravenous\b", re.I), "intravenous"),
    (re.compile(r"\bsubcutaneously\b", re.I), "subcutaneously"),
    (re.compile(r"\bsubcutaneous\b", re.I), "subcutaneous"),
    (re.compile(r"\binfusion\b", re.I), "infusion"),
    (re.compile(r"\binjection\b", re.I), "injection"),
]
SECTION_HEAD = re.compile(r"^\s*(?:\d+\.?\s*)?INDICATIONS AND USAGE\s*", re.I)
CITE_NUM = re.compile(r"\(\s*[\d.,\s]+(?:\s*,\s*[\d.]+)*\s*\)")
PHASE_LABEL = {
    "PHASE1": "phase 1",
    "PHASE2": "phase 2",
    "PHASE3": "phase 3",
    "PHASE4": "phase 4",
    "EARLY_PHASE1": "early phase 1",
    "NA": "NA",
}


def _unique_brands(therapy: dict) -> list[str]:
    name = (therapy.get("name") or "").strip().lower()
    out = []
    seen = {name}
    for b in therapy.get("brandNames") or []:
        b = (b or "").strip()
        if not b:
            continue
        key = b.lower()
        if key in seen:
            continue
        seen.add(key)
        # Prefer ordinary casing over ALL CAPS when both exist.
        out.append(b)
    # Drop an all-caps duplicate of a mixed-case brand already kept.
    cleaned = []
    lowers = set()
    for b in out:
        k = b.lower()
        if k in lowers:
            continue
        # If we have both RYBREVANT and Rybrevant, keep the not-all-caps one.
        siblings = [x for x in out if x.lower() == k]
        pick = next((x for x in siblings if not x.isupper()), siblings[0])
        if pick not in cleaned:
            cleaned.append(pick)
            lowers.add(k)
    return cleaned


def _tidy_excerpt(text: str) -> str:
    t = text or ""
    leading = t.startswith("\u2026") or t.startswith("...")
    trailing = t.endswith("\u2026") or t.endswith("...")
    t = t.strip(".\u2026 ")
    t = SECTION_HEAD.sub("", t)
    t = t.replace("\u2022", "; ")
    t = CITE_NUM.sub("", t)
    t = re.sub(r"\[see[^\]]*\]\s*\.?", "", t)
    t = re.sub(r"\[see[^\]]*$", "", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+:\s+", ": ", t)
    t = t.strip(" ;,.")
    if leading:
        m = re.search(r"(?:\.|;)\s+([A-Z].*)", t)
        if m and len(m.group(1)) >= 40:
            t = m.group(1)
        elif t and t[0].islower():
            rest = t.split(" ", 1)
            t = rest[1] if len(rest) > 1 else t
    # Drop a trailing stub that is clearly a new section heading cut short
    # (e.g. "1.1 Adjuvant Treatme") or a mid-word ending from a truncated excerpt.
    t = re.sub(r"\s+\d+\.\d+\s+[A-Z][A-Za-z]*\.?$", "", t)
    if trailing:
        last = t.split()[-1] if t else ""
        # A leftover letter or obvious mid-word stump ("m", "non-", "fluorouraci", "ob").
        stump = bool(re.search(r"[A-Za-z]$", last)) and (
            len(last) <= 2
            or last.endswith("-")
            or (
                last[0].islower()
                and len(last) >= 6
                and not re.search(
                    r"(ing|ed|ion|ent|est|ous|ive|ity|ies|ted|ble|ine|ase|oma|amp|test|label|use)$",
                    last,
                    re.I,
                )
            )
        )
        if stump:
            t = t[: t.rfind(last)].strip(" ;,.")
            # If what remains after a sentence break is a short leftover clause, drop it.
            for sep in (". ", "; ", ": "):
                i = t.rfind(sep)
                if i >= 80 and (len(t) - i) < 90:
                    t = t[:i].strip()
                    break
    return t.strip(" ;,.")


def _class_phrase(excerpt: str) -> str:
    m = CLASS_RE.search(excerpt or "")
    if not m:
        return ""
    article, body = m.group(1).lower(), m.group(2).strip()
    # Keep scientific abbreviations as they appear; just squeeze space.
    body = re.sub(r"\s+", " ", body)
    return f"{article} {body}"


def _route_phrase(excerpt: str) -> str:
    for pat, label in ROUTE_RES:
        if pat.search(excerpt or ""):
            return label
    return ""


def _ema_bits(therapy: dict) -> list[str]:
    bits = []
    for e in therapy.get("ema") or []:
        status = (e.get("status") or "").strip()
        if status.lower() != "authorised":
            continue
        name = (e.get("name") or "").strip()
        date = (e.get("authorisationDate") or "").strip()
        if not name:
            continue
        if date:
            bits.append(
                f"An EMA record for {name} lists the status as {status}, "
                f"with an authorisation date of {date}."
            )
        else:
            bits.append(f"An EMA record for {name} lists the status as {status}.")
    return bits


def therapy_line(biomarker: dict, therapy: dict) -> dict:
    bid = biomarker["id"]
    name = (therapy.get("name") or "").strip()
    brands = _unique_brands(therapy)
    brand_bit = f" ({', '.join(brands)})" if brands else ""
    excerpt = therapy.get("indicationsExcerpt") or ""
    rel = relevant_excerpt(excerpt, bid, n=520) if excerpt else ""
    tidy = _tidy_excerpt(rel or excerpt)
    klass = _class_phrase(excerpt)
    route = _route_phrase(excerpt)

    head = f"{name}{brand_bit}"
    if klass:
        head += f" is {klass}"
        if route:
            head += f", and the label mentions {route}"
        head += "."
    else:
        head += " is listed on an FDA label in this snapshot."
        if route:
            head += f" The label mentions {route}."

    if tidy and klass:
        # Avoid repeating "X is a kinase inhibitor indicated for" after the head.
        tidy = re.sub(
            r"^.{0,80}?\bindicated(?:\s+for)?\s*:?\s*",
            "",
            tidy,
            count=1,
            flags=re.I,
        ).strip(" ;,.")
    # Stop before a Limitations of Use sentence that the excerpt cut mid-word.
    tidy = re.sub(
        r"\s*Limitations of Use:?\s*Safety and efficacy[^.]*$",
        "",
        tidy,
        flags=re.I,
    ).strip(" ;,.")
    # Stop before a truncated accelerated-approval tail.
    tidy = re.sub(
        r"\s*This indication is approved under accelerated approval based on.*$",
        " This indication is approved under accelerated approval",
        tidy,
        flags=re.I,
    ).strip(" ;,.")
    parts = [head]
    if tidy:
        parts.append(f"The FDA label lists this use: {tidy}.")
    parts.extend(_ema_bits(therapy))
    text = " ".join(parts)
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


def _phase_phrase(phases: list) -> str:
    if not phases:
        return ""
    labels = [PHASE_LABEL.get(p, p) for p in phases]
    if len(labels) == 1:
        return labels[0]
    return " / ".join(labels)


def trial_line(trial: dict) -> dict:
    nct = (trial.get("nctId") or "").strip()
    title = (trial.get("title") or "").strip()
    status = (trial.get("status") or "").strip()
    phase = _phase_phrase(trial.get("phases") or [])
    cond = "; ".join(trial.get("conditions") or [])
    iv = "; ".join(trial.get("interventions") or [])
    start = (trial.get("startDate") or "").strip()
    parts = [f"{nct} is a {status} study"]
    if phase:
        parts[0] += f" ({phase})"
    parts[0] += "."
    if title:
        parts.append(f"It is titled “{title}”.")
    if cond:
        parts.append(f"Conditions listed: {cond}.")
    if iv:
        parts.append(f"Interventions listed: {iv}.")
    if start:
        parts.append(f"The record lists a start date of {start}.")
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
    th = ", ".join(assertion.get("therapies") or []) or "a named therapy"
    summary = (assertion.get("summary") or "").strip()
    amp = assertion.get("ampLevel") or ""
    status = assertion.get("status") or ""
    disease = assertion.get("disease") or ""
    mp = assertion.get("molecularProfile") or ""
    parts = [
        f"CIViC assertion {aid} is early evidence about {th}"
    ]
    extra = []
    if mp:
        extra.append(f"molecular profile {mp}")
    if disease:
        extra.append(f"disease {disease}")
    if extra:
        parts[0] += " (" + "; ".join(extra) + ")"
    parts[0] += "."
    if summary:
        parts.append(f"CIViC’s summary is: {summary}")
        if not summary.endswith("."):
            parts[-1] += "."
    level_bits = []
    if amp:
        level_bits.append(f"evidence level {amp}")
    if status:
        level_bits.append(f"status {status}")
    if level_bits:
        parts.append(
            "The record lists " + " and ".join(level_bits) + "."
        )
    parts.append("This is not an FDA approval.")
    return {
        "id": option_id(ON_THE_EDGE, assertion),
        "category": ON_THE_EDGE,
        "text": " ".join(parts),
        "sources": [
            {
                "id": f"civic:{aid}",
                "url": assertion.get("url") or "",
                "label": f"CIViC assertion {aid}",
            }
        ],
    }


def cdx_line(cdx: dict) -> dict:
    diag = cdx["diagnostic"]
    ind = cdx["indication"]
    sample = cdx.get("sampleType") or ""
    via = cdx.get("viaTherapy") or ""
    text = f"{diag} is an FDA companion diagnostic listed for {ind}."
    if sample:
        text += f" The indication column lists the sample type as {sample}."
    if via:
        text += f" It appears on the snapshot record for {via}."
    return {
        "id": option_id("cdx", cdx),
        "category": "cdx",
        "text": text,
        "sources": [
            {
                "id": f"cdx:{diag}|{ind}",
                "url": cdx.get("url") or "",
                "label": "FDA companion diagnostic list",
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
    for t in mainstream_therapies(biomarker):
        lines.append(therapy_line(biomarker, t))
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
                "text": "The U.S. Food and Drug Administration, which approves drugs and some tests in the United States. This site uses FDA labels, the pharmacogenomic-biomarker table, and the companion-diagnostic list.",
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
                "term": "ampLevel",
                "text": "The evidence level CIViC records on an assertion, such as TIER_I_LEVEL_A or TIER_II_LEVEL_D. This site uses that field as written. It does not add a meaning beyond what the field itself says.",
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
