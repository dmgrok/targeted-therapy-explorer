#!/usr/bin/env python3
"""Decision-tree site: options → gene → cancer → mutation → when → table.

Built from the same snapshot, plain-language lines, decision-tree rules
and withdrawal catalog as the rest of the repo. Every biomarker in the
closed list is built the same way. Pages are static HTML with relative
links. No JavaScript is required to walk the tree.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_site import (  # noqa: E402
    DISCLAIMER_LONG,
    DISCLAIMER_SHORT,
    esc,
    fmt_date,
    notice,
)
from categories import (  # noqa: E402
    AI_NOTE,
    MAINSTREAM,
    ON_THE_EDGE,
    ORDER_NOTE,
    RAW_CATEGORY_RULES,
    TRIALS,
    on_the_edge_assertions,
    option_id,
    trial_options,
)
from generate_plain import _unique_brands  # noqa: E402
from ema_indications import europe_phrase  # noqa: E402
from plain import load_plain, line_by_id  # noqa: E402
from labels import combo_note, entry_for, what_it_is  # noqa: E402
from tree import (  # noqa: E402
    TREE_HOW,
    branch_why,
    leaf_clauses,
    build_tree,
)
from withdrawn import (  # noqa: E402
    display_mainstream,
    indication_notes,
    withdrawn_therapies,
)

SITE = ROOT / "site"
OUT = SITE  # trees live under site/b/<id>/
TREE = SITE / "b"

# Visible level names in this mockup (renamed from the first PR).
LEVELS = {
    "mainstream": ("Mainstream", "level-mainstream"),
    "trials": ("In testing", "level-testing"),
    "on-the-edge": ("On the edge", "level-edge"),
    "withdrawn": ("Withdrawn", "level-withdrawn"),
}

LEVEL_DEFS = (
    ("Mainstream", "An FDA-approved drug for this gene finding, in this snapshot, that has not been withdrawn as a whole product."),
    ("In testing", "A recruiting study whose entry rules require this gene finding."),
    ("On the edge", "Early public evidence that names a drug. It is not an FDA approval in this snapshot."),
)

# Inline, always-visible definitions (not hover-only).
MUTATION_DEFS = {
    "EGFR exon 20 insertion": "an extra piece of DNA in that part of the EGFR gene",
    "EGFR exon 19 deletion or L858R": "two EGFR gene changes named on many labels",
    "EGFR T790M": "an EGFR gene change often named as resistance to earlier drugs",
    "EGFR gene changes the label lists as non-resistant": "EGFR gene changes the label lists as non-resistant",
    "EGFR gene change (no more precise subtype in the text)": "an EGFR gene change, without a more precise subtype in the text",
    "KRAS wild-type (no KRAS change)": "the KRAS gene has no change at the places the label names",
    "HER2 mutation": "a change in the HER2 gene itself",
    "HER2-positive": "a test showing too much HER2 protein, or a HER2 gene gain",
    "HER2-low": "a test showing a low amount of HER2 protein",
    "ALK fusion or ALK-positive": "an ALK gene joined to another gene, or a test that is ALK-positive",
    "BRAF V600E": "a specific change in the BRAF gene, named V600E",
    "BRAF V600K": "a specific change in the BRAF gene, named V600K",
    "BRAF V600": "a change at position 600 of the BRAF gene",
    "KRAS G12C": "a specific change in the KRAS gene, named G12C",
    "NTRK fusion": "an NTRK gene joined to another gene",
    "MSI-H or dMMR": "a test finding of high microsatellite instability or deficient mismatch repair",
}

CANCER_DEFS = {
    "melanoma (skin cancer)": "a cancer that starts in pigment cells of the skin",
    "solid tumours (several cancer types)": "cancers that form a lump, rather than a blood cancer",
    "brain tumour": "a tumour that starts in the brain",
}

TREE_HOW_SHORT = (
    "This tree is built by a fixed rule from the FDA label and from trial "
    "records in this snapshot, not by hand. You pick a cancer type, then a "
    "gene change the label names, then when the drug is used, when the text "
    "says so. If the text does not say, that branch is labelled “label does "
    "not say” or “trial record does not say”. Options in a table are listed "
    "alphabetically within each level. That order is not a ranking."
)

CLOSED_LIST = [
    ("EGFR", True, "EGFR"),
    ("ALK", True, "ALK"),
    ("BRAF V600E", True, "BRAF-V600E"),
    ("KRAS G12C", True, "KRAS-G12C"),
    ("HER2", True, "HER2"),
    ("NTRK", True, "NTRK"),
    ("MSI-H / dMMR", True, "MSI-H-dMMR"),
]

BIOMARKER_LABEL = {bid: label for label, _ready, bid in CLOSED_LIST}


def slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "item"


def title_case_cancer(s: str) -> str:
    if s.startswith("label does not") or s.startswith("trial record does not"):
        return s
    return s[:1].upper() + s[1:] if s else s


def inline_def(term: str) -> str:
    d = MUTATION_DEFS.get(term) or CANCER_DEFS.get(term)
    if not d:
        return esc(title_case_cancer(term))
    return (
        f'{esc(title_case_cancer(term))} '
        f'<span class="inline-def">({esc(d)})</span>'
    )


def asset_prefix(depth: int) -> str:
    return "../" * depth


def mock_head(title: str, depth: int) -> str:
    prefix = asset_prefix(depth)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="A plain-language map of approved targeted therapies and recruiting trials, by gene finding. {DISCLAIMER_SHORT}">
  <title>{esc(title)}</title>
  <link rel="stylesheet" href="{prefix}assets/css/style.css">
  <link rel="stylesheet" href="{prefix}assets/css/mockup.css">
</head>
<body class="mockup">
"""


