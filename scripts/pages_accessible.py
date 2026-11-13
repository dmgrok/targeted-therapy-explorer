#!/usr/bin/env python3
"""Accessible biomarker and home pages: plain language, steps, categories.

Imported by build_site at render time. Shared chrome (masthead, notice,
footer, citations) stays in build_site so the About page is unchanged.
"""
from __future__ import annotations

from categories import (
    AI_NOTE,
    CATEGORY_DEFS,
    MAINSTREAM,
    ON_THE_EDGE,
    ORDER_NOTE,
    TRIALS,
    category_counts,
    civic_for_therapy,
    companion_diagnostics,
    leftover_civic,
    mainstream_therapies,
    on_the_edge_assertions,
    option_id,
    sample_type_from_indication,
    trial_options,
)
from plain import load_glossary, load_home_plain, load_plain, line_by_id

# Late, safe: build_site is already loaded when this is imported from main().
# When imported first (tests), build_site does not import this module at
# the top level, so there is no cycle.
from build_site import (  # noqa: E402
    DISCLAIMER_SHORT,
    cites_html,
    civic_html,
    country_options,
    esc,
    footer,
    head,
    literature_html,
    masthead,
    notice,
    whats_new_html,
)


def _plain_html(line: dict | None, fallback: str = "") -> str:
    if not line:
        return f'<p class="plain">{esc(fallback)}</p>' if fallback else ""
    text = esc(line.get("text") or fallback)
    links = []
    for s in line.get("sources") or []:
        url = s.get("url") or ""
        label = s.get("label") or s.get("id") or "Source"
        if url:
            links.append(f'<a class="plain-src" href="{esc(url)}">{esc(label)}</a>')
        else:
            links.append(f'<span class="plain-src">{esc(label)}</span>')
    cites = (
        f' <span class="plain-cites">{" · ".join(links)}</span>' if links else ""
    )
    return f'<p class="plain">{text}{cites}</p>'


def _sources_block(inner: str, summary: str = "Sources") -> str:
    if not inner.strip():
        return ""
    return (
        f'<details class="sources-toggle">'
        f"<summary>{esc(summary)}</summary>"
        f'<div class="sources-body">{inner}</div>'
        f"</details>"
    )


def _tag(category: str) -> str:
    labels = {
        MAINSTREAM: ("Mainstream", "tag-mainstream"),
        TRIALS: ("Trials", "tag-trials"),
        ON_THE_EDGE: ("On the edge", "tag-edge"),
    }
    label, cls = labels.get(category, (category, "tag"))
    return f'<span class="tag {cls}">{esc(label)}</span>'


def _article_id(name: str) -> str:
    return (name or "").lower().replace(" ", "-")


def therapy_article(t: dict, line: dict | None, civic_rows: list, biomarker: dict) -> str:
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
        ) + ("…" if len(cdx) > 3 else "") + "</p>"
    civic_h = ""
    if civic_rows:
        civic_h = (
            "<h4>CIViC assertions about this therapy</h4>"
            + civic_html({"genes": [], "assertions": civic_rows})
        )
    raw = excerpt_h + ema_h + cdx_h + cites_html(t.get("citations") or []) + civic_h
    name = t.get("name") or "Therapy"
    return f'''
    <article class="item" id="{esc(_article_id(name))}">
      <h3>{esc(name)}{brand} {_tag(MAINSTREAM)}</h3>
      {_plain_html(line)}
      {_sources_block(raw)}
    </article>
    '''


