#!/usr/bin/env python3
"""Render the static site from data/snapshot.json into site/."""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "snapshot.json"
SITE = ROOT / "site"

# Shared matching: pages show only therapies that target the biomarker.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from matching import targeting_therapies  # noqa: E402
from trial_matching import requiring_trials  # noqa: E402

DISCLAIMER_SHORT = "Not medical advice. Talk to your oncologist."
DISCLAIMER_LONG = (
    "This site is general information only. It is not medical advice, a diagnosis "
    "or a treatment recommendation, and it is not a medical device. It does not "
    "take account of any person’s medical situation. Talk to your oncologist before "
    "making any decision about your care."
)

def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)

def fmt_date(iso: str) -> str:
    if not iso:
        return ""
    # 2026-11-12 or 2026-11-12T...
    day = iso[:10]
    try:
        d = datetime.strptime(day, "%Y-%m-%d")
        return d.strftime("%-d %B %Y")
    except ValueError:
        return iso

def notice(snapshot_date: str, ct_ts: str = "", root: bool = True) -> str:
    data_file = "data/snapshot.json" if root else "../data/snapshot.json"
    # data is in repo data/, also copy into site/data/
    data_file = "data/snapshot.json" if root else "../data/snapshot.json"
    ct = (
        f' ClinicalTrials.gov processed this trial data on <time datetime="{esc(ct_ts)}">{esc(fmt_date(ct_ts))}</time>.'
        if ct_ts else ""
    )
    return f'''
    <div class="notice" role="note">
      <strong>{esc(DISCLAIMER_SHORT)}</strong>
      {esc(DISCLAIMER_LONG)}
      Data is a snapshot as of <time datetime="{esc(snapshot_date)}">{esc(fmt_date(snapshot_date))}</time>.{ct}
    </div>
    <div class="stale" id="stale-banner" hidden>
      This snapshot is more than eight days old. Figures may be out of date — please check the original FDA, EMA and ClinicalTrials.gov records, and do not rely on this page alone.
    </div>
    <p class="snapshot-meta">Snapshot date: <time id="snapshot-date" datetime="{esc(snapshot_date)}">{esc(fmt_date(snapshot_date))}</time></p>
    '''

def masthead(snap: dict, page: str, root: bool = True) -> str:
    prefix = "" if root else "../"
    def cur(name):
        return ' aria-current="page"' if page == name else ""
    title = "Targeted Therapy Explorer"
    h = "h1" if page == "home" else "p"
    title_html = (
        f'<{h} class="site-title"><a href="{prefix}index.html">{esc(title)}</a></{h}>'
        if page != "home"
        else f'<h1 class="site-title"><a href="{prefix}index.html">{esc(title)}</a></h1>'
    )
    return f'''
    <a class="skip" href="#main">Skip to content</a>
    <header class="masthead">
      <p class="kicker">A watch-and-explain gazette · not a medical device</p>
      {title_html}
      <p class="issue"><span class="label">Snapshot</span>{esc(fmt_date(snap["snapshotDate"]))}</p>
      <p class="standfirst">A plain-language map of approved targeted therapies and recruiting trials, organised by biomarker, from public regulatory and trial registers.</p>
    </header>
    <nav class="sections" aria-label="Sections">
      <a href="{prefix}index.html"{cur("home")}>Biomarkers</a>
      <a href="{prefix}index.html#whats-new"{cur("")}>What’s new</a>
      <a href="{prefix}about.html"{cur("about")}>About &amp; sources</a>
    </nav>
    '''

def footer(snap: dict, root: bool = True) -> str:
    prefix = "" if root else "../"
    return f'''
    <footer>
      <div class="notice" role="note">
        <strong>{esc(DISCLAIMER_SHORT)}</strong>
        {esc(DISCLAIMER_LONG)}
        Data is a snapshot as of <time datetime="{esc(snap["snapshotDate"])}">{esc(fmt_date(snap["snapshotDate"]))}</time>.
      </div>
      <nav aria-label="Footer">
        <a href="{prefix}index.html">Home</a>
        <a href="{prefix}about.html">About &amp; sources</a>
        <a href="https://github.com/dmgrok/targeted-therapy-explorer">Source code</a>
      </nav>
      <p class="fine">Code is MIT-licensed. Each data source remains under its own terms — see <a href="{prefix}about.html">About &amp; sources</a>. No cookies, no accounts, no analytics, no patient uploads.</p>
    </footer>
    <script src="{prefix}assets/js/app.js" defer></script>
    '''