def mock_foot(depth: int) -> str:
    prefix = asset_prefix(depth)
    return f"""
    <footer class="mock-foot">
      <p class="fine">{esc(DISCLAIMER_SHORT)} This site uses only public sources. It does not recommend a treatment. Options in a table are listed alphabetically within each level. That order is not a ranking.</p>
      <p class="fine"><a href="{prefix}index.html">Home</a>
      · <a href="{prefix}options/index.html">Drug pages</a>
      · <a href="{prefix}cases/index.html">Case studies</a>
      · <a href="{prefix}about.html">About and sources</a>
      · <a href="{prefix}notice.html">Notice</a>
      · <a href="https://github.com/dmgrok/targeted-therapy-explorer">Source code</a></p>
    </footer>
  </div>
  <script src="{prefix}assets/js/app.js" defer></script>
</body>
</html>
"""


def sources_block(inner: str, summary: str = "Sources") -> str:
    if not (inner or "").strip():
        return ""
    return (
        f'<details class="sources-toggle"><summary>{esc(summary)}</summary>'
        f'<div class="sources-body">{inner}</div></details>'
    )


def level_tag(kind: str) -> str:
    label, cls = LEVELS.get(kind, (kind, "level"))
    return f'<span class="level {cls}">{esc(label)}</span>'


def level_legend() -> str:
    items = "".join(
        f'<li><strong>{esc(name)}</strong> — {esc(defn)}</li>'
        for name, defn in LEVEL_DEFS
    )
    raw = f'<p class="excerpt">{esc(RAW_CATEGORY_RULES)}</p>'
    return (
        '<section class="levels" id="levels">'
        "<h2>The three levels</h2>"
        f"<ul class='level-defs'>{items}</ul>"
        f"<p class='fine'>{esc(ORDER_NOTE)} “In testing” is the name used here for recruiting studies.</p>"
        f"<p class='fine'>{esc(AI_NOTE)}</p>"
        + sources_block(raw, "Exact assignment rule")
        + "</section>"
    )


def tree_note() -> str:
    raw = (
        f'<p class="excerpt">{esc(TREE_HOW)}</p>'
        '<p class="fine">The rule lives in scripts/tree.py. Cancer types, gene-change '
        "subtypes and “when used” phrases are fixed lists in that file.</p>"
    )
    return (
        f'<p class="lede tree-how">{esc(TREE_HOW_SHORT)}</p>'
        + sources_block(raw, "How this tree is built")
    )


def crumbs(parts: list[tuple[str, str]], depth: int) -> str:
    """parts: list of (href or '', label). Last is current."""
    bits = []
    for i, (href, label) in enumerate(parts):
        if href and i < len(parts) - 1:
            bits.append(f'<a href="{esc(href)}">{esc(label)}</a>')
        else:
            bits.append(f"<span>{esc(label)}</span>")
    return '<nav class="crumbs" aria-label="Your path">' + " / ".join(bits) + "</nav>"


def display_name(kind: str, rec) -> tuple[str, str]:
    if kind == "mainstream":
        name = rec.get("name") or "Drug"
        brands = ", ".join(_unique_brands(rec))
        return name, brands
    if kind == "withdrawn":
        t = rec["therapy"] if isinstance(rec, dict) and "therapy" in rec else rec
        name = t.get("name") or "Drug"
        brands = ", ".join(_unique_brands(t))
        entry = rec.get("entry") if isinstance(rec, dict) else None
        if not brands and entry and "Exkivity" in (entry.get("names") or []):
            brands = "Exkivity"
        return name, brands
    if kind == "trials":
        return rec.get("nctId") or "Study", ""
    if kind == "on-the-edge":
        return ", ".join(rec.get("therapies") or []) or "Public evidence", ""
    return "Option", ""


def line_for(kind: str, rec, plain: dict) -> dict | None:
    if kind == "mainstream":
        return line_by_id(plain, option_id(MAINSTREAM, rec))
    if kind == "trials":
        return line_by_id(plain, option_id(TRIALS, rec))
    if kind == "on-the-edge":
        return line_by_id(plain, option_id(ON_THE_EDGE, rec))
    if kind == "withdrawn":
        t = rec["therapy"]
        return line_by_id(plain, f"withdrawn:{(t.get('name') or '').strip()}")
    return None


