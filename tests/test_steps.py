#!/usr/bin/env python3
"""Gates for the steps front door (site/index.html) and the drug-pages start."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from readability import flesch_kincaid, visible_text  # noqa: E402

SITE = ROOT / "site"
INDEX = SITE / "index.html"
OPTIONS = SITE / "options" / "index.html"
BIOMARKER_IDS = ["EGFR", "ALK", "BRAF-V600E", "KRAS-G12C", "HER2", "NTRK", "MSI-H-dMMR"]
STEPS = [
    "step-diagnosis",
    "step-testing",
    "step-second-opinion",
    "step-tumour-board",
    "step-matching",
    "step-monitoring",
    "step-access",
]
# 8th-to-early-high-school is the target; medical names inflate the score a little.
FK_MAX = 9.0

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)
    print(f"FAIL: {msg}")


def ok(msg: str) -> None:
    print(f"ok: {msg}")


def section(html: str, sid: str) -> str:
    m = re.search(
        rf'<section[^>]*id="{re.escape(sid)}"[^>]*>(.*?)</section>',
        html,
        flags=re.S | re.I,
    )
    return m.group(1) if m else ""


def test_front_door() -> None:
    if not INDEX.is_file():
        err("missing site/index.html")
        return
    html = INDEX.read_text(encoding="utf-8")
    vis = visible_text(html)
    if "<h1>" not in html or "Steps people take today" not in html:
        err("home is not the steps front door")
    else:
        ok("index is the steps front door")
    if "Not medical advice. Talk to your oncologist." not in html:
        err("steps page missing short banner")
    if "notice.html" not in html or "Full notice" not in html:
        err("steps page does not link to the full notice")
    if re.search(r"<form\b", html, re.I):
        err("steps page has a form")
    if re.search(r"<(input|textarea|select)\b", html, re.I):
        err("steps page collects input")
    if re.search(r"\b(we recommend|best option|preferred option|you should take)\b", html, re.I):
        err("steps page sounds like a recommendation")
    if "not a ranking" not in vis.lower() and "not a ranking" not in html.lower():
        err("steps page does not say the lists are not a ranking")
    # No live AI: static boxes only, no chat widget.
    if re.search(r"\b(chat\s*widget|ask the assistant|type your question)\b", vis, re.I):
        err("steps page looks like a live AI chat")
    if "no live ai" not in vis.lower() and "no live ai" not in html.lower():
        err("steps page does not say there is no live AI")
    if (
        "no patient data" not in vis.lower()
        and "stores no patient data" not in vis.lower()
        and "no collection of patient data" not in vis.lower()
    ):
        if (
            "stores no patient data" not in html.lower()
            and "no patient data" not in html.lower()
            and "no collection of patient data" not in html.lower()
        ):
            err("steps page does not say it collects no patient data")
    if html.count('class="notice notice-full"') or html.count("notice-full"):
        err("steps page still has a second, full disclaimer block; merge into one short notice")
    if "Some figures come from studies of older AI models" not in vis:
        err("confidence is not a single plain line about older AI models")
    if "High confidence for the steps" in vis:
        err("detailed confidence box is still in the visible body")
    ok("banner, notice, no form, no live AI, no recommendation")


def test_each_step() -> None:
    html = INDEX.read_text(encoding="utf-8")
    for sid in STEPS:
        chunk = section(html, sid)
        if not chunk:
            err(f"missing step section #{sid}")
            continue
        if 'class="ai-explainer"' not in chunk:
            err(f"{sid} missing static AI explainer box")
        if "How AI can help" not in chunk:
            err(f"{sid} AI box missing heading")
        if "must not" not in chunk.lower() and "must not" not in visible_text(chunk).lower():
            err(f"{sid} AI box missing a limit")
        if "Opened" not in chunk and "Re-opened" not in chunk:
            err(f"{sid} missing an opened date on sources")
        if "November 2026" not in chunk:
            err(f"{sid} sources missing the 2026 opened date")
    ok("each of the 7 steps has an explanation, a static AI box, and dated sources")


def test_matching_links_drug_pages() -> None:
    html = INDEX.read_text(encoding="utf-8")
    chunk = section(html, "step-matching")
    if 'href="options/index.html"' not in chunk:
        err("matching step does not link to options/index.html")
    else:
        ok("matching step links to the drug pages")
    for bid in BIOMARKER_IDS:
        if f'href="b/{bid}/index.html"' not in html:
            err(f"steps page missing link to {bid}")
    if not OPTIONS.is_file():
        err("missing options/index.html (drug-pages start)")
        return
    opt = OPTIONS.read_text(encoding="utf-8")
    if "Choose a gene finding" not in opt:
        err("options page is not the decision-tree start")
    for bid in BIOMARKER_IDS:
        if f'href="../b/{bid}/index.html"' not in opt:
            err(f"options page missing link to {bid}")
    if "Mainstream" not in opt or "On the edge" not in opt:
        err("options page missing category labels")
    if "Not medical advice. Talk to your oncologist." not in opt:
        err("options page missing disclaimer")
    ok("drug pages remain reachable from the matching step")


def test_where_to_start() -> None:
    html = INDEX.read_text(encoding="utf-8")
    chunk = section(html, "where-to-start")
    if not chunk:
        err("missing #where-to-start")
        return
    vis = visible_text("<section>" + chunk + "</section>")
    if "not a ranking" not in chunk.lower():
        err("where-to-start does not say the order is not a ranking")
    for heading in (
        "Testing and expert networks",
        "Early and compassionate access",
        "Trial finders",
    ):
        if heading not in chunk:
            err(f"where-to-start missing category {heading!r}")
    # A–Z within each group: extract place-name text.
    groups = re.findall(
        r'<div class="places-group">(.*?)</div>',
        chunk,
        flags=re.S,
    )
    if len(groups) != 3:
        err(f"expected 3 place groups, got {len(groups)}")
    for g in groups:
        names = re.findall(r'class="place-name"><a[^>]*>(.*?)</a>', g, flags=re.S)
        names = [re.sub(r"<[^>]+>", "", n).strip() for n in names]
        if names != sorted(names, key=lambda s: s.lower()):
            err(f"place names are not A–Z: {names}")
    if "ChiCTR" not in chunk:
        err("where-to-start does not mention ChiCTR")
    # Mention only: no finder card and no search-tool link.
    if re.search(r'href="[^"]*chictr[^"]*"', chunk, re.I):
        err("ChiCTR must be a mention only, not a search-tool link")
    if "not used here as a search tool" not in chunk:
        err("ChiCTR mention does not say it is not a search tool")
    # Country is a fact, not an organising axis: no country-switch UI.
    if re.search(r'role="tablist"|country-switch|data-country', chunk, re.I):
        err("where-to-start has a country switch")
    ok("where-to-start is category then A–Z, no ranking, ChiCTR mention only")


def test_sid_example() -> None:
    html = INDEX.read_text(encoding="utf-8")
    chunk = section(html, "sid-sijbrandij")
    if not chunk:
        err("missing #sid-sijbrandij")
        return
    if "This is one person’s story, not evidence that a treatment works." not in chunk:
        err("Sid section missing the case-study opener")
    if "I currently have no evidence of disease." not in chunk:
        err("Sid section missing verified Substack quote")
    if "But my fight with cancer is far from over." not in chunk:
        err("Sid section missing the second Substack quote")
    if "maximum diagnostics" not in chunk:
        err("Sid section missing the cancer-page quote")
    if "work through enormous amounts of data" not in chunk:
        err("Sid section missing the Forum paraphrase")
    if "AIS helped" in visible_text(chunk):
        err("Sid visible text prints the transcript typo 'AIS helped' as his words")
    if "I’m not gonna trust this out of the box" not in chunk and "I'm not gonna trust this out of the box" not in chunk:
        err("Sid section missing Stern’s verified quote")
    if "As of 20 January 2026, per his Substack post" not in chunk:
        err("Sid status is not 'As of <date>, per <source>'")
    if 'href="cases/sijbrandij.html"' not in chunk:
        err("Sid section does not link to the case study page")
    # Must not claim Kilo Code as his cancer tool, anywhere.
    if re.search(r"used Kilo Code", chunk) and "does not claim" not in (section(html, "how-we-checked") + chunk):
        err("page claims Kilo Code use")
    if "Kilo Code" in visible_text(chunk):
        err("Sid visible text mentions Kilo Code; keep that only in How we checked")
    ok("Sid example uses the opener, verified quotes, and dated status")


def test_gpt35_and_newer_evidence() -> None:
    html = INDEX.read_text(encoding="utf-8")
    vis = visible_text(html)
    if "2023 studies of GPT-3.5" not in vis and "2023 studies of GPT-3.5" not in html:
        err("2023 GPT-3.5 figures are not clearly labelled as 2023 studies of an older model")
    if "older model" not in vis and "older model" not in html:
        err("GPT-3.5 is not labelled as an older model")
    if "13 of 104" not in html or "12.5%" not in html:
        err("2023 JAMA hallucination figure missing")
    # 2024 evidence that was actually opened this work.
    if "23 October 2024" not in html or "JAMA Network Open" not in html:
        err("2024 JAMA Network Open study is missing")
    if "57 out of 79" not in html and "57 of 79" not in html:
        err("2024 multiple-choice figure missing")
    if "30 out of 79" not in html and "30 of 79" not in html:
        err("2024 free-text figure missing")
    if "14 November 2026" not in html:
        err("2024 paper is not cited with the date it was opened")
    if "jamanetworkopen.2024.37711" not in html and "fullarticle/2825235" not in html:
        err("2024 paper is not linked")
    ok("2023 GPT-3.5 figures are labelled; 2024 opened evidence is cited")


def _reader_body(html: str) -> str:
    """Visible body, outside sources toggles and the How we checked note."""
    # visible_text already drops <details>. Also drop a How we checked
    # section if it is ever rendered outside details.
    html = re.sub(
        r'<section[^>]*id="how-we-checked"[^>]*>.*?</section>',
        " ",
        html,
        flags=re.I | re.S,
    )
    html = re.sub(
        r'<details[^>]*id="how-we-checked"[^>]*>.*?</details>',
        " ",
        html,
        flags=re.I | re.S,
    )
    return visible_text(html)


def test_no_verification_chatter() -> None:
    html = INDEX.read_text(encoding="utf-8")
    body = _reader_body(html)
    for phrase in ("opened", "Unverified", "commenter", "AIS helped"):
        # Case-sensitive for Unverified and AIS; case-insensitive for opened/commenter
        if phrase in ("opened", "commenter"):
            hit = phrase.lower() in body.lower()
        else:
            hit = phrase in body
        if hit:
            # Show a short window for debugging.
            low = body.lower() if phrase in ("opened", "commenter") else body
            key = phrase.lower() if phrase in ("opened", "commenter") else phrase
            i = low.find(key)
            window = body[max(0, i - 40): i + 60]
            err(f"reader-facing body contains {phrase!r}: …{window}…")
    # How we checked (or a sources toggle) must still hold the moved notes.
    checked = section(html, "how-we-checked")
    if not checked and 'id="how-we-checked"' not in html:
        err("missing How we checked note")
    else:
        blob = checked or html
        if "Kilo Code" in blob and "does not claim Kilo Code" not in blob:
            err("How we checked is missing the Kilo Code non-claim")
        if "13 November 2026" not in blob and "Opened 13 November 2026" not in html:
            err("opened dates are missing from sources / How we checked")
    ok("reader-facing body has no verification chatter; notes are in sources / How we checked")


def test_readability() -> None:
    html = INDEX.read_text(encoding="utf-8")
    vis = visible_text(html)
    score = flesch_kincaid(vis)
    grade = score["grade"]
    print(f"FK grade for steps page: {grade} ({score['words']} words, {score['sentences']} sentences)")
    if grade is None:
        err("could not score FK grade")
    elif grade > FK_MAX:
        err(f"steps page FK grade {grade} is above {FK_MAX}")
    else:
        ok(f"steps page FK grade {grade} is at or under {FK_MAX}")


def test_identity() -> None:
    css = (SITE / "assets" / "css" / "mockup.css").read_text(encoding="utf-8")
    if re.search(r"#d97[0-9a-fA-F]{3}|#c65[0-9a-fA-F]{3}|#e67e22|#ff6b00|#f97316|#ea580c", css):
        err("mockup CSS appears to contain orange")
    html = INDEX.read_text(encoding="utf-8")
    # No product-look class names.
    if re.search(r"copilot|chatgpt-widget|claude-box|grok-box", html, re.I):
        err("steps page uses a forbidden assistant-product look")
    ok("Risograph identity, no orange, no assistant-product look")

STEP_DIAGRAM_IDS = ["step-diagnosis", "step-testing", "step-second-opinion", "step-tumour-board",
                    "step-matching", "step-monitoring", "step-access"]


def _figure(html: str, fid: str) -> str:
    m = re.search(r'<figure class="dg[^"]*" id="' + re.escape(fid) + r'">(.*?)</figure>', html, re.S)
    return m.group(1) if m else ""


def _svgs(fig: str) -> list[str]:
    return re.findall(r"<svg\b.*?</svg>", fig, re.S)


def _check_svg_a11y(svg: str, where: str) -> None:
    head = re.match(r"<svg\b[^>]*>", svg).group(0)
    if 'role="img"' not in head or "aria-labelledby" not in head:
        err(f"{where}: svg lacks role=img / aria-labelledby")
    ids = re.search(r'aria-labelledby="([^"]+)"', head)
    for i in (ids.group(1).split() if ids else []):
        if not re.search(r'<(title|desc) id="' + re.escape(i) + r'">[^<]{8,}</(title|desc)>', svg):
            err(f"{where}: labelled-by id {i} has no non-empty title/desc")
    if "viewBox" not in head:
        err(f"{where}: svg has no viewBox (not responsive)")


def test_diagrams() -> None:
    html = INDEX.read_text(encoding="utf-8")
    ov = _figure(html, "path-diagram")
    if not ov:
        err("overview diagram #path-diagram missing")
        return
    svgs = _svgs(ov)
    if len(svgs) != 2 or 'class="dg-wide"' not in svgs[0] or 'class="dg-tall"' not in svgs[1]:
        err("overview should have a wide and a tall (mobile) svg")
    for s in svgs:
        _check_svg_a11y(s, "overview")
        for n in range(1, 8):
            if f">Step {n}<" not in s and f">STEP {n}<" not in s:
                err(f"overview svg missing Step {n}")
        if ">Re-test<" not in s:
            err("overview svg has no Re-test loop label")
        if "stroke-dasharray" not in s:
            err("overview svg has no dashed branch to access routes")
    if "<figcaption" in ov:
        err("overview should not repeat its legend in a visible caption (title/desc carry it)")
    # Pink connectors are only the re-test return: one pink loop line per variant.
    wide = svgs[0] if svgs else ""
    if len(re.findall(r'<line\b[^>]*stroke="#b02058"', wide)) != 2:
        err("overview (wide): expected exactly one pink return line plus the pink key swatch")
    tall = svgs[1] if len(svgs) > 1 else ""
    if len(re.findall(r'<line\b[^>]*stroke="#b02058"', tall)) != 1:
        err("overview (mobile): expected exactly one pink return line")
    # overview sits before step 1
    if html.find('id="path-diagram"') > html.find('id="step-diagnosis"'):
        err("overview diagram should come before step 1")
    for sid in STEP_DIAGRAM_IDS:
        fig = _figure(html, f"dg-{sid}")
        if not fig:
            err(f"step diagram dg-{sid} missing")
            continue
        sec = re.search(r'<section class="path-step" id="' + sid + r'">(.*?)</section>', html, re.S)
        if not sec or f'id="dg-{sid}"' not in sec.group(1):
            err(f"dg-{sid} is not inside its step section")
        ss = _svgs(fig)
        if len(ss) != 2:
            err(f"dg-{sid}: expected wide + tall svg")
        for s in ss:
            _check_svg_a11y(s, f"dg-{sid}")
            if "ai can" not in s.lower() or "must not" not in s.lower():
                err(f"dg-{sid}: AI can / Must not panel missing")
    ok("overview + 7 step diagrams: role=img, title/desc, wide + mobile variants")


def test_sid_timeline_dates() -> None:
    import json
    html = INDEX.read_text(encoding="utf-8")
    fig = _figure(html, "sid-timeline")
    if not fig:
        err("Sid timeline #sid-timeline missing")
        return
    data = json.loads((ROOT / "data" / "cases" / "sijbrandij.json").read_text(encoding="utf-8"))
    def dates_in(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "date" and isinstance(v, str):
                    yield v.strip().lower()
                else:
                    yield from dates_in(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from dates_in(v)
    known = set(dates_in(data))
    shown = set()
    for s in _svgs(fig):
        _check_svg_a11y(s, "sid-timeline")
        for d in re.findall(r'fill="#b02058"[^>]*>([^<]+)</text>', s):
            shown.add(d.strip().lower())
    if not shown:
        err("Sid timeline shows no dates")
    extra = shown - known
    if extra:
        err(f"Sid timeline shows dates not in sijbrandij.json: {sorted(extra)}")
    ok(f"Sid timeline: {len(shown)} dates, all from the verified case file")


def test_diagram_wording() -> None:
    html = INDEX.read_text(encoding="utf-8")
    svg = " ".join(re.findall(r"<svg\b.*?</svg>", html, re.S))
    words = " ".join(re.findall(r">([^<>]+)</text>", svg))
    for bad in ("Use not on the label", "Came back at Th4", "Disease at Th4", "by country"):
        if bad in words:
            err(f"diagram still says {bad!r}")
    for good in ("Hospital platforms (France)", "wherever you live", "Off-label use", "A use not listed on the label",
                 "Cancer came back in the spine (Th4 vertebra)"):
        if good not in words:
            err(f"diagram should say {good!r}")
    no_svg = re.sub(r"<svg\b.*?</svg>", "", html, flags=re.S)
    if "a use not listed on the label" not in no_svg.lower():
        err("off-label explanation must reuse wording already on the page")
    if re.search(r"(?i)not organised by country|countries are ignored", no_svg):
        err("page text suggests countries are ignored")
    ok("diagram wording: plain labels, countries kept, off-label explained")


def test_diagram_hygiene() -> None:
    html = INDEX.read_text(encoding="utf-8")
    svg = " ".join(re.findall(r"<svg\b.*?</svg>", html, re.S))
    if re.search(r"#(f[0-9a-f]8[0-9a-f]{3}|ff[6-9a-c][0-9a-f]{3}|e[6-9a-f]7[0-9a-f]2[0-9a-f])\b", svg, re.I) or re.search(r"\borange\b", svg, re.I):
        err("orange-ish colour inside a diagram")
    words = " ".join(re.findall(r">([^<>]+)</text>", svg)).lower()
    for w in ("opened", "unverified", "commenter", "ais helped", "kilo code"):
        if w in words:
            err(f"verification chatter in diagram text: {w!r}")
    for w in ("best", "top-ranked", "you should take", "recommended for you"):
        if w in words:
            err(f"ranking/advice wording in diagram text: {w!r}")
    if re.search(r"<text\b(?![^>]*data-bg=)[^>]*>", svg):
        err("an svg <text> lacks data-bg (contrast gate cannot measure it)")
    ok("diagrams: no orange, no chatter, no ranking words, every label measurable")


def main() -> int:
    if not INDEX.is_file():
        err("site/index.html is missing — run scripts/build_site.py")
        print("FAIL")
        return 1
    test_front_door()
    test_each_step()
    test_matching_links_drug_pages()
    test_where_to_start()
    test_sid_example()
    test_gpt35_and_newer_evidence()
    test_no_verification_chatter()
    test_readability()
    test_identity()
    test_diagrams()
    test_sid_timeline_dates()
    test_diagram_wording()
    test_diagram_hygiene()
    if errors:
        print(f"\n{len(errors)} FAIL(S)")
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
