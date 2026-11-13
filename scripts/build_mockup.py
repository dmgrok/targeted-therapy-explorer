#!/usr/bin/env python3
"""EGFR-only clickable mockup: home → gene → cancer → mutation → when → table.

Built from the same snapshot, plain-language lines, decision-tree rules
and withdrawal catalog as the rest of the repo. Other biomarkers are
listed on the mockup home but are not built — David asked to judge the
shape on EGFR first.

Pages are static HTML with relative links. No JavaScript is required.
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
from generate_plain import _ema_year, _unique_brands  # noqa: E402
from plain import load_plain, line_by_id  # noqa: E402
from tree import (  # noqa: E402
    TREE_HOW,
    build_tree,
)
from withdrawn import (  # noqa: E402
    display_mainstream,
    indication_notes,
    withdrawn_therapies,
)

OUT = ROOT / "site" / "mockup"
BIOMARKER_ID = "EGFR"

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
    "EGFR mutations the label calls non-resistant": "EGFR gene changes the label lists as non-resistant",
    "EGFR mutation (subtype not further named)": "an EGFR gene change, without a more precise subtype in the text",
    "KRAS wild-type (no KRAS change)": "the KRAS gene has no change at the places the label names",
    "HER2 mutation": "a change in the HER2 gene itself",
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
    ("ALK", False, "ALK"),
    ("BRAF V600E", False, "BRAF-V600E"),
    ("KRAS G12C", False, "KRAS-G12C"),
    ("HER2", False, "HER2"),
    ("NTRK", False, "NTRK"),
    ("MSI-H / dMMR", False, "MSI-H-dMMR"),
]


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
  <meta name="description" content="EGFR mockup of a decision-tree explorer. {DISCLAIMER_SHORT}">
  <meta name="robots" content="noindex,follow">
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
      <p class="fine">{esc(DISCLAIMER_SHORT)} This mockup uses only public sources. It does not recommend a treatment.</p>
      <p class="fine"><a href="{prefix}about.html">About and sources</a>
      · <a href="https://github.com/dmgrok/targeted-therapy-explorer">Source code</a>
      · <a href="{prefix}index.html">Current site (earlier design)</a></p>
    </footer>
  </div>
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


def approval_cell(kind: str, rec) -> str:
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
    # Mainstream: FDA label in the snapshot; Europe year if EMA authorised.
    bits = []
    fda = rec.get("fda") or {}
    if (
        fda.get("dailymedUrl")
        or fda.get("drugsfdaUrl")
        or rec.get("indicationsExcerpt")
        or True  # targeting therapies are on an FDA list in this snapshot
    ):
        bits.append("United States (FDA label in this snapshot)")
    _name, year = _ema_year(rec)
    if year:
        bits.append(f"Europe since {year}")
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
    excerpt_h = (
        f'<p class="excerpt">{esc(excerpt)}</p>'
        '<p class="fine">Excerpt of Indications and Usage from the FDA drug label. '
        "See the official label for the complete, current text.</p>"
    ) if excerpt else ""
    ema_block = f'<ul class="cites">{ema_h}</ul>' if ema_h else ""
    return excerpt_h + ema_block


def table_html(options: list, plain: dict) -> str:
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
            # "What it is" is the everyday description. Approval place and
            # date live in their own column, so drop a trailing approval clause.
            if ". " in what:
                first, rest = what.split(". ", 1)
                if rest.lower().startswith("approved") or rest.lower().startswith("authorised"):
                    what = first + "."
                elif ". Authorised" in what or ". Approved" in what:
                    what = what.split(". Authorised")[0].split(". Approved")[0] + "."
            approved = approval_cell(kind, rec)
            url, slabel = source_link(kind, rec)
            if url:
                slink = f'<a href="{esc(url)}">{esc(slabel)}</a>'
            else:
                slink = esc(slabel)
            raw = raw_sources(kind, rec)
            brand_h = f' <span class="brand">({esc(brand)})</span>' if brand else ""
            option_cell = f"<strong>{esc(name)}</strong>{brand_h}"
            if kind == "trials" and (rec.get("title") or ""):
                # Visible trial title stays short — the plain line already is.
                pass
            rows.append(
                "<tr>"
                f'<th scope="row" class="col-option">{option_cell}</th>'
                f'<td class="col-what" data-label="What it is">{esc(what)}</td>'
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
        cards.append(
            f'<li><a class="{cls}" href="{esc(it["href"])}">'
            f'<span class="choice-name">{it["label_html"]}</span>'
            f'<span class="choice-n">{n} {noun} this way</span>'
            "</a></li>"
        )
    return (
        f"<h1>{esc(heading)}</h1>"
        f'<p class="question">{esc(question)}</p>'
        f'<ul class="choices">{"".join(cards)}</ul>'
    )


def page_shell(title: str, depth: int, snap: dict, body: str, crumbs_h: str) -> str:
    ct_ts = (snap.get("clinicalTrials") or {}).get("dataTimestamp") or ""
    # notice() uses root= to pick data path; mockup is under site/mockup/...
    # Data file: from mockup/index (depth 1) → ../data; from deeper, still site-relative.
    # The published site copies data to site/data. notice(root=False) uses ../data/snapshot.json
    # which is correct from site/b/ but from site/mockup/EGFR/lung/... need more ..
    # We'll write our own short notice using the same wording, with a correct relative data link.
    data_rel = asset_prefix(depth) + "data/snapshot.json"
    notice_h = f"""
    <div class="notice" role="note">
      <strong>{esc(DISCLAIMER_SHORT)}</strong>
      {esc(DISCLAIMER_LONG)}
      Data is a snapshot as of <time datetime="{esc(snap['snapshotDate'])}">{esc(fmt_date(snap['snapshotDate']))}</time>.
      ClinicalTrials.gov processed this trial data on <time datetime="{esc(ct_ts)}">{esc(fmt_date(ct_ts))}</time>.
    </div>
    <div class="stale" id="stale-banner" hidden>
      This snapshot is more than eight days old. Figures may be out of date — please check the original FDA, EMA and ClinicalTrials.gov records, and do not rely on this page alone.
    </div>
    <p class="snapshot-meta">Snapshot date: <time id="snapshot-date" datetime="{esc(snap['snapshotDate'])}">{esc(fmt_date(snap['snapshotDate']))}</time>
    · Mockup of a new page design, EGFR only.</p>
    """
    prefix = asset_prefix(depth)
    mast = f"""
    <header class="mock-head">
      <p class="site-title"><a href="{prefix}mockup/index.html">Targeted Therapy Explorer</a></p>
      <p class="mock-flag">Design mockup</p>
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
            items.append(
                '<div class="indication-note">'
                '<p>A later public record notes that one listed use of '
                f'{esc(t.get("name") or "")} was withdrawn; another approved use remains '
                "in this snapshot, so the drug is still tagged Mainstream. See Sources.</p>"
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


def build(snap: dict) -> dict:
    """Build the EGFR mockup. Returns a report dict."""
    b = next(x for x in snap.get("biomarkers") or [] if x["id"] == BIOMARKER_ID)
    plain = load_plain(BIOMARKER_ID)
    therapies = display_mainstream(b)
    withdrawn = withdrawn_therapies(b)
    trials = trial_options(b)
    edge = on_the_edge_assertions(b)
    tree = build_tree(therapies, trials, edge, withdrawn, BIOMARKER_ID)
    notes = indication_notes_html(therapies)

    # Wipe previous mockup pages (keep directory).
    if OUT.exists():
        for p in OUT.rglob("*.html"):
            p.unlink()
    OUT.mkdir(parents=True, exist_ok=True)

    n_leaves = 0
    n_pages = 0
    leaf_report = []

    # --- Home ---
    cards = []
    for label, ready, bid in CLOSED_LIST:
        if ready:
            cards.append(
                f'<li><a class="choice bm-ready" href="EGFR/index.html">'
                f'<span class="choice-name">{esc(label)}</span>'
                f'<span class="choice-n">Open the decision tree</span>'
                "</a></li>"
            )
        else:
            cards.append(
                f'<li><span class="choice bm-later">'
                f'<span class="choice-name">{esc(label)}</span>'
                f'<span class="choice-n">Not in this mockup yet</span>'
                "</span></li>"
            )
    intro = plain.get("intro") or {}
    # Home uses short site intro, not the EGFR intro.
    home_body = (
        "<h1>Choose a gene finding</h1>"
        '<p class="lede">This site maps a short list of tumour gene findings to approved '
        "drugs and recruiting studies, from public sources only. It is general information. "
        "It is not medical advice, a diagnosis or a treatment recommendation.</p>"
        '<p class="lede">Pick a gene finding. You will walk a decision tree: cancer type, '
        "then the gene change, then when a drug is used. At the end you will see one table "
        "of options, tagged Mainstream, In testing, or On the edge.</p>"
        '<p class="mock-note">This is a design mockup of the new page shape, built from '
        "the real public snapshot, for EGFR only. The other six gene findings will be "
        "built the same way once this shape is judged.</p>"
        f'<ul class="choices home-choices">{"".join(cards)}</ul>'
        + level_legend()
        + tree_note()
    )
    write(
        OUT / "index.html",
        page_shell(
            "Choose a gene finding — Targeted Therapy Explorer (mockup)",
            1,
            snap,
            home_body,
            crumbs([("index.html", "Home")], 1),
        ),
    )
    n_pages += 1

    # --- EGFR cancer list ---
    # Withdrawal banner with a link into the actual branch.
    wd_h = ""
    if withdrawn:
        links = []
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
            # Find its first leaf path.
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
            links.append(
                f'<a href="{esc(href)}">{esc(headn)}</a>{esc(yr)}. '
                "It is not tagged Mainstream. This snapshot has no FDA label excerpt "
                "for it, so the tree places it under “label does not say the cancer type”."
            )
        src_h = ""
        for rec in withdrawn:
            for s in rec["entry"].get("sources") or []:
                src_h += (
                    f'<li><a href="{esc(s.get("url") or "")}">{esc(s.get("label") or "Source")}</a> '
                    f'{esc(s.get("date") or "")}. {esc(s.get("detail") or "")}</li>'
                )
        wd_h = (
            '<div class="wd-banner">'
            f'<p>{level_tag("withdrawn")} {"".join(links)}</p>'
            + sources_block(f"<ul class='cites'>{src_h}</ul>", "Sources for this withdrawal")
            + "</div>"
        )

    cancer_items = []
    for cnode in tree:
        cancer_items.append(
            {
                "label": cnode["cancer"],
                "label_html": inline_def(cnode["cancer"]),
                "count": cnode["count"],
                "href": f"{slug(cnode['cancer'])}.html"
                if False
                else f"{slug(cnode['cancer'])}/index.html",
            }
        )
    # Use EGFR/lung-cancer/index.html for mutation lists
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
    # Raw CIViC in Sources only.
    raw_intro = ""
    for g in (b.get("civic") or {}).get("genes") or []:
        if g.get("description"):
            raw_intro += (
                f'<p class="excerpt">{esc(g["description"])} '
                f'<a href="{esc(g.get("url") or "")}">CIViC gene summary for '
                f'{esc(g.get("name") or "")}</a> (CC0).</p>'
            )
    egfr_body = (
        what_h
        + f'<p class="fine">{esc(report)}</p>'
        + sources_block(raw_intro, "Sources for this introduction")
        + wd_h
        + notes
        + choice_list(cancer_items, "EGFR", "Which kind of cancer is this about?")
        + level_legend()
        + tree_note()
    )
    write(
        OUT / "EGFR" / "index.html",
        page_shell(
            "EGFR — choose a cancer type (mockup)",
            2,
            snap,
            egfr_body,
            crumbs(
                [
                    ("../index.html", "Home"),
                    ("index.html", "EGFR"),
                ],
                2,
            ),
        ),
    )
    n_pages += 1

    # --- Mutation lists, when lists, leaf tables ---
    for cnode in tree:
        cslug = slug(cnode["cancer"])
        cdir = OUT / "EGFR" / cslug
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
                f"{title_case_cancer(cnode['cancer'])} — EGFR mockup",
                3,
                snap,
                mut_body,
                crumbs(
                    [
                        ("../../index.html", "Home"),
                        ("../index.html", "EGFR"),
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
                    f"{mnode['mutation']} — EGFR mockup",
                    4,
                    snap,
                    when_body,
                    crumbs(
                        [
                            ("../../../index.html", "Home"),
                            ("../../index.html", "EGFR"),
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
                leaf_report.append(
                    {
                        "cancer": cnode["cancer"],
                        "mutation": mnode["mutation"],
                        "when": wnode["when"],
                        "counts": {LEVELS[k][0]: n for k, n in kinds.items()},
                        "n": wnode["count"],
                        "path": f"EGFR/{cslug}/{mslug}/{wslug}.html",
                    }
                )
                table = table_html(wnode["options"], plain)
                # Indication notes if a named mainstream drug on this leaf has one.
                leaf_notes = indication_notes_html(
                    [
                        o["record"]
                        for o in wnode["options"]
                        if o["kind"] == "mainstream"
                    ]
                )
                leaf_body = (
                    f"<h1>Options</h1>"
                    f'<p class="path-plain">EGFR · {esc(title_case_cancer(cnode["cancer"]))} · '
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
                        f"Options — {wnode['when']} — EGFR mockup",
                        4,
                        snap,
                        leaf_body,
                        crumbs(
                            [
                                ("../../../index.html", "Home"),
                                ("../../index.html", "EGFR"),
                                ("../index.html", title_case_cancer(cnode["cancer"])),
                                ("index.html", mnode["mutation"]),
                                (f"{wslug}.html", wnode["when"]),
                            ],
                            4,
                        ),
                    ),
                )
                n_pages += 1

    report = {
        "pages": n_pages,
        "leaves": n_leaves,
        "cancers": len(tree),
        "mainstream": len(therapies),
        "withdrawn": len(withdrawn),
        "trials": len(trials),
        "edge": len(edge),
        "leaf_report": leaf_report,
    }
    return report


def main() -> int:
    import json

    snap = json.loads((ROOT / "data" / "snapshot.json").read_text(encoding="utf-8"))
    report = build(snap)
    print(
        f"Wrote EGFR mockup to {OUT.relative_to(ROOT)}: "
        f"{report['pages']} pages, {report['leaves']} leaves, "
        f"{report['cancers']} cancer branches, "
        f"{report['mainstream']} mainstream, {report['trials']} in testing, "
        f"{report['edge']} on the edge, {report['withdrawn']} withdrawn."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