def trial_article(t: dict, line: dict | None) -> str:
    countries = t.get("countries") or []
    attr = " ".join(countries)
    phases = ", ".join(t.get("phases") or []) or "Phase not stated"
    cond = ", ".join(t.get("conditions") or [])
    iv = "; ".join(t.get("interventions") or [])
    loc_preview = ", ".join(sorted(countries)[:12])
    more = f" (+{len(countries)-12} more)" if len(countries) > 12 else ""
    start = t.get("startDate") or ""
    raw = f'''
      <p class="fine">
        <span class="badge">{esc(t.get("status") or "Recruiting")}</span>
        <span class="badge">{esc(phases)}</span>
        {f'<span class="badge">start {esc(start)}</span>' if start else ""}
      </p>
      <p class="excerpt">{esc(cond)}</p>
      <p class="fine">{esc(iv)}</p>
      <p class="fine">Locations: {esc(loc_preview)}{esc(more)}</p>
      <ul class="cites"><li><span class="src"><a href="{esc(t.get("url") or "")}">ClinicalTrials.gov</a></span> Record {esc(t.get("nctId") or "")}.</li></ul>
    '''
    return f'''
    <article class="item trial" data-countries="{esc(attr)}" data-nct="{esc(t.get("nctId") or "")}">
      <h3><a href="{esc(t.get("url") or "")}">{esc(t.get("nctId") or "")}</a>: {esc(t.get("title") or "")} {_tag(TRIALS)}</h3>
      {_plain_html(line)}
      {_sources_block(raw)}
    </article>
    '''


def edge_article(a: dict, line: dict | None) -> str:
    th = ", ".join(a.get("therapies") or [])
    bits = " · ".join(filter(None, [a.get("significance"), a.get("ampLevel"), a.get("disease"), th]))
    raw = f'''
      <p class="excerpt">{esc(a.get("summary") or a.get("molecularProfile") or "CIViC assertion")}</p>
      <p class="fine">{esc(bits)} — <a href="{esc(a.get("url") or "")}">CIViC assertion {esc(a.get("id"))}</a> (CC0). Status: {esc(a.get("status") or "")}.</p>
    '''
    title = th or f"CIViC assertion {a.get('id')}"
    return f'''
    <article class="item edge" id="civic-{esc(a.get("id"))}">
      <h3>{esc(title)} {_tag(ON_THE_EDGE)}</h3>
      {_plain_html(line)}
      {_sources_block(raw)}
    </article>
    '''


def cdx_article(c: dict, line: dict | None) -> str:
    sample = c.get("sampleType") or sample_type_from_indication(c.get("indication") or "")
    raw = f'''
      <p class="excerpt">{esc(c.get("diagnostic") or "")}</p>
      <p class="fine">Indication — sample type: {esc(c.get("indication") or "")}
      {f"(sample type: {esc(sample)})" if sample else ""}.</p>
      <p class="fine">Listed on the snapshot record for {esc(c.get("viaTherapy") or "a mainstream therapy")}.</p>
      <ul class="cites"><li><span class="src"><a href="{esc(c.get("url") or "")}">FDA companion diagnostic list</a></span></li></ul>
    '''
    return f'''
    <article class="item cdx">
      <h3>{esc(c.get("diagnostic") or "Companion diagnostic")}</h3>
      {_plain_html(line)}
      {_sources_block(raw)}
    </article>
    '''


def category_legend() -> str:
    items = []
    for d in CATEGORY_DEFS:
        items.append(
            f'''<div class="legend-item">
              {_tag(d["id"])}
              <p class="legend-short"><strong>{esc(d["short"])}</strong></p>
              <p class="fine rule">{esc(d["rule"])}</p>
            </div>'''
        )
    return (
        '<div class="category-legend" id="categories">'
        "<h3>How options are tagged</h3>"
        f"<p class='fine'>{esc(ORDER_NOTE)} Colours and position do not rank options.</p>"
        + "".join(items)
        + f"<p class='fine ai-note'>{esc(AI_NOTE)}</p>"
        + "</div>"
    )


def glossary_html() -> str:
    data = load_glossary()
    items = []
    for t in data.get("terms") or []:
        items.append(
            f"<div class='gloss-item'><dt>{esc(t.get('term') or '')}</dt>"
            f"<dd>{esc(t.get('text') or '')}</dd></div>"
        )
    return f'''
    <section class="glossary" id="glossary">
      <h2>Short glossary</h2>
      <p class="fine">Words that appear on these pages and are hard to avoid. These are general explanations, not medical advice.</p>
      <dl>{"".join(items)}</dl>
    </section>
    '''