def head(title: str, root: bool = True, extra: str = "") -> str:
    prefix = "" if root else "../"
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Watch-and-explain explorer of approved targeted cancer therapies and recruiting trials, by biomarker. {DISCLAIMER_SHORT}">
  <meta name="robots" content="index,follow">
  <title>{esc(title)}</title>
  <link rel="stylesheet" href="{prefix}assets/css/style.css">
  {extra}
</head>
<body>
'''

def cites_html(citations: list) -> str:
    if not citations:
        return '<p class="fine">No citation recorded — this row should not have been published.</p>'
    items = []
    for c in citations:
        url = c.get("url") or ""
        src = c.get("source") or "Source"
        detail = c.get("detail") or ""
        link = f'<a href="{esc(url)}">{esc(src)}</a>' if url else esc(src)
        items.append(f'<li><span class="src">{link}</span> {esc(detail)}</li>')
    return '<ul class="cites">' + "".join(items) + "</ul>"

def therapy_html(t: dict) -> str:
    brands = ", ".join(t.get("brandNames") or [])
    brand = f' <span class="brand">({esc(brands)})</span>' if brands else ""
    excerpt = t.get("indicationsExcerpt") or ""
    excerpt_h = (
        f'<p class="excerpt">{esc(excerpt)}</p>'
        '<p class="fine">Excerpt of Indications and Usage from the FDA drug label '
        "(openFDA / DailyMed). See the official label for the complete, current text.</p>"
    ) if excerpt else ""
    ema = t.get("ema") or []
    ema_h = ""
    if ema:
        bits = []
        for e in ema:
            name = e.get("name") or e.get("inn") or "EMA record"
            url = e.get("url") or ""
            st = e.get("status") or ""
            dt = e.get("authorisationDate") or ""
            label = f"{name}" + (f" — {st}" if st else "") + (f", authorised {dt}" if dt else "")
            if url:
                bits.append(f'<a href="{esc(url)}">{esc(label)}</a>')
            else:
                bits.append(esc(label))
        ema_h = "<p class='fine'>EMA: " + "; ".join(bits) + "</p>"
    cdx = t.get("companionDiagnostics") or []
    cdx_h = ""
    if cdx:
        cdx_h = "<p class='fine'>Companion diagnostic (FDA): " + "; ".join(
            esc(c.get("diagnostic") or "") for c in cdx[:3]
        ) + "</p>"
    return f'''
    <article class="item" id="{esc((t.get("name") or "").lower().replace(" ","-"))}">
      <h3>{esc(t.get("name") or "Therapy")}{brand}</h3>
      {excerpt_h}
      {ema_h}
      {cdx_h}
      {cites_html(t.get("citations") or [])}
    </article>
    '''

def trial_html(t: dict) -> str:
    countries = t.get("countries") or []
    attr = " ".join(countries)
    phases = ", ".join(t.get("phases") or []) or "Phase not stated"
    cond = ", ".join(t.get("conditions") or [])
    iv = "; ".join(t.get("interventions") or [])
    loc_preview = ", ".join(sorted(countries)[:12])
    more = f" (+{len(countries)-12} more)" if len(countries) > 12 else ""
    return f'''
    <article class="item trial" data-countries="{esc(attr)}" data-nct="{esc(t.get("nctId") or "")}">
      <h3><a href="{esc(t.get("url") or "")}">{esc(t.get("nctId") or "")}</a>: {esc(t.get("title") or "")}</h3>
      <p class="fine">
        <span class="badge">{esc(t.get("status") or "Recruiting")}</span>
        <span class="badge">{esc(phases)}</span>
      </p>
      <p class="excerpt">{esc(cond)}</p>
      <p class="fine">{esc(iv)}</p>
      <p class="fine">Locations: {esc(loc_preview)}{esc(more)}</p>
      <ul class="cites"><li><span class="src"><a href="{esc(t.get("url") or "")}">ClinicalTrials.gov</a></span> Record {esc(t.get("nctId") or "")}.</li></ul>
    </article>
    '''

def literature_html(cards: list) -> str:
    if not cards:
        return "<p class='fine'>No PubMed citation cards in this snapshot.</p>"
    out = ['<div class="cards">']
    for c in cards:
        out.append(f'''
        <article class="card">
          <p><a href="{esc(c.get("url") or "")}">{esc(c.get("title") or "")}</a></p>
          <p class="fine">{esc(c.get("authors") or "")} <em>{esc(c.get("journal") or "")}</em>, {esc(c.get("date") or "")}. PMID {esc(c.get("pmid") or "")}.</p>
        </article>''')
    out.append("</div>")
    return "".join(out)

def civic_html(civic: dict) -> str:
    genes = civic.get("genes") or []
    assertions = civic.get("assertions") or []
    parts = []
    for g in genes:
        if g.get("description"):
            parts.append(
                f'<p>{esc(g["description"])} <a href="{esc(g.get("url") or "")}">CIViC gene summary for {esc(g.get("name") or "")}</a> (CC0).</p>'
            )
    if assertions:
        parts.append("<div class='cards'>")
        for a in assertions[:15]:
            th = ", ".join(a.get("therapies") or [])
            bits = " · ".join(filter(None, [a.get("significance"), a.get("ampLevel"), a.get("disease"), th]))
            parts.append(f'''
            <article class="card">
              <p>{esc(a.get("summary") or a.get("molecularProfile") or "CIViC assertion")}</p>
              <p class="fine">{esc(bits)} — <a href="{esc(a.get("url") or "")}">CIViC assertion {esc(a.get("id"))}</a> (CC0).</p>
            </article>''')
        parts.append("</div>")
    if not assertions:
        parts.append("<p>No curated assertions yet.</p>")
    if not parts:
        return "<p>No curated assertions yet.</p>"
    return "".join(parts)

def country_options(trials: list) -> str:
    countries = sorted({c for t in trials for c in (t.get("countries") or []) if c})
    preferred = ["France", "Switzerland"]
    rest = [c for c in countries if c not in preferred]
    opts = ['<option value="all" selected>All countries</option>']
    for c in preferred:
        n = sum(1 for t in trials if c in (t.get("countries") or []))
        opts.append(f'<option value="{esc(c)}">{esc(c)} ({n})</option>')
    for c in rest:
        n = sum(1 for t in trials if c in (t.get("countries") or []))
        opts.append(f'<option value="{esc(c)}">{esc(c)} ({n})</option>')
    return "\n".join(opts)

def page_biomarker(snap: dict, b: dict) -> str:
    ct_ts = (snap.get("clinicalTrials") or {}).get("dataTimestamp") or ""
    therapies = targeting_therapies(b)
    trials = requiring_trials(b)
    fr = sum(1 for t in trials if "France" in (t.get("countries") or []))
    ch = sum(1 for t in trials if "Switzerland" in (t.get("countries") or []))
    th_h = "".join(therapy_html(t) for t in therapies) or "<p>No therapies in this snapshot have a label indication, FDA pharmacogenomic row or companion-diagnostic row that ties the drug to this biomarker as a selection criterion.</p>"
    tr_h = "".join(trial_html(t) for t in trials)
    summary_cites = cites_html(b.get("summarySources") or [])
    return (
        head(f"{b['name']} — Targeted Therapy Explorer", root=False)
        + '<div class="wrap">'
        + masthead(snap, "bm", root=False)
        + f'<main id="main">'
        + notice(snap["snapshotDate"], ct_ts, root=False)
        + f'<h2>{esc(b["name"])}</h2>'
        + f'<p class="lede">{esc(b.get("fullName") or "")}</p>'
        + f'<div class="prose"><p>{esc(b.get("summary") or "")}</p>{summary_cites}</div>'
        + f'<h2 id="therapies">Approved therapies</h2>'
        + f'<p class="fine">{len(therapies)} approved therapies whose label indication, the FDA pharmacogenomic biomarker table, or an FDA companion-diagnostic row ties the drug to this biomarker as a selection criterion, with EMA matches where found. Mentions that are only incidental, or that use the biomarker as an exclusion or opposite-status criterion (for example “no EGFR or ALK aberrations”, or a HER2-negative indication), are kept in the snapshot data and are not shown here. Excerpts are not a substitute for the official label.</p>'
        + th_h
        + f'<h2 id="trials">Recruiting trials</h2>'
        + f'<p class="fine">{len(trials)} recruiting studies from ClinicalTrials.gov whose condition or eligibility inclusion criteria require this biomarker as a selection criterion, including {fr} with a site in France and {ch} with a site in Switzerland. A mention only in exclusions, interventions or keywords is not enough; those records stay in the snapshot data and are not shown. Filter is applied on this page only; nothing is sent anywhere.</p>'
        + f'''<div class="filter-bar">
          <label for="country-filter">Country
            <select id="country-filter" name="country">
              {country_options(trials)}
            </select>
          </label>
          <p class="fine" id="filter-count" aria-live="polite"></p>
        </div>'''
        + (tr_h or "<p>No recruiting trials in this snapshot.</p>")
        + '<p class="trial-empty" id="trial-empty">No recruiting trials in the snapshot for that country. Try “All countries”, or check ClinicalTrials.gov directly.</p>'
        + '<h2 id="civic">Open evidence from CIViC</h2>'
        + '<p class="fine">CIViC is an educational knowledgebase released under CC0. These statements are not regulatory approvals.</p>'
        + civic_html(b.get("civic") or {})
        + '<h2 id="reading">Further reading</h2>'
        + '<p class="fine">Citation cards only — titles, authors, journal and a link to PubMed. Abstracts are not reproduced.</p>'
        + literature_html(b.get("literature") or [])
        + "</main>"
        + footer(snap, root=False)
        + "</div></body></html>\n"
    )

def whats_new_html(items: list) -> str:
    if not items:
        return "<p>No changes recorded.</p>"
    out = ['<ol class="news">']
    for it in items:
        kind = (it.get("type") or "note").replace("-", " ")
        url = it.get("url")
        text = it.get("text") or ""
        body = f'<a href="{esc(url)}">{esc(text)}</a>' if url else esc(text)
        out.append(f'<li><span class="kind">{esc(kind)}</span> {body}</li>')
    out.append("</ol>")
    return "".join(out)

def page_home(snap: dict) -> str:
    cards = []
    for b in snap.get("biomarkers") or []:
        n_th = len(targeting_therapies(b))
        n_tr = len(requiring_trials(b))
        cards.append(f'''
        <li>
          <a class="bm-card" href="b/{esc(b["id"])}.html">
            <p class="name">{esc(b["name"])}</p>
            <p class="full">{esc(b.get("fullName") or "")}</p>
            <p class="counts">{n_th} therapies · {n_tr} recruiting trials</p>
          </a>
        </li>''')
    ct_ts = (snap.get("clinicalTrials") or {}).get("dataTimestamp") or ""
    counts = snap.get("counts") or {}
    return (
        head("Targeted Therapy Explorer — approved therapies and recruiting trials", root=True)
        + '<div class="wrap">'
        + masthead(snap, "home", root=True)
        + '<main id="main">'
        + notice(snap["snapshotDate"], ct_ts, root=True)
        + '<h2 id="biomarkers">Choose a biomarker</h2>'
        + '<p class="lede">Pick one entry from this closed list. There is no search box, no upload, and no place to enter personal or clinical information.</p>'
        + f'<ul class="bm-grid">{"".join(cards)}</ul>'
        + '<h2 id="whats-new">What’s new this week</h2>'
        + '<p class="fine">Changes are computed from the difference between this snapshot and the previous one.</p>'
        + whats_new_html(snap.get("whatsNew") or [])
        + f'''<p class="fine">This snapshot: {counts.get("therapies",0)} therapy rows, {counts.get("trials",0)} recruiting trials, {counts.get("civicAssertions",0)} CIViC assertions, {counts.get("literature",0)} citation cards.</p>'''
        + "</main>"
        + footer(snap, root=True)
        + "</div></body></html>\n"
    )

def page_about(snap: dict) -> str:
    stats = snap.get("sourceStats") or {}
    counts = snap.get("counts") or {}
    failures = snap.get("failures") or []
    fail_h = ""
    if failures:
        fail_h = "<h3>Sources that failed in this snapshot</h3><ul>" + "".join(
            f"<li>{esc(f.get('source'))}: {esc(f.get('error'))}</li>" for f in failures
        ) + "</ul>"
    else:
        fail_h = "<p>Every source responded for this snapshot.</p>"
    ct_ts = (snap.get("clinicalTrials") or {}).get("dataTimestamp") or ""
    return (
        head("About &amp; sources — Targeted Therapy Explorer", root=True)
        + '<div class="wrap">'
        + masthead(snap, "about", root=True)
        + '<main id="main" class="prose">'
        + notice(snap["snapshotDate"], ct_ts, root=True)
        + "<h2>About this site</h2>"
        + f"<p>{esc(DISCLAIMER_LONG)}</p>"
        + """
        <p>The explorer maps a <strong>closed list of tumour biomarkers</strong> to approved targeted therapies and recruiting clinical trials, using public sources only. It is a watch-and-explain tool. It is not personalised to any patient, and it is not intended to be used to take a diagnostic or therapeutic decision.</p>
        <p>You can pick a biomarker from the list. There is no free-text field, no file upload, no cookie, no analytics, and no account. A country filter on each trial list runs entirely in your browser.</p>
        <p>A legal review of this wording, including under the EU Medical Device Regulation, is planned before any promotion of the site. It did not block this first build.</p>
        <h2>How the data is refreshed</h2>
        <p>A weekly GitHub Action rebuilds the static JSON snapshot and opens a pull request. Nothing goes live until that pull request is merged. If a snapshot is more than eight days old, every page shows a stale-data banner. ClinicalTrials.gov’s own processing date is shown where trials appear, as their terms require.</p>
        <h2>Sources, licences and attribution</h2>
        <p>Terms were checked against each source’s official pages on 12 November 2026 (Europe/Paris). A full table, including notes on terms that are restrictive or that could not be re-extracted this turn, is in <a href="SOURCES.md">SOURCES.md</a>. This explorer uses public sources only.</p>
        <div class="sources-table-wrap">
        <table class="sources">
          <thead>
            <tr>
              <th>Source</th>
              <th>What we use</th>
              <th>Licence or terms</th>
              <th>Terms URL</th>
              <th>Attribution requirement</th>
              <th>How we meet it</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>ClinicalTrials.gov API v2</td>
              <td>Recruiting trial records (title, NCT ID, status, phase, conditions, interventions, site city and country). Registry-level only: no contact names, emails or phones.</td>
              <td>Free to use under the Terms and Conditions (last updated 31 January 2023). International copyright outside the United States. Display the source and processing date; keep data current; no proprietary rights; no email marketing.</td>
              <td><a href="https://clinicaltrials.gov/about-site/terms-conditions">Terms</a>; <a href="https://clinicaltrials.gov/">ClinicalTrials.gov</a></td>
              <td>Attribute ClinicalTrials.gov; show the processing date; describe selection.</td>
              <td>Each card cites ClinicalTrials.gov and links to the NCT record. The processing date is on every trials page. Weekly snapshots; stale banner after eight days. No emails are extracted.</td>
            </tr>
            <tr>
              <td>openFDA drug labels</td>
              <td>Indications and Usage excerpts, brand and generic names, application numbers, DailyMed set IDs.</td>
              <td>Public domain under <a href="https://creativecommons.org/publicdomain/zero/1.0/">CC0 1.0</a> unless a record is marked as a third-party work (those are skipped). Attribution requested, not required. Not for medical-care decisions.</td>
              <td><a href="https://open.fda.gov/terms/">Terms</a>; <a href="https://open.fda.gov/license/">License</a>; <a href="https://open.fda.gov/apis/drug/label/">API</a></td>
              <td>Requested: “Data provided by the U.S. Food and Drug Administration (https://open.fda.gov)”.</td>
              <td>That credit is given on this page. Each excerpt is labelled as FDA label text and linked to DailyMed.</td>
            </tr>
            <tr>
              <td>DailyMed (NLM)</td>
              <td>Outbound links to the official FDA Structured Product Label.</td>
              <td>FDA label text is U.S. government public text. NLM terms: acknowledge NLM, do not imply endorsement, keep current or say so.</td>
              <td><a href="https://dailymed.nlm.nih.gov/dailymed/about-dailymed.cfm">About DailyMed</a>; <a href="https://www.nlm.nih.gov/databases/download.html">NLM downloading terms</a></td>
              <td>Acknowledge the source; link back to the official label.</td>
              <td>Every excerpt cites “FDA drug label (openFDA / DailyMed)” and links to the DailyMed record.</td>
            </tr>
            <tr>
              <td>Drugs@FDA</td>
              <td>Application-number links (BLA/NDA overview). Files themselves are not copied.</td>
              <td>FDA website content is, unless otherwise noted, a U.S. government work in the public domain. Date the copy and link back.</td>
              <td><a href="https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files">Drugs@FDA data files</a>; <a href="https://www.fda.gov/about-fda/about-website/website-policies">FDA website policies</a></td>
              <td>Recommended: date the copy and link back.</td>
              <td>Each therapy cites Drugs@FDA with the application number and a link. The snapshot date is on every page.</td>
            </tr>
            <tr>
              <td>FDA Table of Pharmacogenomic Biomarkers in Drug Labeling</td>
              <td>Rows associating a biomarker with a drug’s labeling sections, used to seed therapy lists.</td>
              <td>U.S. government work, public domain unless otherwise noted. Date the copy and link back.</td>
              <td><a href="https://www.fda.gov/drugs/science-and-research-drugs/table-pharmacogenomic-biomarkers-drug-labeling">PGx table</a>; <a href="https://www.fda.gov/about-fda/about-website/website-policies">FDA website policies</a></td>
              <td>Recommended: date the copy, link back, credit the FDA.</td>
              <td>Each therapy cites the table by name, with a link. Snapshot date on every page. Credit on this page.</td>
            </tr>
            <tr>
              <td>FDA list of authorized companion diagnostic devices</td>
              <td>Device name and indication rows, shown as companion-diagnostic notes.</td>
              <td>Same FDA website policy as above.</td>
              <td><a href="https://www.fda.gov/medical-devices/in-vitro-diagnostics/list-fda-authorized-companion-diagnostic-devices-in-vitro-and-imaging-tools">CDx list</a>; <a href="https://www.fda.gov/about-fda/about-website/website-policies">FDA website policies</a></td>
              <td>Recommended: date the copy, link back, credit the FDA.</td>
              <td>Each cited device is attributed to the FDA CDx list with a link.</td>
            </tr>
            <tr>
              <td>European Medicines Agency medicines data</td>
              <td>Name, INN, authorisation status and date, EPAR URL. Full EPARs are not copied.</td>
              <td>© EMA 1995–2026. May be reproduced and distributed, commercially or not, provided the Agency is acknowledged as the source in each copy. EMA logo may not be used.</td>
              <td><a href="https://www.ema.europa.eu/en/about-us/about-website/legal-notice">Legal notice</a>; <a href="https://www.ema.europa.eu/en/medicines/download-medicine-data">Downloadable medicines data</a></td>
              <td>Acknowledge the European Medicines Agency as the source. Do not use the EMA logo.</td>
              <td>EMA is named on each matching therapy and in citations, with a link to the EPAR. The logo is not used. The EMA PMS API is not used.</td>
            </tr>
            <tr>
              <td>CIViC</td>
              <td>Gene summaries (including EGFR) and curated assertion statements, via the public GraphQL API.</td>
              <td>Dedicated to the public domain under <strong>CC0 1.0 Universal</strong>. Attribution is not legally required. Educational; not medical advice.</td>
              <td><a href="https://civicdb.org/releases/licensing">CIViC licensing</a>; <a href="https://creativecommons.org/publicdomain/zero/1.0/">CC0 1.0</a></td>
              <td>Not legally required; we cite CIViC as scholarly practice.</td>
              <td>Summaries and assertions are credited “CIViC (CC0)” with a link to <code>https://civicdb.org/…</code>.</td>
            </tr>
            <tr>
              <td>PubMed / NCBI E-utilities</td>
              <td>Bibliographic metadata only (title, authors, journal, year, PMID, link). Abstracts and full text are not fetched, stored or displayed.</td>
              <td>NLM government webpages are public domain. Acknowledge NLM; do not imply endorsement; keep current or disclose. NLM does not claim copyright on PubMed abstracts, but publishers or authors may — abstracts are omitted. At most three E-utilities requests per second without a key; identify <code>tool</code> and <code>email</code>.</td>
              <td><a href="https://www.ncbi.nlm.nih.gov/home/about/policies/">NCBI policies</a>; <a href="https://www.nlm.nih.gov/databases/download.html">NLM downloading terms</a>; <a href="https://www.ncbi.nlm.nih.gov/books/NBK25497/">E-utilities help</a></td>
              <td>Acknowledge NLM; no implied endorsement; do not copy publisher-copyrighted abstracts; show NCBI’s disclaimer; identify tool and email.</td>
              <td>Cards show only citation metadata and a PMID link. NLM is acknowledged here; endorsement is not implied. Requests send <code>tool</code> and a project email, at or under three per second, with no API key.</td>
            </tr>
            <tr>
              <td>MyGene.info and other gene-summary APIs</td>
              <td><strong>Not used.</strong> Gene summaries come from CIViC (CC0).</td>
              <td>—</td>
              <td>—</td>
              <td>—</td>
              <td>—</td>
            </tr>
            <tr>
              <td>OncoKB</td>
              <td><strong>Not used.</strong> Memorial Sloan Kettering’s terms do not allow redistribution without permission.</td>
              <td>Memorial Sloan Kettering’s terms do not allow redistribution without permission. The terms URL is not linked here: OncoKB hosts are forbidden on this site.</td>
              <td>—</td>
              <td>Do not redistribute.</td>
              <td>No OncoKB data is fetched, stored or displayed. A gate test fails if OncoKB appears.</td>
            </tr>
          </tbody>
        </table>
        </div>
        <div class="licence">
          <h3>ClinicalTrials.gov API v2</h3>
          <p>Trial records come from the U.S. National Library of Medicine’s <a href="https://clinicaltrials.gov/">ClinicalTrials.gov</a> API v2. Downloading the data signifies acceptance of the <a href="https://clinicaltrials.gov/about-site/terms-conditions">ClinicalTrials.gov Terms and Conditions</a> (last updated 31 January 2023). The data are free to use, but they carry an international copyright outside the United States; some records may also be subject to third-party copyright. We attribute the source as ClinicalTrials.gov, display the processing date (<code>dataTimestamp</code>), keep weekly snapshots, and describe our selection (recruiting studies whose condition or eligibility inclusion requires the biomarker, closed biomarker queries, a country filter applied in the page). We assert no proprietary rights in the database and do not use extracted email addresses.</p>
          <p class="fine">This snapshot: {trials} recruiting records. Processing date: {ct_human}.</p>
        </div>
        <div class="licence">
          <h3>openFDA drug labels and Drugs@FDA</h3>
          <p>Label excerpts come from <a href="https://open.fda.gov/apis/drug/label/">openFDA</a>, with links to DailyMed and <a href="https://www.fda.gov/drugs/drug-approvals-and-databases/drugsfda-data-files">Drugs@FDA</a>. openFDA data is, unless otherwise noted, dedicated to the public domain under <a href="https://open.fda.gov/terms/">CC0 1.0</a>. Some records may be third-party works and are skipped if so marked. FDA asks that openFDA not be relied on to make decisions about medical care. Credit: Data provided by the U.S. Food and Drug Administration (<a href="https://open.fda.gov">https://open.fda.gov</a>). No API key is used; the published no-key rate limits apply.</p>
          <p class="fine">This snapshot: {labels} labels.</p>
        </div>
        <div class="licence">
          <h3>FDA pharmacogenomic and companion-diagnostic tables</h3>
          <p>Associations between biomarkers and therapies are taken from the <a href="https://www.fda.gov/drugs/science-and-research-drugs/table-pharmacogenomic-biomarkers-drug-labeling">Table of Pharmacogenomic Biomarkers in Drug Labeling</a> and the <a href="https://www.fda.gov/medical-devices/in-vitro-diagnostics/list-fda-authorized-companion-diagnostic-devices-in-vitro-and-imaging-tools">list of FDA-authorized companion diagnostic devices</a>, then checked against the drug’s Indications and Usage. A therapy is shown on a biomarker page only when the label indication, the pharmacogenomic table, or a companion-diagnostic row ties the drug to that biomarker as a <em>selection criterion</em>. Mentions that are incidental, or that use the biomarker as an exclusion or an opposite-status criterion, stay in the snapshot data (with a <code>relation</code> field) and are not rendered. FDA website contents are, unless otherwise noted, in the public domain. Credit to the U.S. Food and Drug Administration is given; each copied table is dated and linked back, as FDA recommends.</p>
          <p class="fine">This snapshot: {pgx} pharmacogenomic rows, {cdx} companion-diagnostic rows.</p>
        </div>
        <div class="licence">
          <h3>European Medicines Agency medicine data</h3>
          <p>EU authorisations come from the EMA’s <a href="https://www.ema.europa.eu/en/medicines/download-medicine-data">downloadable medicines data</a>, used under the <a href="https://www.ema.europa.eu/en/about-us/about-website/legal-notice">EMA legal notice</a>: documents may be reproduced and distributed, commercially or not, provided the Agency is acknowledged as the source in each copy. © EMA 1995–2026. We acknowledge the European Medicines Agency as the source. We link to each European Public Assessment Report rather than copying the full report. The EMA logo is not used. The EMA PMS API is not used.</p>
          <p class="fine">This snapshot: {ema} human medicines in the workbook; matches are listed on each therapy.</p>
        </div>
        <div class="licence">
          <h3>CIViC</h3>
          <p>Open evidence statements come from the <a href="https://civicdb.org/releases/licensing">CIViC</a> knowledgebase (Washington University School of Medicine), dedicated to the public domain under <strong>CC0 1.0 Universal</strong>. Attribution is not legally required; we cite CIViC as a matter of scholarly practice. CIViC is an educational resource and is not medical advice. We do not notify the CIViC team unless asked to.</p>
          <p class="fine">This snapshot: {civic} assertions.</p>
        </div>
        <div class="licence">
          <h3>PubMed E-utilities</h3>
          <p>Further-reading cards are bibliographic metadata from <a href="https://www.ncbi.nlm.nih.gov/home/about/policies/">NCBI PubMed</a> (title, authors, journal, date, PMID and a link). Abstracts and full text are not stored. An API key is not used; requests stay at or under three per second. NLM is acknowledged as the source; this site does not imply NLM endorsement. NLM does not claim copyright on PubMed abstracts, but publishers or authors may — which is why abstracts are omitted. <a href="https://www.nlm.nih.gov/databases/download.html">NLM downloading terms</a>.</p>
          <p class="fine">This snapshot: {lit} citation cards.</p>
        </div>
        <div class="licence">
          <h3>Sources not used</h3>
          <p><strong>OncoKB is not used.</strong> Memorial Sloan Kettering’s terms do not allow redistribution of OncoKB content to third parties without permission; a public website would be redistribution. No OncoKB data is fetched, stored or displayed.</p>
          <p>bioRxiv, medRxiv and arXiv are available as outbound citation sources in later snapshots if needed; this first snapshot uses PubMed for literature cards. HAS, INCa and Swissmedic are reserved for a later addition.</p>
        </div>
        <h2>This snapshot</h2>
        {fail}
        <p>Generated on {gen_human}. Counts: {th} therapies, {tr} trials, {cv} CIViC assertions, {li} literature cards.</p>
        <h2>Licence for the code</h2>
        <p>The code of this site is offered under the MIT License. The data remains under each source’s own terms, as set out above.</p>
        """.format(
            trials=counts.get("trials", 0),
            ct=esc(ct_ts or "not available"),
            ct_human=esc(fmt_date(ct_ts) if ct_ts else "not available"),
            labels=counts.get("openfdaLabels", 0),
            pgx=counts.get("fdaPgxRows", 0),
            cdx=counts.get("fdaCdxRows", 0),
            ema=counts.get("emaRows", 0),
            civic=counts.get("civicAssertions", 0),
            lit=counts.get("literature", 0),
            fail=fail_h,
            gen=esc(snap.get("generatedAt") or ""),
            gen_human=esc(fmt_date(snap.get("generatedAt") or "") or (snap.get("generatedAt") or "")),
            th=counts.get("therapies", 0),
            tr=counts.get("trials", 0),
            cv=counts.get("civicAssertions", 0),
            li=counts.get("literature", 0),
        )
        + "</main>"
        + footer(snap, root=True)
        + "</div></body></html>\n"
    )

def main() -> int:
    if not DATA.is_file():
        print(f"missing {DATA}", file=sys.stderr)
        return 1
    snap = json.loads(DATA.read_text(encoding="utf-8"))
    # Plain-language text is committed data, not generated at build or in
    # the browser. Fail the build if a line is unsourced, a number/date/drug
    # is not in its source, or the source hash is stale.
    from plain import validate_all
    errors = validate_all(snap)
    if errors:
        print(f"plain-text validation failed ({len(errors)} errors):", file=sys.stderr)
        for e in errors:
            print(" ", e, file=sys.stderr)
        return 1
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "b").mkdir(exist_ok=True)
    (SITE / "data").mkdir(exist_ok=True)
    # Copy snapshot next to the site so relative paths work on Pages
    (SITE / "data" / "snapshot.json").write_text(
        json.dumps({
            "snapshotDate": snap["snapshotDate"],
            "clinicalTrials": snap.get("clinicalTrials"),
            "counts": snap.get("counts"),
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    (SITE / "about.html").write_text(page_about(snap), encoding="utf-8")
    sources_md = ROOT / "SOURCES.md"
    if sources_md.is_file():
        (SITE / "SOURCES.md").write_text(sources_md.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Wrote about page and snapshot to {SITE}")
    from build_mockup import build as build_tree_site
    report = build_tree_site(snap)
    print(
        f"Wrote decision-tree site: {report['pages']} pages, "
        f"{report['leaves']} leaves, {len(report['biomarkers'])} biomarkers"
    )
    return 0

if __name__ == "__main__":
    sys.exit(main())