def approval_cell(kind: str, rec, triple: tuple[str, str, str] | None = None) -> str:
    if kind == "withdrawn":
        entry = rec.get("entry") or {}
        date = entry.get("effective_date") or ""
        year = ""
        m = re.search(r"(19|20)\d{2}", date)
        if m:
            year = m.group(0)
        if year:
            return f"US approval withdrawn in {year}"
        return "Withdrawn from the US market"
    if kind == "trials":
        phases = rec.get("phases") or []
        labels = {
            "PHASE1": "phase 1",
            "PHASE2": "phase 2",
            "PHASE3": "phase 3",
            "PHASE4": "phase 4",
            "EARLY_PHASE1": "early phase 1",
            "NA": "phase listed as NA",
        }
        phase = " / ".join(labels.get(p, p) for p in phases) or "phase not stated"
        n = len(rec.get("countries") or [])
        noun = "country" if n == 1 else "countries"
        if n:
            return f"Recruiting ({esc(phase)}). Sites in {n} {noun}."
        return f"Recruiting ({esc(phase)})."
    if kind == "on-the-edge":
        return "Not an FDA approval"
    # Mainstream: FDA presence is indication-level (the leaf is built from
    # that use on the FDA label) but this snapshot has no complete
    # indication-level FDA approval-date catalog, so the US part names
    # the snapshot label and does not show a year. A drug-level first-
    # approval year on a later indication would be the same bug as a
    # drug-level EMA year. The Europe part is indication-specific: see
    # ema_indications.europe_phrase.
    bits = []
    fda = rec.get("fda") or {}
    if (
        fda.get("dailymedUrl")
        or fda.get("drugsfdaUrl")
        or rec.get("indicationsExcerpt")
        or True  # targeting therapies are on an FDA list in this snapshot
    ):
        bits.append("United States (FDA label in this snapshot)")
    europe = europe_phrase(rec, triple)
    if europe:
        bits.append(europe)
    return "; ".join(bits) if bits else "The snapshot does not give a place or date"


def source_link(kind: str, rec) -> tuple[str, str]:
    """Return (url, label) for the visible source link."""
    if kind == "trials":
        return rec.get("url") or "", "ClinicalTrials.gov"
    if kind == "on-the-edge":
        return rec.get("url") or "", "Public evidence record"
    if kind == "withdrawn":
        entry = rec.get("entry") or {}
        for s in entry.get("sources") or []:
            if s.get("url"):
                return s["url"], s.get("label") or "Withdrawal record"
        return "", "Withdrawal record"
    fda = rec.get("fda") or {}
    if fda.get("dailymedUrl"):
        return fda["dailymedUrl"], "FDA drug label"
    if fda.get("drugsfdaUrl"):
        return fda["drugsfdaUrl"], "Drugs@FDA"
    for e in rec.get("ema") or []:
        if e.get("url"):
            return e["url"], "EMA record"
    for c in rec.get("citations") or []:
        if c.get("url"):
            return c["url"], c.get("source") or "Source"
    return "", "Source in this snapshot"


def raw_sources(kind: str, rec) -> str:
    if kind == "trials":
        countries = rec.get("countries") or []
        loc = ", ".join(sorted(countries)[:12])
        more = f" (+{len(countries)-12} more)" if len(countries) > 12 else ""
        return (
            f'<p class="excerpt">{esc(rec.get("title") or "")}</p>'
            f'<p class="fine">{esc(", ".join(rec.get("conditions") or []))}</p>'
            f'<p class="fine">{esc("; ".join(rec.get("interventions") or []))}</p>'
            f'<p class="fine">Locations: {esc(loc)}{esc(more)}. '
            f'Start: {esc(rec.get("startDate") or "not stated")}.</p>'
            f'<p class="fine"><a href="{esc(rec.get("url") or "")}">ClinicalTrials.gov '
            f'{esc(rec.get("nctId") or "")}</a></p>'
        )
    if kind == "withdrawn":
        t = rec["therapy"]
        entry = rec.get("entry") or {}
        bits = ""
        if t.get("indicationsExcerpt"):
            bits += f'<p class="excerpt">{esc(t["indicationsExcerpt"])}</p>'
        else:
            bits += (
                '<p class="fine">This snapshot has no FDA label excerpt for this drug, '
                "so the tree cannot place a cancer type from the label.</p>"
            )
        bits += "<ul class='cites'>"
        for s in entry.get("sources") or []:
            bits += (
                f'<li><a href="{esc(s.get("url") or "")}">{esc(s.get("label") or "Source")}</a> '
                f'{esc(s.get("date") or "")}. {esc(s.get("detail") or "")}</li>'
            )
        bits += "</ul>"
        return bits
    if kind == "on-the-edge":
        return (
            f'<p class="excerpt">{esc(rec.get("summary") or rec.get("molecularProfile") or "")}</p>'
            f'<p class="fine"><a href="{esc(rec.get("url") or "")}">Public evidence record '
            f'{esc(rec.get("id"))}</a>. Status: {esc(rec.get("status") or "")}.</p>'
        )
    excerpt = rec.get("indicationsExcerpt") or ""
    label_entry = entry_for(rec) or {}
    ema_h = ""
    for e in rec.get("ema") or []:
        name = e.get("name") or e.get("inn") or "EMA"
        st = e.get("status") or ""
        dt = e.get("authorisationDate") or ""
        url = e.get("url") or ""
        label = f"{name} — {st}" + (f", authorised {dt}" if dt else "")
        ema_h += (
            f'<li><a href="{esc(url)}">{esc(label)}</a></li>'
            if url
            else f"<li>{esc(label)}</li>"
        )
    iu = label_entry.get("indications_and_usage") or excerpt
    meta = ""
    if label_entry:
        meta = (
            f'<p class="fine">Committed FDA label snapshot: set id '
            f'{esc(label_entry.get("set_id") or "")}, version {esc(label_entry.get("version") or "")}, '
            f'effective {esc(label_entry.get("effective_time") or "")}, '
            f'retrieved {esc(label_entry.get("retrieval_date") or "")}. '
            f'<a href="{esc(label_entry.get("dailymed_url") or "")}">DailyMed</a> · '
            f'<a href="{esc(label_entry.get("openfda_url") or "")}">openFDA</a>.</p>'
        )
    excerpt_h = (
        f'<p class="excerpt">{esc(iu)}</p>'
        + (meta or (
            '<p class="fine">Excerpt of Indications and Usage from the FDA drug label. '
            "See the official label for the complete, current text.</p>"
        ))
    ) if iu else (meta or "")
    ema_block = f'<ul class="cites">{ema_h}</ul>' if ema_h else ""
    return excerpt_h + ema_block