def intro_block(biomarker: dict, plain: dict) -> str:
    intro = plain.get("intro") or {}
    what = intro.get("what") or []
    report = intro.get("test_report") or ""
    # Raw CIViC gene summary, verbatim, including any source typos.
    civic = leftover_civic(biomarker)
    genes_raw = ""
    for g in civic.get("genes") or []:
        if g.get("description"):
            genes_raw += (
                f'<p class="excerpt">{esc(g["description"])} '
                f'<a href="{esc(g.get("url") or "")}">CIViC gene summary for '
                f'{esc(g.get("name") or "")}</a> (CC0).</p>'
            )
    summary_cites = cites_html(biomarker.get("summarySources") or [])
    # Also keep the raw snapshot summary if it differs in wrapping only;
    # it is the same CIViC text in this snapshot.
    raw = genes_raw or (
        f'<p class="excerpt">{esc(biomarker.get("summary") or "")}</p>'
    )
    raw += summary_cites
    what_h = "".join(f"<p class='lede'>{esc(s)}</p>" for s in what)
    # Intro sources: attach the same refs as the committed intro.
    intro_line = {
        "text": report,
        "sources": intro.get("test_report_sources") or intro.get("sources") or [],
    }
    return f'''
    <section class="intro" id="intro">
      {what_h}
      {_plain_html(intro_line)}
      {_sources_block(raw, "Sources for this introduction")}
    </section>
    '''


