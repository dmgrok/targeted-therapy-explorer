#!/usr/bin/env python3
"""Front-door steps page: the usual process, static AI explainers, official lists.

This writes site/index.html. The decision-tree drug pages live at
options/index.html and are linked from the matching step. There is no live
AI, no form, no patient data, and no ranking. Countries are not an organising
axis: one shared path, with official FR/CH/EU lists in "Where to start looking".
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_mockup import (  # noqa: E402
    CLOSED_LIST,
    crumbs,
    esc,
    page_shell,
    sources_block,
    write,
    SITE,
)
from build_site import DISCLAIMER_SHORT, fmt_date  # noqa: E402

# Opened dates, Europe/Paris (UTC+1). Official process and directory pages,
# and the 2023 JAMA / NCI / Sid pages, were opened or re-opened 13 Nov 2026.
# The 2024 JAMA Network Open paper was opened 14 Nov 2026.
OPENED_13 = "Opened 13 November 2026 (Europe/Paris)"
OPENED_13_RE = "Re-opened 13 November 2026 (Europe/Paris)"
OPENED_14 = "Opened 14 November 2026 (Europe/Paris)"

# Official and cited URLs. Only pages that were actually opened.
URL = {
    "nci_biomarker": "https://www.cancer.gov/about-cancer/treatment/types/biomarker-testing-cancer-treatment",
    "nci_pathology": "https://www.cancer.gov/about-cancer/diagnosis-staging/diagnosis/pathology-reports-fact-sheet",
    "nci_finding": "https://www.cancer.gov/about-cancer/managing-care/finding-cancer-care",
    "esmo_pcm": "https://dam.esmo.org/image/upload/ESMO-Patient-Guide-Personalised-Cancer-Medicine.pdf",
    "esmo_advanced": "https://dam.esmo.org/image/upload/v1737536221/EN%20%7C%20A%20Guide%20for%20Patients%20with%20Advanced%20Cancer.pdf",
    "esmo_mtb": "https://www.annalsofoncology.org/article/S0923-7534(25)00080-8/fulltext",
    "inca_rcp": "https://www.cancer.fr/professionnels-de-sante/parcours-de-soins-des-patients/la-reunion-de-concertation-pluridisciplinaire",
    "inca_platforms": "https://www.cancer.fr/professionnels-de-sante/parcours-de-soins-des-patients/traitements/traitements-medicamenteux/les-therapies-ciblees/les-plateformes-de-genetique-moleculaire-des-cancers/missions-et-localisation-des-plateformes",
    "inca_rare": "https://www.cancer.fr/professionnels-de-sante/l-organisation-de-l-offre-de-soins/organisation-des-soins-pour-les-cancers-rares",
    "inca_rare_centres": "https://www.cancer.fr/professionnels-de-sante/l-organisation-de-l-offre-de-soins/organisation-des-soins-pour-les-cancers-rares/une-organisation-en-centres-de-reference-et-de-competences",
    "inca_trials": "https://www.cancer.fr/professionnels-de-la-recherche/nos-actions-de-recherche/recherche-clinique/le-registre-des-essais-cliniques",
    "ansm_aac": "https://ansm.sante.fr/qui-sommes-nous/nos-missions/faciliter-lacces-a-linnovation-therapeutique/p/encadrer-lacces-precoce-aux-produits-de-sante",
    "has_aap": "https://has-sante.fr/jcms/r_1500918/fr/acces-precoce-a-un-medicament",
    "ema_cu": "https://www.ema.europa.eu/en/human-regulatory-overview/research-development/compassionate-use",
    "euracan": "https://www.euracan.eu/patients/how-euracan-helps-you",
    "krebsliga": "https://www.krebsliga.ch/beratung-unterstuetzung/qualitaet-in-der-behandlung/",
    "swiss_institute": "https://www.swisscancerinstitute.ch/en/for-patients/",
    "humres": "https://www.humanforschung-schweiz.ch/en/",
    "kofam": "https://www.kofam.ch/",
    "ctis": "https://euclinicaltrials.eu/search-for-clinical-trials",
    "eu_ctr": "https://www.clinicaltrialsregister.eu/ctr-search/search",
    "ctg": "https://www.clinicaltrials.gov/",
    "nci_chatbots": "https://www.cancer.gov/news-events/cancer-currents-blog/2023/chatbots-answer-cancer-questions",
    "jama_2023": "https://jamanetwork.com/journals/jamaoncology/fullarticle/2808731",
    "jama_2024": "https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2825235",
    "forum": "https://forum.openai.com/public/videos/event-replay-from-terminal-to-turnaround-how-gitlabs-co-founder-leveraged-chatgpt-in-his-cancer-fight-2026-03-18",
    "academy": "https://academy.openai.com/public/blogs/sid-sijbrandij-chatgpt-cancer-research",
    "sytse": "https://sytse.com/cancer/",
    "substack": "https://sijbrandij.substack.com/p/im-going-founder-mode-on-my-cancer",
    "osteosarc": "https://osteosarc.com/",
}


def src_item(href: str, label: str, note: str) -> str:
    return (
        f'<li><a href="{esc(href)}">{esc(label)}</a>. {esc(note)}</li>'
    )


def src_block(items: list[str], summary: str = "Sources for this step") -> str:
    inner = "<ul class='source-dates'>" + "".join(items) + "</ul>"
    return sources_block(inner, summary)


def ai_box(step_id: str, help_text: str, limit_text: str) -> str:
    hid = f"ai-{step_id}"
    return (
        f'<aside class="ai-explainer" aria-labelledby="{esc(hid)}">'
        f'<h3 id="{esc(hid)}">How AI can help — and its limits</h3>'
        f"<p>{help_text}</p>"
        f"<p>{limit_text}</p>"
        "</aside>"
    )


def step(step_id: str, number: int, title: str, body: str, help_text: str, limit_text: str, sources: list[str]) -> str:
    return (
        f'<section class="path-step" id="{esc(step_id)}">'
        f'<p class="path-step-num">Step {number} of 7</p>'
        f"<h2>{esc(title)}</h2>"
        + body
        + ai_box(step_id, help_text, limit_text)
        + src_block(sources)
        + "</section>"
    )


def drug_pages_panel() -> str:
    cards = []
    for label, _ready, bid in CLOSED_LIST:
        cards.append(
            f'<li><a class="choice bm-ready" href="b/{esc(bid)}/index.html">'
            f'<span class="choice-name">{esc(label)}</span>'
            f'<span class="choice-n">Open the decision tree</span>'
            "</a></li>"
        )
    return (
        '<div class="drug-pages-panel" id="drug-pages">'
        "<h3>The drug pages</h3>"
        "<p>The drug pages digest public labels: what a medicine is authorised "
        "for, in which cancer and marker, in the EU and the US. They are not a "
        "recommendation. They sit to one side of this path. Use them with your "
        "care team after a molecular result.</p>"
        '<p><a class="choice choice-cta" href="options/index.html">'
        '<span class="choice-name">Open the drug pages</span>'
        '<span class="choice-n">Choose a gene finding and walk the decision tree</span>'
        "</a></p>"
        '<ul class="choices home-choices">'
        + "".join(cards)
        + "</ul>"
        "</div>"
    )


def place(name: str, href: str, body: str, note: str) -> str:
    return (
        "<li>"
        f'<p class="place-name"><a href="{esc(href)}">{esc(name)}</a></p>'
        f"<p>{body}</p>"
        + (f'<p class="fine">{note}</p>' if (note or "").strip() else "")
        + "</li>"
    )


def where_to_start() -> str:
    testing = [
        place(
            "ERN EURACAN",
            URL["euracan"],
            "An EU network for rare adult solid cancers. It describes how it can help patients.",
            "EU.",
        ),
        place(
            "INCa plateformes de génétique moléculaire",
            URL["inca_platforms"],
            "France’s national cancer institute describes hospital platforms that run molecular tests. The directory on that page is from 2020 and can change.",
            "France. Page dated 11 February 2022; directory from 2020.",
        ),
        place(
            "INCa rare-cancer networks",
            URL["inca_rare"],
            "France’s rare-cancer networks include an expert tumour board. A related centre list seen on a companion page is dated March 2020 and can change. "
            f'<a href="{esc(URL["inca_rare_centres"])}">Centres de référence et de compétences</a>.',
            "France. Page dated 24 November 2024.",
        ),
        place(
            "Swiss Cancer League Q-Label",
            URL["krebsliga"],
            "A quality label. A tumour board is one criterion. This label is for breast centres only.",
            "Switzerland.",
        ),
    ]
    access = [
        place(
            "ANSM accès compassionnel (AAC)",
            URL["ansm_aac"],
            "A named-patient compassionate-access route in France, run by ANSM.",
            "France.",
        ),
        place(
            "EMA compassionate use",
            URL["ema_cu"],
            "The European Medicines Agency describes compassionate use. Member States run the programmes.",
            "EU.",
        ),
        place(
            "HAS accès précoce (AAP)",
            URL["has_aap"],
            "An early-access route in France, run by HAS. The page lists four conditions. It was updated on 1 September 2026.",
            "France. Updated 1 September 2026.",
        ),
    ]
    trials = [
        place(
            "ClinicalTrials.gov",
            URL["ctg"],
            "The U.S. public trial registry. Many studies that open in Europe are also listed here.",
            "",
        ),
        place(
            "EU Clinical Trials Information System (CTIS)",
            URL["ctis"],
            "The EU’s current public trial finder. Trials under Regulation 536/2014 are listed here.",
            "EU.",
        ),
        place(
            "EU Clinical Trials Register",
            URL["eu_ctr"],
            "The older EudraCT register. Newer trials under the 2014 regulation are on CTIS.",
            "EU.",
        ),
        place(
            "INCa registre des essais cliniques",
            URL["inca_trials"],
            "France’s national cancer institute trial register.",
            "France.",
        ),
        place(
            "Swiss Cancer Institute",
            URL["swiss_institute"],
            "A Swiss research organisation, formerly SAKK. Its patient page describes studies.",
            "Switzerland.",
        ),
        place(
            "Swiss HumRes",
            URL["humres"],
            "Switzerland’s public search for human research studies. kofam.ch redirects here.",
            "Switzerland.",
        ),
    ]
    place_sources = [
        src_item(URL["euracan"], "ERN EURACAN, How EURACAN helps you", f"EU. {OPENED_13}."),
        src_item(URL["inca_platforms"], "INCa, Plateformes de génétique moléculaire des cancers", f"France. 11 February 2022; directory from 2020. {OPENED_13}."),
        src_item(URL["inca_rare"], "INCa, Organisation des soins pour les cancers rares", f"France. 24 November 2024. {OPENED_13}."),
        src_item(URL["inca_rare_centres"], "INCa, Centres de référence et de compétences", f"France. Centre list seen dated March 2020. {OPENED_13}."),
        src_item(URL["krebsliga"], "Krebsliga, Qualität in der Behandlung (Q-Label)", f"Switzerland. Breast centres. {OPENED_13}."),
        src_item(URL["ansm_aac"], "ANSM, Encadrer l’accès précoce aux produits de santé", f"France. {OPENED_13}."),
        src_item(URL["ema_cu"], "EMA, Compassionate use", f"EU. {OPENED_13}."),
        src_item(URL["has_aap"], "HAS, Accès précoce à un médicament", f"France. Updated 1 September 2026. {OPENED_13}."),
        src_item(URL["ctg"], "ClinicalTrials.gov", f"{OPENED_13}."),
        src_item(URL["ctis"], "EU Clinical Trials Information System (CTIS)", f"EU. {OPENED_13}."),
        src_item(URL["eu_ctr"], "EU Clinical Trials Register", f"EU. {OPENED_13}."),
        src_item(URL["inca_trials"], "INCa, Registre des essais cliniques", f"France. {OPENED_13}."),
        src_item(URL["swiss_institute"], "Swiss Cancer Institute, For patients", f"Switzerland. {OPENED_13}."),
        src_item(URL["humres"], "HumRes, Swiss human research study search", f"Switzerland. {OPENED_13}."),
        src_item(URL["kofam"], "kofam.ch", f"Redirect to HumRes observed 13 November 2026. {OPENED_13}."),
    ]
    return (
        '<section class="places" id="where-to-start">'
        "<h2>Where to start looking</h2>"
        "<p>These are official public lists for France, Switzerland and the EU. "
        "They are grouped by type of place, then listed A to Z. "
        "<strong>That order is not a ranking.</strong> "
        "This page does not recommend one place over another. "
        "Some directories are older than 2024 and can change. "
        "Check the live official page.</p>"
        '<div class="places-group">'
        "<h3>Testing and expert networks</h3>"
        '<ul class="places-list">' + "".join(testing) + "</ul>"
        "</div>"
        '<div class="places-group">'
        "<h3>Early and compassionate access</h3>"
        '<ul class="places-list">' + "".join(access) + "</ul>"
        "</div>"
        '<div class="places-group">'
        "<h3>Trial finders</h3>"
        '<ul class="places-list">' + "".join(trials) + "</ul>"
        "</div>"
        '<p class="chict-mention" id="chict-mention">China also has a trial registry, ChiCTR. '
        "This site mentions it only. It is not used here as a search tool.</p>"
        + src_block(place_sources, "Sources for these lists")
        + "</section>"
    )


def sid_example() -> str:
    q1 = (
        "After I ran out of standard-of-care treatment options and there were "
        "no trials available for me, I started doing maximum diagnostics, "
        "created new treatments, started doing treatments in parallel, and "
        "began scaling this for others."
    )
    q3 = "I’m not gonna trust this out of the box, it can certainly make mistakes."
    q4 = "I currently have no evidence of disease."
    q5 = "But my fight with cancer is far from over."
    return (
        '<section class="sid-example" id="sid-sijbrandij">'
        "<h2>One person’s story: Sid Sijbrandij</h2>"
        '<div class="case-banner" role="note">'
        "<strong>This is one person’s story, not evidence that a treatment works.</strong> "
        "It is not medical advice, a recommendation, or a ranking. "
        "The people on these pages are not options in the tables. "
        "This is n=1, not a template to copy."
        "</div>"
        "<p>Sid Sijbrandij has bone cancer, called osteosarcoma, in the spine. "
        "A longer telling, with a timeline, is on his "
        '<a href="cases/sijbrandij.html">case study page</a>.</p>'
        "<h3>In his own words</h3>"
        '<blockquote class="case-quote"><p>'
        + esc(q1)
        + "</p>"
        '<footer>Per his <a href="' + esc(URL["sytse"]) + '">cancer page</a>.</footer></blockquote>'
        "<p>In an OpenAI Forum talk, posted 18 March 2026, he said AI tools "
        "helped them work through enormous amounts of data and navigate new treatments. "
        "The talk describes ChatGPT, then expert review. A collaborator, Jacob Stern, "
        "said there, of a custom agent harness: "
        "“" + esc(q3) + "”</p>"
        '<p class="fine">Per the <a href="' + esc(URL["forum"]) + '">OpenAI Forum on-page transcript</a>, '
        "posted 18 March 2026.</p>"
        '<blockquote class="case-quote"><p>'
        + esc(q4)
        + "</p><p>"
        + esc(q5)
        + "</p>"
        '<footer>Per his <a href="' + esc(URL["substack"]) + '">Substack post of 20 January 2026</a>.</footer></blockquote>'
        "<p><strong>As of 20 January 2026, per his Substack post.</strong></p>"
        "<p>The pattern worth taking is speed of digestion, under the care team. "
        "It is never a system that chooses treatment.</p>"
        + src_block(
            [
                src_item(URL["sytse"], "sytse.com/cancer", f"Sid Sijbrandij’s own page. {OPENED_13_RE}."),
                src_item(URL["forum"], "OpenAI Forum talk and on-page transcript", f"Posted 18 March 2026. {OPENED_13_RE}."),
                src_item(URL["substack"], "Substack, “I’m going Founder Mode on my cancer”", f"20 January 2026. {OPENED_13_RE}."),
                src_item(URL["osteosarc"], "osteosarc.com", f"Homepage text. {OPENED_13}. No AI-use description in that text."),
                src_item(URL["academy"], "OpenAI Academy article", f"6 August 2026. Published by OpenAI, so not independent. {OPENED_13_RE}. Not used for quotes."),
            ],
            "Sources for this example",
        )
        + "</section>"
    )


def ai_limits() -> str:
    return (
        '<section class="ai-limits" id="ai-limits">'
        "<h2>Limits on every AI use</h2>"
        "<p>The figures in this first paragraph are from "
        "<strong>2023 studies of GPT-3.5, an older model</strong>. "
        "They may not describe current tools.</p>"
        "<p>A <a href=\"" + esc(URL["jama_2023"]) + "\">JAMA Oncology letter</a>, "
        "published online 24 August 2023, found chatbot responses "
        "“hallucinated (ie, were not part of any recommended treatment) in 13 of 104 (12.5%) outputs,” "
        "and that “one-third of treatments recommended by the chatbot were at least partially "
        "nonconcordant with NCCN guidelines.” "
        "The authors wrote: “Clinicians should advise patients that LLM chatbots are not a "
        "reliable source of treatment information.” "
        "NCI, on 3 October 2023, quoted the lead author: chatbots can "
        "“seamlessly combine correct and incorrect treatment recommendations, making it "
        "difficult even for experts to detect the errors.” "
        "Those studies used GPT-3.5 and peers.</p>"
        "<p>A later, peer-reviewed study was published on 23 October 2024 in "
        '<a href="' + esc(URL["jama_2024"]) + '">JAMA Network Open</a>. '
        "It tested 10 chatbots, including later models, on 79 clinical oncology cases. "
        "On multiple-choice questions, the best score was 57 out of 79 (72%). "
        "On free-text answers, which are closer to a real conversation, the best score "
        "was 30 out of 79 (38%). "
        "Nine of the 10 chatbots, including all three that could read images, scored "
        "lower on free-text than on multiple-choice. "
        "The authors wrote that more work is needed to improve reliability in oncology. "
        "doi:10.1001/jamanetworkopen.2024.37711.</p>"
        "<p>Do not paste identifiable records into a public tool. "
        "This site has no forms that collect anything, and no live AI in this version.</p>"
        + src_block(
            [
                src_item(URL["jama_2023"], "JAMA Oncology, “Use of Artificial Intelligence Chatbots for Cancer Treatment Information”", f"Published online 24 August 2023. {OPENED_13_RE}."),
                src_item(URL["nci_chatbots"], "NCI Cancer Currents, “Can Artificial Intelligence–Driven Chatbots Correctly Answer Questions about Cancer?”", f"3 October 2023, Edward Winstead. {OPENED_13_RE}."),
                src_item(URL["jama_2024"], "JAMA Network Open, “Performance of Multimodal Artificial Intelligence Chatbots Evaluated on Clinical Oncology Cases”", f"Published 23 October 2024. doi:10.1001/jamanetworkopen.2024.37711. {OPENED_14}."),
            ],
            "Sources for these limits",
        )
        + "</section>"
    )


def how_we_checked() -> str:
    """Verification notes for this page: not part of the reader-facing body."""
    transcript = (
        "emphasize along the way how AIS helped us work through enormous "
        "amounts of data and navigate new treatments."
    )
    return (
        '<details class="sources-toggle how-we-checked" id="how-we-checked">'
        "<summary>How we checked</summary>"
        '<div class="sources-body">'
        "<p>Official process and directory pages were opened on 13 November 2026 "
        "(Europe/Paris). High confidence for the steps and those lists. "
        "Medium confidence for how widely a separate molecular tumour board is "
        "used outside France. Some official directories are older than 2024 "
        "and can change. The NCI biomarker-testing page was last updated on "
        "14 December 2021; its wording that testing “is not yet part of routine "
        "care for most patients” may be dated.</p>"
        "<p>The 2023 JAMA Oncology letter and the NCI Cancer Currents commentary "
        "were re-opened on 13 November 2026. The 2024 JAMA Network Open study "
        f"was opened on 14 November 2026 (Europe/Paris). {OPENED_14}.</p>"
        "<p>No official privacy page for consumer chatbots was opened for this work, "
        "which is why this page says not to paste identifiable records into a "
        "public tool.</p>"
        "<p>ChiCTR is mentioned only. It was not opened as a working finder for "
        "this page. A redirect from kofam.ch to Swiss HumRes was observed on "
        "13 November 2026.</p>"
        "<h3>Sid Sijbrandij’s story</h3>"
        "<p>Quotes on this page are only from pages opened or re-opened on "
        "13 November 2026. The OpenAI Forum on-page transcript, posted 18 March 2026, "
        "reads: “" + esc(transcript) + "” "
        "“AIS” looks like a transcript typing slip, so the visible page "
        "paraphrases that part and does not print it as his words.</p>"
        "<p>His Substack post of 20 January 2026, in his own text, does not "
        "mention ChatGPT. A commenter mentioned “AI, Kilo”; that is not Sid. "
        "The osteosarc.com homepage, as opened, did not describe AI use. "
        "No page opened for this work shows him saying he used Kilo Code for "
        "his cancer work. He and Stern describe ChatGPT and a custom harness. "
        "This page does not claim Kilo Code as his cancer tool. "
        "An OpenAI Academy article about him, dated 6 August 2026, was published "
        "by OpenAI, so it is not an independent source. It was re-opened the "
        "same day and is not used here for quotes. The pages opened for this "
        "work do not spell out, in his own words, how he used any AI tool, "
        "beyond what is quoted or paraphrased on this page.</p>"
        "</div>"
        "</details>"
    )


def page_body() -> str:
    diagnosis = step(
        "step-diagnosis",
        1,
        "Diagnosis and pathology",
        "<p>A pathologist studies tissue from a biopsy or from surgery. "
        "Their report is the definitive diagnosis. You can ask to discuss "
        "the report with your doctor.</p>",
        "AI can turn hard words into a short glossary. It can help you list questions for the visit.",
        "It must not interpret the report before your doctor has seen it.",
        [
            src_item(URL["nci_pathology"], "NCI, Pathology reports", f"Reviewed 8 August 2022. {OPENED_13}."),
        ],
    )
    testing = step(
        "step-testing",
        2,
        "Molecular testing",
        "<p>Doctors can test tumour tissue, or a blood sample (a liquid biopsy), "
        "for gene and protein markers. In France, national hospital platforms "
        "run many of these tests. A result is a snapshot. It may point to a drug, "
        "a trial, or neither. The decision is with your care team.</p>",
        "AI can explain types of tests. It can help you prepare questions.",
        "It must not predict a result. It must not match a person to a drug.",
        [
            src_item(URL["nci_biomarker"], "NCI, Biomarker testing for cancer treatment", f"Page last updated 14 December 2021. {OPENED_13}."),
            src_item(URL["inca_platforms"], "INCa, Plateformes de génétique moléculaire des cancers", f"11 February 2022; directory from 2020. {OPENED_13}."),
        ],
    )
    second = step(
        "step-second-opinion",
        3,
        "Second opinion",
        "<p>Asking for a second opinion is common. France’s national cancer "
        "institute calls it an important step. You can take your reports and "
        "questions to another specialist.</p>",
        "AI can help you organise reports and questions.",
        "AI is not a second opinion. It must not pick a doctor for you.",
        [
            src_item(URL["nci_finding"], "NCI, Finding cancer care", f"Last updated 28 August 2024. Includes second opinion. {OPENED_13}."),
            src_item(URL["inca_rcp"], "INCa, La réunion de concertation pluridisciplinaire", f"25 July 2025. {OPENED_13}."),
        ],
    )
    board = step(
        "step-tumour-board",
        4,
        "Tumour board",
        "<p>In many centres, a group of specialists meets to discuss a person’s file. "
        "This is a tumour board. In France it is called a réunion de concertation "
        "pluridisciplinaire, or RCP. Official French guidance says every person "
        "with cancer should have their file presented when treatment starts or changes.</p>"
        "<p>In Switzerland, a quality label for breast centres requires a tumour board. "
        "That label is for breast centres only. Some centres also hold a molecular "
        "review of gene-test results. France’s rare-cancer networks include an expert "
        "board. An ESMO patient guide from 2011, which is dated, calls a tumour board "
        "common in many centres. This page links to professional recommendations. "
        "It does not copy them.</p>",
        "AI can explain what the meeting is for.",
        "It must not second-guess the board. It must not take the place of a molecular review.",
        [
            src_item(URL["inca_rcp"], "INCa, La réunion de concertation pluridisciplinaire", f"25 July 2025. {OPENED_13}."),
            src_item(URL["krebsliga"], "Krebsliga, Qualität in der Behandlung (Q-Label)", f"Breast centres. {OPENED_13}."),
            src_item(URL["inca_rare"], "INCa, Organisation des soins pour les cancers rares", f"24 November 2024. {OPENED_13}."),
            src_item(URL["esmo_advanced"], "ESMO, A guide for patients with advanced cancer", f"2011 — dated; tumour-board wording. {OPENED_13}."),
            src_item(URL["esmo_mtb"], "ESMO, molecular tumour board recommendations", f"Linked, not reproduced. {OPENED_13}."),
        ],
    )
    matching_body = (
        "<p>A gene-test result may point to an approved drug, a use not listed "
        "on the label, or a clinical trial. The decision is made with the treating "
        "doctor. This site’s drug pages sit at this step. They are general "
        "information from public sources. They are not a recommendation.</p>"
        + drug_pages_panel()
    )
    matching = step(
        "step-matching",
        5,
        "Matching to options or trials",
        matching_body,
        "AI can summarise an official trial record as it stands.",
        "It must not declare that a person is eligible for a trial or a drug.",
        [
            src_item(URL["nci_biomarker"], "NCI, Biomarker testing for cancer treatment", f"Page last updated 14 December 2021. {OPENED_13}."),
            src_item(URL["ctg"], "ClinicalTrials.gov", f"{OPENED_13}."),
        ],
    )
    monitoring = step(
        "step-monitoring",
        6,
        "Monitoring and re-testing",
        "<p>Other markers can follow cancer during and after treatment. Markers "
        "can change. If the cancer comes back, the team may want to test again.</p>",
        "AI can help you list questions for a follow-up visit.",
        "It must not read a scan or a lab file and declare news. It must not advise a new biopsy.",
        [
            src_item(URL["nci_biomarker"], "NCI, Biomarker testing for cancer treatment", f"Page last updated 14 December 2021. {OPENED_13}."),
            src_item(URL["inca_platforms"], "INCa, Plateformes de génétique moléculaire des cancers", f"11 February 2022. {OPENED_13}."),
        ],
    )
    access = step(
        "step-access",
        7,
        "Access routes",
        "<p>Some medicines can be reached before a full authorisation, under official "
        "early-access or compassionate-use rules. In France, accès précoce (AAP) is "
        "run by HAS, with four stated conditions. Accès compassionnel (AAC) is a "
        "named-patient route run by ANSM. In the EU, the EMA describes compassionate "
        "use, which Member States run. Public trial finders are listed in "
        '<a href="#where-to-start">Where to start looking</a>.</p>',
        "AI can say which kind of route a public record describes. It can point to the official page.",
        "It must not say that a person qualifies.",
        [
            src_item(URL["has_aap"], "HAS, Accès précoce à un médicament", f"Updated 1 September 2026. {OPENED_13}."),
            src_item(URL["ansm_aac"], "ANSM, Encadrer l’accès précoce aux produits de santé", f"{OPENED_13}."),
            src_item(URL["ema_cu"], "EMA, Compassionate use", f"{OPENED_13}."),
        ],
    )
    return (
        "<h1>Steps people take today for personalised cancer treatment</h1>"
        '<p class="lede">Each step has a short explanation, a static box on how AI '
        "can help you digest this and what it must not do, and sources. "
        "This is one shared path. It is not organised by country.</p>"
        '<p class="confidence-line" id="confidence">Some figures come from studies of older AI models; dates are shown with each source.</p>'
        '<section id="process">'
        "<h2>The process</h2>"
        "<p>Personalised cancer care uses tests on the tumour’s genes, proteins "
        "and other markers. The aim is to choose a treatment more likely to help. "
        "The U.S. National Cancer Institute (NCI) says biomarker testing is already "
        "routine to select treatment in some cancers. It names non-small cell lung "
        "cancer, breast cancer and colorectal cancer. The same page says this "
        "“is not yet part of routine care for most patients.” That page was last "
        "updated on 14 December 2021. A result is a snapshot.</p>"
        + src_block(
            [
                src_item(URL["nci_biomarker"], "NCI, Biomarker testing for cancer treatment", f"Page last updated 14 December 2021. {OPENED_13}."),
                src_item(URL["esmo_pcm"], "ESMO, Personalised Cancer Medicine: a guide for patients", f"2013 — dated; used for definition only. {OPENED_13}. Linked, not reproduced as guideline content."),
            ],
            "Sources for this introduction",
        )
        + "</section>"
        + diagnosis
        + testing
        + second
        + board
        + matching
        + monitoring
        + access
        + ai_limits()
        + where_to_start()
        + sid_example()
        + how_we_checked()
        + '<p class="fine">This site does not reproduce NCCN or ESMO guideline content. '
        "Where a professional document is named, it is linked. "
        f'{esc(DISCLAIMER_SHORT)}</p>'
    )


def merged_notice(snap: dict) -> str:
    """One short notice: not medical advice, plus a link to the full notice page."""
    return (
        '<div class="notice notice-short" role="note">'
        f"<strong>{esc(DISCLAIMER_SHORT)}</strong> "
        "This page is general information about a common path and official "
        "places to start looking, for use with your care team. It is not a "
        "diagnosis, a treatment recommendation, or a care plan. There is no "
        "live AI on this site, and no collection of patient data. "
        "Data is a snapshot as of "
        f'<time datetime="{esc(snap["snapshotDate"])}">{esc(fmt_date(snap["snapshotDate"]))}</time>. '
        '<a href="notice.html">Full notice</a>.'
        "</div>"
    )


def write_steps(snap: dict) -> None:
    write(
        SITE / "index.html",
        page_shell(
            "Steps for personalised cancer treatment — Targeted Therapy Explorer",
            0,
            snap,
            page_body(),
            crumbs([("index.html", "Home")], 0),
            full_notice=False,
            custom_notice=merged_notice(snap),
        ),
    )


def main() -> int:
    import json

    snap = json.loads((ROOT / "data" / "snapshot.json").read_text(encoding="utf-8"))
    write_steps(snap)
    print(f"Wrote steps front door to {SITE / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