def table_html(options: list, plain: dict, biomarker_id: str = "", triple: tuple[str, str, str] | None = None) -> str:
    # Group by level, alphabetical within. Level order is fixed, not a ranking.
    order = ["mainstream", "trials", "on-the-edge", "withdrawn"]
    grouped: dict[str, list] = {k: [] for k in order}
    for opt in options:
        grouped.setdefault(opt["kind"], []).append(opt)
    for k in grouped:
        grouped[k].sort(key=lambda o: (o.get("sort_name") or "").lower())

    rows = []
    for kind in order:
        for opt in grouped[kind]:
            rec = opt["record"]
            name, brand = display_name(kind, rec)
            line = line_for(kind, rec, plain)
            what = (line or {}).get("text") or ""
            combo = ""
            therapy_rec = rec
            if kind == "withdrawn" and isinstance(rec, dict) and "therapy" in rec:
                therapy_rec = rec["therapy"]
            if kind == "mainstream":
                what = what_it_is(therapy_rec, biomarker_id)
                # Capitalise for the cell: "A once-daily pill..."
                if what:
                    what = what[0].upper() + what[1:]
                combo = opt.get("combo") or ""
            elif ". " in what:
                # "What it is" is the everyday description. Approval place and
                # date live in their own column, so drop a trailing approval clause.
                first, rest = what.split(". ", 1)
                if rest.lower().startswith("approved") or rest.lower().startswith("authorised"):
                    what = first + "."
                elif ". Authorised" in what or ". Approved" in what:
                    what = what.split(". Authorised")[0].split(". Approved")[0] + "."
            approved = approval_cell(kind, rec, triple=triple)
            url, slabel = source_link(kind, rec)
            if url:
                slink = f'<a href="{esc(url)}">{esc(slabel)}</a>'
            else:
                slink = esc(slabel)
            raw = raw_sources(kind, rec)
            brand_h = f' <span class="brand">({esc(brand)})</span>' if brand else ""
            option_cell = f"<strong>{esc(name)}</strong>{brand_h}"
            if kind == "trials" and (rec.get("title") or ""):
                pass
            combo_h = f'<p class="combo">{esc(combo)}</p>' if combo else ""
            what_h = esc(what) + combo_h
            rows.append(
                "<tr>"
                f'<th scope="row" class="col-option">{option_cell}</th>'
                f'<td class="col-what" data-label="What it is">{what_h}</td>'
                f'<td class="col-level" data-label="Level">{level_tag(kind)}</td>'
                f'<td class="col-approved" data-label="Approved">{esc(approved) if kind != "trials" else approved}</td>'
                f'<td class="col-source" data-label="Source">{slink}{sources_block(raw)}</td>'
                "</tr>"
            )
    if not rows:
        return "<p>No options sit on this branch in this snapshot.</p>"
    counts = []
    for kind in order:
        n = len(grouped[kind])
        if n:
            label = LEVELS[kind][0]
            noun = "option" if n == 1 else "options"
            counts.append(f"{n} {label}")
    count_h = f'<p class="table-counts">{" · ".join(counts)}. Within a level, the rows are alphabetical. That is not a ranking.</p>'
    return (
        count_h
        + '<div class="opt-table-wrap">'
        + '<table class="opt-table">'
        + "<thead><tr>"
        + "<th scope='col'>Option</th>"
        + "<th scope='col'>What it is</th>"
        + "<th scope='col'>Level</th>"
        + "<th scope='col'>Approved where, and since when</th>"
        + "<th scope='col'>Source</th>"
        + "</tr></thead>"
        + "<tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def choice_list(items: list[dict], heading: str, question: str) -> str:
    cards = []
    for it in items:
        unknown = "does not say" in (it["label"] or "")
        cls = "choice unknown" if unknown else "choice"
        n = it["count"]
        noun = "listing" if n == 1 else "listings"
        why = it.get("why") or branch_why(it["label"])
        why_h = f'<span class="choice-why">{esc(why)}</span>' if why else ""
        cards.append(
            f'<li><a class="{cls}" href="{esc(it["href"])}">'
            f'<span class="choice-name">{it["label_html"]}</span>'
            f'{why_h}'
            f'<span class="choice-n">{n} {noun} this way</span>'
            "</a></li>"
        )
    return (
        f"<h1>{esc(heading)}</h1>"
        f'<p class="question">{esc(question)}</p>'
        f'<ul class="choices">{"".join(cards)}</ul>'
    )


def page_shell(title: str, depth: int, snap: dict, body: str, crumbs_h: str, full_notice: bool = False, custom_notice: str | None = None) -> str:
    ct_ts = (snap.get("clinicalTrials") or {}).get("dataTimestamp") or ""
    data_rel = asset_prefix(depth) + "data/snapshot.json"
    notice_rel = asset_prefix(depth) + "notice.html"
    if custom_notice is not None:
        short = custom_notice
        long = ""
    else:
        short = (
            f'<div class="notice notice-short" role="note">'
            f'<strong>{esc(DISCLAIMER_SHORT)}</strong> '
            f'<a href="{esc(notice_rel)}">Full notice</a>.'
            f'</div>'
        )
        long = ""
        if full_notice:
            long = (
                f'<div class="notice notice-full" role="note">'
                f'{esc(DISCLAIMER_LONG)} '
                f'Data is a snapshot as of <time datetime="{esc(snap["snapshotDate"])}">{esc(fmt_date(snap["snapshotDate"]))}</time>. '
                f'ClinicalTrials.gov processed this trial data on <time datetime="{esc(ct_ts)}">{esc(fmt_date(ct_ts))}</time>.'
                f'</div>'
            )
    notice_h = f"""
    {short}
    {long}
    <div class="stale" id="stale-banner" hidden>
      This snapshot is more than eight days old. Figures may be out of date — please check the original FDA, EMA and ClinicalTrials.gov records, and do not rely on this page alone.
    </div>
    <p class="snapshot-meta">Snapshot date: <time id="snapshot-date" datetime="{esc(snap['snapshotDate'])}">{esc(fmt_date(snap['snapshotDate']))}</time></p>
    """
    prefix = asset_prefix(depth)
    mast = f"""
    <header class="mock-head">
      <p class="site-title"><a href="{prefix}index.html">Targeted Therapy Explorer</a></p>
      <nav class="mock-nav" aria-label="Site">
        <a href="{prefix}index.html">Home</a>
        <a href="{prefix}options/index.html">Drug pages</a>
        <a href="{prefix}cases/index.html">Case studies</a>
        <a href="{prefix}about.html">About</a>
      </nav>
    </header>
    """
    return (
        mock_head(title, depth)
        + '<div class="wrap mock-wrap">'
        + mast
        + '<main id="main">'
        + notice_h
        + crumbs_h
        + body
        + "</main>"
        + mock_foot(depth)
    )


def indication_notes_html(therapies: list) -> str:
    items = []
    seen = set()
    for t in therapies:
        for note in indication_notes(t):
            nid = note.get("id")
            if nid in seen:
                continue
            seen.add(nid)
            src = note.get("source") or {}
            url = src.get("url") or ""
            raw = (
                f'<p class="excerpt">{esc(note.get("indication") or "")}</p>'
                f'<p class="fine">{esc(note.get("sure") or "")}</p>'
                f'<p class="fine"><a href="{esc(url)}">{esc(src.get("label") or "Source")}</a> '
                f'{esc(src.get("date") or "")}.</p>'
            )
            name = t.get("name") or ""
            plain = (note.get("plain") or "").strip() or (
                f"A later public record notes that one listed use of {name} "
                "was withdrawn; another approved use remains in this snapshot, "
                "so the drug is still tagged Mainstream. See Sources."
            )
            items.append(
                '<div class="indication-note">'
                f"<p>{esc(plain)}</p>"
                + sources_block(raw, "Sources for this indication note")
                + "</div>"
            )
    return "".join(items)


def withdrawn_banner(withdrawn: list) -> str:
    if not withdrawn:
        return ""
    bits = []
    for rec in withdrawn:
        t = rec["therapy"]
        entry = rec["entry"]
        name = t.get("name") or ""
        brands = ", ".join(_unique_brands(t))
        if not brands and "Exkivity" in (entry.get("names") or []):
            brands = "Exkivity"
        head = f"{name} ({brands})" if brands else name
        year = ""
        m = re.search(r"(19|20)\d{2}", entry.get("effective_date") or "")
        if m:
            year = m.group(0)
        href = f"{slug('label does not say the cancer type')}/{slug((therapy_branch_mut(rec)))}/"
        # We link from EGFR index to the withdrawn branch below, computed by caller.
        bits.append((head, year, rec))
    return bits  # processed by caller


def therapy_branch_mut(rec) -> str:
    return ""


def write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def leaf_count(node) -> int:
    return sum(len(w["options"]) for m in node.get("mutations", node) for w in (m.get("whens") if "whens" in m else [m]))



def _combo_only(clauses: list[str]) -> bool:
    """True when every placing clause is combination-only (no standalone use)."""
    if not clauses:
        return False
    any_combo = False
    for cl in clauses:
        low = (cl or "").lower()
        if "in combination with" in low:
            any_combo = True
            # "as a single agent or in combination" is not combination-only.
            if "as a single agent or in combination" in low or "as monotherapy or in combination" in low:
                return False
        elif "as a single agent" in low or "as monotherapy" in low:
            return False
        else:
            # An indication with no combination wording is a standalone use.
            return False
    return any_combo


def _attach_combos(options: list, triple: tuple[str, str, str]) -> list[str]:
    """Set opt['combo'] from the label; fail if a combo-only drug looks standalone."""
    errors = []
    c, m, w = triple
    for opt in options:
        if opt.get("kind") != "mainstream":
            continue
        rec = opt["record"]
        clauses = leaf_clauses(rec, triple)
        note = combo_note(clauses)
        opt["combo"] = note
        if _combo_only(clauses):
            if "together with" not in (note or "").lower():
                errors.append(
                    f"{rec.get('name')} at {c} / {m} / {w}: combination-only on the "
                    f"label but the row does not say 'used together with' (note={note!r})"
                )
            # A combination partner must not read as a standalone option.
            if note and "used alone" in note.lower() and "or together" not in note.lower():
                errors.append(
                    f"{rec.get('name')} at {c} / {m} / {w}: combination-only but "
                    f"the note implies a standalone use: {note!r}"
                )
    return errors


def write_notice(snap: dict) -> None:
    """One full-notice page, linked from the short banner on every step."""
    body = (
        "<h1>Notice</h1>"
        f"<p>{esc(DISCLAIMER_LONG)}</p>"
        "<p>This site is general information from public FDA, EMA and "
        "ClinicalTrials.gov records in a dated snapshot. It is not a medical "
        "device, and it does not take account of any person’s medical situation.</p>"
        "<p>Talk to your oncologist before making any decision about your care. "
        "Check the original FDA drug label, the EMA record and ClinicalTrials.gov "
        "for the complete, current text.</p>"
        "<p>A Case studies page, kept separate from these decision trees, tells "
        "one person’s published story. A case study is not evidence that a "
        "treatment works, and it is not an option in the tables.</p>"
        f'<p class="fine"><a href="index.html">Back to the home page</a>.</p>'
    )
    write(
        SITE / "notice.html",
        page_shell(
            "Notice — Targeted Therapy Explorer",
            0,
            snap,
            body,
            crumbs([("index.html", "Home"), ("notice.html", "Notice")], 0),
            full_notice=True,
        ),
    )


def _wipe_previous_trees() -> None:
    """Remove leftover long pages and the EGFR-only mockup directory."""
    import shutil

    mock = SITE / "mockup"
    if mock.exists():
        shutil.rmtree(mock)
    if TREE.exists():
        # Drop old one-file biomarker pages and previous trees.
        for p in TREE.glob("*.html"):
            p.unlink()
        for d in TREE.iterdir():
            if d.is_dir():
                shutil.rmtree(d)
    TREE.mkdir(parents=True, exist_ok=True)


def _withdrawn_banner_html(withdrawn: list, tree: list) -> str:
    if not withdrawn:
        return ""
    links = []
    src_h = ""
    for rec in withdrawn:
        t = rec["therapy"]
        entry = rec["entry"]
        name = t.get("name") or ""
        brands = ", ".join(_unique_brands(t))
        if not brands and "Exkivity" in (entry.get("names") or []):
            brands = "Exkivity"
        headn = f"{name} ({brands})" if brands else name
        year = ""
        m = re.search(r"(19|20)\d{2}", entry.get("effective_date") or "")
        if m:
            year = m.group(0)
        href = ""
        for cnode in tree:
            for mnode in cnode["mutations"]:
                for wnode in mnode["whens"]:
                    if any(o["kind"] == "withdrawn" for o in wnode["options"]):
                        href = (
                            f"{slug(cnode['cancer'])}/{slug(mnode['mutation'])}/"
                            f"{slug(wnode['when'])}.html"
                        )
                        break
                if href:
                    break
            if href:
                break
        yr = f", US approval withdrawn in {year}" if year else ""
        if href:
            links.append(
                f'<a href="{esc(href)}">{esc(headn)}</a>{esc(yr)}. '
                "It is not tagged Mainstream."
            )
        else:
            links.append(f"{esc(headn)}{esc(yr)}. It is not tagged Mainstream.")
        for s in entry.get("sources") or []:
            src_h += (
                f'<li><a href="{esc(s.get("url") or "")}">{esc(s.get("label") or "Source")}</a> '
                f'{esc(s.get("date") or "")}. {esc(s.get("detail") or "")}</li>'
            )
    return (
        '<div class="wd-banner">'
        f'<p>{level_tag("withdrawn")} {" ".join(links)}</p>'
        + sources_block(f"<ul class='cites'>{src_h}</ul>", "Sources for this withdrawal")
        + "</div>"
    )


def build_biomarker(snap: dict, bid: str) -> dict:
    """Build one biomarker tree under site/b/<id>/. Returns a report dict."""
    b = next(x for x in snap.get("biomarkers") or [] if x["id"] == bid)
    plain = load_plain(bid)
    therapies = display_mainstream(b)
    withdrawn = withdrawn_therapies(b)
    trials = trial_options(b)
    edge = on_the_edge_assertions(b)
    tree = build_tree(therapies, trials, edge, withdrawn, bid)
    notes = indication_notes_html(therapies)
    intro = plain.get("intro") or {}
    label = BIOMARKER_LABEL.get(bid, bid)

    root = TREE / bid
    root.mkdir(parents=True, exist_ok=True)

    n_leaves = 0
    n_pages = 0
    leaf_report = []
    level_counts = {"mainstream": 0, "trials": 0, "on-the-edge": 0, "withdrawn": 0}

    wd_h = _withdrawn_banner_html(withdrawn, tree)

    cancer_items = []
    for cnode in tree:
        cancer_items.append(
            {
                "label": cnode["cancer"],
                "label_html": inline_def(cnode["cancer"]),
                "count": cnode["count"],
                "href": f"{slug(cnode['cancer'])}/index.html",
            }
        )
    what = intro.get("what") or []
    report = intro.get("test_report") or ""
    what_h = "".join(f'<p class="lede">{esc(s)}</p>' for s in what)
    raw_intro = ""
    for g in (b.get("civic") or {}).get("genes") or []:
        if g.get("description"):
            raw_intro += (
                f'<p class="excerpt">{esc(g["description"])} '
                f'<a href="{esc(g.get("url") or "")}">CIViC gene summary for '
                f'{esc(g.get("name") or "")}</a> (CC0).</p>'
            )
    for a in (b.get("civic") or {}).get("assertions") or []:
        raw_intro += (
            f'<p class="excerpt">CIViC assertion {esc(a.get("id") or "")}: '
            f'{esc(a.get("summary") or "")} '
            f'assertionType={esc(a.get("assertionType") or "")} '
            f'significance={esc(a.get("significance") or "")} '
            f'ampLevel={esc(a.get("ampLevel") or "")} '
            f'status={esc(a.get("status") or "")}. '
            f'<a href="{esc(a.get("url") or "")}">CIViC record</a> (CC0).</p>'
        )
    bm_body = (
        what_h
        + (f'<p class="fine">{esc(report)}</p>' if report else "")
        + sources_block(raw_intro, "Sources for this introduction")
        + wd_h
        + notes
        + choice_list(cancer_items, label, "Which kind of cancer is this about?")
        + level_legend()
        + tree_note()
    )
    write(
        root / "index.html",
        page_shell(
            f"{label} — choose a cancer type",
            2,
            snap,
            bm_body,
            crumbs(
                [
                    ("../../index.html", "Home"),
                    ("../../options/index.html", "Drug pages"),
                    ("index.html", label),
                ],
                2,
            ),
        ),
    )
    n_pages += 1

    for cnode in tree:
        cslug = slug(cnode["cancer"])
        cdir = root / cslug
        mut_items = []
        for mnode in cnode["mutations"]:
            mut_items.append(
                {
                    "label": mnode["mutation"],
                    "label_html": inline_def(mnode["mutation"]),
                    "count": mnode["count"],
                    "href": f"{slug(mnode['mutation'])}/index.html",
                }
            )
        mut_body = (
            choice_list(
                mut_items,
                title_case_cancer(cnode["cancer"]),
                "Which gene change does the test or the label name?",
            )
            + '<p class="fine">If the label does not distinguish a subtype, that is said plainly.</p>'
            + level_legend()
            + tree_note()
        )
        write(
            cdir / "index.html",
            page_shell(
                f"{title_case_cancer(cnode['cancer'])} — {label}",
                3,
                snap,
                mut_body,
                crumbs(
                    [
                        ("../../../index.html", "Home"),
                        ("../../../options/index.html", "Drug pages"),
                        ("../index.html", label),
                        ("index.html", title_case_cancer(cnode["cancer"])),
                    ],
                    3,
                ),
            ),
        )
        n_pages += 1

        for mnode in cnode["mutations"]:
            mslug = slug(mnode["mutation"])
            mdir = cdir / mslug
            when_items = []
            for wnode in mnode["whens"]:
                when_items.append(
                    {
                        "label": wnode["when"],
                        "label_html": esc(wnode["when"]),
                        "count": wnode["count"],
                        "href": f"{slug(wnode['when'])}.html",
                    }
                )
            when_body = (
                f"<p class='context'>{inline_def(mnode['mutation'])}</p>"
                + choice_list(
                    when_items,
                    title_case_cancer(cnode["cancer"]),
                    "When is this used, according to the label or the trial record?",
                )
                + level_legend()
                + tree_note()
            )
            write(
                mdir / "index.html",
                page_shell(
                    f"{mnode['mutation']} — {label}",
                    4,
                    snap,
                    when_body,
                    crumbs(
                        [
                            ("../../../../index.html", "Home"),
                            ("../../../../options/index.html", "Drug pages"),
                            ("../../index.html", label),
                            ("../index.html", title_case_cancer(cnode["cancer"])),
                            ("index.html", mnode["mutation"]),
                        ],
                        4,
                    ),
                ),
            )
            n_pages += 1

            for wnode in mnode["whens"]:
                n_leaves += 1
                wslug = slug(wnode["when"])
                kinds = {}
                for o in wnode["options"]:
                    kinds[o["kind"]] = kinds.get(o["kind"], 0) + 1
                    if o["kind"] in level_counts:
                        level_counts[o["kind"]] += 1
                leaf_report.append(
                    {
                        "biomarker": bid,
                        "cancer": cnode["cancer"],
                        "mutation": mnode["mutation"],
                        "when": wnode["when"],
                        "counts": {LEVELS[k][0]: n for k, n in kinds.items()},
                        "n": wnode["count"],
                        "path": f"b/{bid}/{cslug}/{mslug}/{wslug}.html",
                    }
                )
                combo_errors = _attach_combos(
                    wnode["options"],
                    (cnode["cancer"], mnode["mutation"], wnode["when"]),
                )
                if combo_errors:
                    raise SystemExit(
                        "Combination gate failed:\n" + "\n".join(combo_errors)
                    )
                table = table_html(
                    wnode["options"],
                    plain,
                    bid,
                    triple=(cnode["cancer"], mnode["mutation"], wnode["when"]),
                )
                leaf_notes = indication_notes_html(
                    [
                        o["record"]
                        for o in wnode["options"]
                        if o["kind"] == "mainstream"
                    ]
                )
                leaf_body = (
                    f"<h1>Options</h1>"
                    f'<p class="path-plain">{esc(label)} · {esc(title_case_cancer(cnode["cancer"]))} · '
                    f'{inline_def(mnode["mutation"])} · {esc(wnode["when"])}.</p>'
                    f"{leaf_notes}"
                    f"{table}"
                    + level_legend()
                    + tree_note()
                    + '<p class="fine"><a href="index.html">Change when it is used</a> · '
                    f'<a href="../index.html">Change the gene change</a> · '
                    f'<a href="../../index.html">Change the cancer type</a></p>'
                )
                write(
                    mdir / f"{wslug}.html",
                    page_shell(
                        f"Options — {wnode['when']} — {label}",
                        4,
                        snap,
                        leaf_body,
                        crumbs(
                            [
                                ("../../../../index.html", "Home"),
                            ("../../../../options/index.html", "Drug pages"),
                                ("../../index.html", label),
                                ("../index.html", title_case_cancer(cnode["cancer"])),
                                ("index.html", mnode["mutation"]),
                                (f"{wslug}.html", wnode["when"]),
                            ],
                            4,
                        ),
                        full_notice=True,
                    ),
                )
                n_pages += 1

    # Count unique branches (cancer + mutation + when choice pages, not leaves)
    n_cancers = len(tree)
    n_mutations = sum(len(c["mutations"]) for c in tree)
    n_whens = sum(len(m["whens"]) for c in tree for m in c["mutations"])
    return {
        "id": bid,
        "pages": n_pages,
        "leaves": n_leaves,
        "cancers": n_cancers,
        "mutation_branches": n_mutations,
        "when_branches": n_whens,
        "branches": n_cancers + n_mutations + n_whens,
        "mainstream": len(therapies),
        "withdrawn": len(withdrawn),
        "trials": len(trials),
        "edge": len(edge),
        "level_counts": level_counts,
        "leaf_report": leaf_report,
    }


def write_home(snap: dict) -> None:
    """Write the decision-tree start at options/index.html, not the site front door."""
    cards = []
    for label, ready, bid in CLOSED_LIST:
        cards.append(
            f'<li><a class="choice bm-ready" href="../b/{esc(bid)}/index.html">'
            f'<span class="choice-name">{esc(label)}</span>'
            f'<span class="choice-n">Open the decision tree</span>'
            "</a></li>"
        )
    home_body = (
        "<h1>Choose a gene finding</h1>"
        '<p class="lede">These drug pages map a short list of tumour gene findings to approved '
        "drugs and recruiting studies, from public sources only. It is general information. "
        "It is not medical advice, a diagnosis or a treatment recommendation. "
        "They are linked from the "
        '<a href="../index.html#step-matching">matching to options or trials</a> '
        "step on the home page.</p>"
        '<p class="lede">Pick a gene finding. You will walk a decision tree: cancer type, '
        "then the gene change, then when a drug is used. At the end you will see one table "
        "of options, tagged Mainstream, In testing, or On the edge.</p>"
        '<p class="lede">A separate <a href="../cases/index.html">Case studies</a> page tells '
        "one person’s published story. A case study is not evidence that a treatment works, "
        "and it is not an option in the tables.</p>"
        f'<ul class="choices home-choices">{"".join(cards)}</ul>'
        + level_legend()
        + tree_note()
    )
    write(
        SITE / "options" / "index.html",
        page_shell(
            "Choose a gene finding — Targeted Therapy Explorer",
            1,
            snap,
            home_body,
            crumbs([("../index.html", "Home"), ("index.html", "Drug pages")], 1),
            full_notice=True,
        ),
    )


def build(snap: dict) -> dict:
    """Build the decision-tree site for every biomarker. Returns a report."""
    _wipe_previous_trees()
    write_notice(snap)
    from build_steps import write_steps
    write_steps(snap)
    write_home(snap)

    reports = {}
    all_leaves = []
    n_pages = 3  # steps + options + notice
    n_leaves = 0
    for _label, _ready, bid in CLOSED_LIST:
        rep = build_biomarker(snap, bid)
        reports[bid] = {k: v for k, v in rep.items() if k != "leaf_report"}
        all_leaves.extend(rep["leaf_report"])
        n_pages += rep["pages"]
        n_leaves += rep["leaves"]
        print(
            f"  {bid}: {rep['pages']} pages, {rep['leaves']} leaves, "
            f"{rep['cancers']} cancer branches, "
            f"mainstream listings {rep['level_counts']['mainstream']}, "
            f"in testing {rep['level_counts']['trials']}, "
            f"on the edge {rep['level_counts']['on-the-edge']}."
        )

    from build_cases import build as build_case_pages
    case_rep = build_case_pages(snap)
    n_pages += case_rep["pages"]

    return {
        "pages": n_pages,
        "leaves": n_leaves,
        "biomarkers": reports,
        "leaf_report": all_leaves,
        "cases": case_rep,
    }


def main() -> int:
    import json

    snap = json.loads((ROOT / "data" / "snapshot.json").read_text(encoding="utf-8"))
    report = build(snap)
    print(
        f"Wrote decision-tree site to {SITE.relative_to(ROOT)}: "
        f"{report['pages']} pages, {report['leaves']} leaves, "
        f"{len(report['biomarkers'])} biomarkers."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