def page_biomarker(snap: dict, b: dict) -> str:
    ct_ts = (snap.get("clinicalTrials") or {}).get("dataTimestamp") or ""
    plain = load_plain(b["id"])
    therapies = mainstream_therapies(b)
    trials = trial_options(b)
    edge = on_the_edge_assertions(b)
    cdx = companion_diagnostics(b)
    fr = sum(1 for t in trials if "France" in (t.get("countries") or []))
    ch = sum(1 for t in trials if "Switzerland" in (t.get("countries") or []))

    cdx_h = "".join(
        cdx_article(c, line_by_id(plain, option_id("cdx", c))) for c in cdx
    ) or (
        "<p>This snapshot does not list an FDA companion-diagnostic row for this biomarker. "
        "An approved therapy’s label may still require detection by an FDA-approved test — "
        "see each option’s sources.</p>"
    )

    th_h = "".join(
        therapy_article(
            t,
            line_by_id(plain, option_id(MAINSTREAM, t)),
            civic_for_therapy(b, t),
            b,
        )
        for t in therapies
    ) or (
        "<p>No therapies in this snapshot have a label indication, FDA pharmacogenomic row "
        "or companion-diagnostic row that ties the drug to this biomarker as a selection criterion.</p>"
    )

    tr_h = "".join(
        trial_article(t, line_by_id(plain, option_id(TRIALS, t))) for t in trials
    )
    edge_h = "".join(
        edge_article(a, line_by_id(plain, option_id(ON_THE_EDGE, a))) for a in edge
    ) or (
        "<p>This snapshot has no On the edge option for this biomarker: there is no CIViC "
        "PREDICTIVE assertion with a recorded evidence level below TIER_I_LEVEL_A that names a therapy.</p>"
    )

    leftover = leftover_civic(b)
    # Assertions already shown on a therapy's Sources or as an On the edge option
    # are skipped here so we do not repeat them; the raw text still exists on
    # those items. Remaining diagnostic / prognostic / oncogenic rows stay.
    shown_ids = {a.get("id") for a in edge}
    for t in therapies:
        for a in civic_for_therapy(b, t):
            shown_ids.add(a.get("id"))
    leftover_assert = [a for a in leftover.get("assertions") or [] if a.get("id") not in shown_ids]
    leftover_h = civic_html({"genes": [], "assertions": leftover_assert}) if leftover_assert else ""
    civic_section = ""
    if leftover_h:
        civic_section = (
            '<h2 id="civic">Other open evidence from CIViC</h2>'
            '<p class="fine">CIViC is an educational knowledgebase released under CC0. '
            "These statements are not regulatory approvals. They are diagnostic, "
            "prognostic or oncogenic assertions, or highest-level predictive "
            "assertions not already shown on a therapy. Raw wording is unchanged.</p>"
            + _sources_block(leftover_h, "Sources: other CIViC assertions")
        )
    elif not leftover.get("assertions") and not ((b.get("civic") or {}).get("assertions") or []):
        civic_section = (
            '<h2 id="civic">Open evidence from CIViC</h2>'
            '<p class="fine">CIViC is an educational knowledgebase released under CC0. '
            "These statements are not regulatory approvals.</p>"
            "<p>No curated assertions yet.</p>"
        )
    else:
        # Keep the id so existing tests that split on it still work.
        civic_section = '<div id="civic" hidden></div>'

    reading = (
        '<h2 id="reading">Further reading</h2>'
        '<p class="fine">Citation cards only — titles, authors, journal and a link to PubMed. Abstracts are not reproduced.</p>'
        + _sources_block(literature_html(b.get("literature") or []), "Sources: PubMed citation cards")
    )

    return (
        head(f"{b['name']} — Targeted Therapy Explorer", root=False)
        + '<div class="wrap">'
        + masthead(snap, "bm", root=False)
        + f'<main id="main">'
        + notice(snap["snapshotDate"], ct_ts, root=False)
        + f'<h2>{esc(b["name"])}</h2>'
        + f'<p class="lede">{esc(b.get("fullName") or "")}</p>'
        + intro_block(b, plain)
        + '<h2 id="path">Options on the public record</h2>'
        + '<p class="fine">This is a map of what the public record in this snapshot contains, '
        "not a decision procedure and not a recommendation. "
        f"{esc(ORDER_NOTE)}</p>"
        + category_legend()
        + '''
        <ol class="steps">
          <li class="step" id="step-test">
            <h3><span class="step-num" aria-hidden="true">1</span> A test confirms this biomarker</h3>
            <p>FDA companion diagnostics listed for this biomarker in this snapshot are below. The sample type, when the FDA table gives one, is the part of the indication after the dash.</p>
        '''
        + cdx_h
        + f'''
          </li>
          <li class="step" id="step-options">
            <h3><span class="step-num" aria-hidden="true">2</span> Options, tagged by how they appear in the public record</h3>
            <p class="fine">The three groups have equal weight. {esc(ORDER_NOTE)}</p>
            <div class="branches branches-legend" aria-hidden="false">
              <div class="branch">{_tag(MAINSTREAM)}<p class="fine"><span class="count">{len(therapies)}</span> in this snapshot.</p></div>
              <div class="branch">{_tag(TRIALS)}<p class="fine"><span class="count">{len(trials)}</span> in this snapshot, including {fr} with a site in France and {ch} with a site in Switzerland.</p></div>
              <div class="branch">{_tag(ON_THE_EDGE)}<p class="fine"><span class="count">{len(edge)}</span> in this snapshot.</p></div>
            </div>
            <div class="option-lists">
              <section class="branch-list" id="therapies">
                <h3>Mainstream <span class="count">{len(therapies)}</span></h3>
                <p class="fine">{esc(CATEGORY_DEFS[0]["short"])} {len(therapies)} in this snapshot, listed alphabetically.</p>
                {th_h}
              </section>
              <section class="branch-list" id="trials">
                <h3>Trials <span class="count">{len(trials)}</span></h3>
                <p class="fine">{len(trials)} recruiting studies from ClinicalTrials.gov whose condition or eligibility inclusion criteria require this biomarker as a selection criterion, including {fr} with a site in France and {ch} with a site in Switzerland. A mention only in exclusions, interventions or keywords is not enough; those records stay in the snapshot data and are not shown. Filter is applied on this page only; nothing is sent anywhere. Listed alphabetically by NCT number.</p>
                <div class="filter-bar">
                  <label for="country-filter">Country
                    <select id="country-filter" name="country">
                      {country_options(trials)}
                    </select>
                  </label>
                  <p class="fine" id="filter-count" aria-live="polite"></p>
                </div>
                {tr_h or "<p>No recruiting trials in this snapshot.</p>"}
                <p class="trial-empty" id="trial-empty">No recruiting trials in the snapshot for that country. Try “All countries”, or check ClinicalTrials.gov directly.</p>
              </section>
              <section class="branch-list" id="edge">
                <h3>On the edge <span class="count">{len(edge)}</span></h3>
                <p class="fine">{esc(CATEGORY_DEFS[2]["short"])} {len(edge)} in this snapshot, listed alphabetically.</p>
                {edge_h}
              </section>
            </div>
          </li>
        </ol>
        '''
        + civic_section
        + reading
        + glossary_html()
        + "</main>"
        + footer(snap, root=False)
        + "</div></body></html>\n"
    )


def page_home(snap: dict) -> str:
    plain = load_home_plain()
    intro = plain.get("intro") or {}
    what = intro.get("what") or []
    how_line = line_by_id(plain, "home:how")
    cards = []
    for b in snap.get("biomarkers") or []:
        counts = category_counts(b)
        cards.append(f'''
        <li>
          <a class="bm-card" href="b/{esc(b["id"])}.html">
            <p class="name">{esc(b["name"])}</p>
            <p class="full">{esc(b.get("fullName") or "")}</p>
            <p class="counts"><span>{counts[MAINSTREAM]} mainstream</span> <span>{counts[TRIALS]} trials</span> <span>{counts[ON_THE_EDGE]} on the edge</span></p>
          </a>
        </li>''')
    ct_ts = (snap.get("clinicalTrials") or {}).get("dataTimestamp") or ""
    counts = snap.get("counts") or {}
    what_h = "".join(f"<p class='lede'>{esc(s)}</p>" for s in what)
    return (
        head("Targeted Therapy Explorer — approved therapies and recruiting trials", root=True)
        + '<div class="wrap">'
        + masthead(snap, "home", root=True)
        + '<main id="main">'
        + notice(snap["snapshotDate"], ct_ts, root=True)
        + '<section class="intro" id="intro">'
        + "<h2>What this site is</h2>"
        + what_h
        + _plain_html(how_line)
        + "</section>"
        + category_legend()
        + '''
        <section class="home-steps" id="path">
          <h2>How a biomarker page is organised</h2>
          <ol class="steps">
            <li class="step">
              <h3><span class="step-num" aria-hidden="true">1</span> A test confirms the biomarker</h3>
              <p>Each biomarker page lists FDA companion diagnostics from this snapshot, including the sample type when the FDA table gives one.</p>
            </li>
            <li class="step">
              <h3><span class="step-num" aria-hidden="true">2</span> Options on the public record</h3>
              <p>Options are tagged Mainstream, Trials or On the edge, using the rules above. The three groups have equal weight. This is a map, not a decision procedure.</p>
              <div class="branches home-branches">
                <div class="branch">''' + _tag(MAINSTREAM) + '''<p class="fine">FDA-approved for that biomarker, in this snapshot.</p></div>
                <div class="branch">''' + _tag(TRIALS) + '''<p class="fine">A recruiting study that requires that biomarker.</p></div>
                <div class="branch">''' + _tag(ON_THE_EDGE) + '''<p class="fine">Early evidence from CIViC, not an FDA approval in this snapshot.</p></div>
              </div>
            </li>
          </ol>
        </section>
        '''
        + '<h2 id="biomarkers">Choose a biomarker</h2>'
        + '<p class="lede">Pick one entry from this closed list. There is no search box, no upload, and no place to enter personal or clinical information. Counts are from this snapshot; they do not rank the biomarkers.</p>'
        + f'<ul class="bm-grid">{"".join(cards)}</ul>'
        + '<h2 id="whats-new">What’s new this week</h2>'
        + '<p class="fine">Changes are computed from the difference between this snapshot and the previous one.</p>'
        + whats_new_html(snap.get("whatsNew") or [])
        + f'''<p class="fine">This snapshot: {counts.get("therapies",0)} therapy rows, {counts.get("trials",0)} recruiting trials, {counts.get("civicAssertions",0)} CIViC assertions, {counts.get("literature",0)} citation cards.</p>'''
        + glossary_html()
        + "</main>"
        + footer(snap, root=True)
        + "</div></body></html>\n"
    )
