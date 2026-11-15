#!/usr/bin/env python3
"""Practical access: one shared path, and investigational mRNA cancer vaccines.

Public sources only. No patient data, no form, no trial-registry records.
Registry links are the registry page only. Figures below are the ones
supplied for this page; nothing else is added.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_mockup import SITE, crumbs, esc, page_shell, write  # noqa: E402
from build_site import DISCLAIMER_SHORT, fmt_date  # noqa: E402

CHECKED = "Last checked 15 Nov 2026"

URL = {
    "nci_centers": "https://www.cancer.gov/research/infrastructure/cancer-centers/find",
    "inca_platforms": (
        "https://www.cancer.fr/professionnels-de-sante/parcours-de-soins-des-patients/"
        "traitements/traitements-medicamenteux/les-therapies-ciblees/"
        "les-plateformes-de-genetique-moleculaire-des-cancers/"
        "missions-et-localisation-des-plateformes"
    ),
    "nhs_cvlp": "https://www.southampton.ac.uk/ctu/cancer-vaccine-launch-pad.page",
    "nhs_directory": "https://www.england.nhs.uk/genomics/the-national-genomic-test-directory/",
    "pfmg_cancer": "https://pfmg2025.fr/patients-et-famille/la-medecine-genomique-appliquee-aux-cancers/",
    "pfmg_home": "https://pfmg2025.fr/",
    "ctg": "https://clinicaltrials.gov",
    "who_search": "https://trialsearch.who.int",
    "who_tool": "https://www.who.int/tools/clinical-trials-registry-platform",
    "ctis": "https://euclinicaltrials.eu/search-for-clinical-trials",
    "rojas": "https://www.nature.com/articles/s41586-023-06063-y",
    "long": "https://www.nejm.org/doi/full/10.1056/NEJMoa2609762",
    "merck": (
        "https://www.merck.com/news/merck-and-moderna-will-present-results-from-landmark-phase-3-"
        "interpath-001-trial-for-intismeran-autogene-plus-keytruda-pembrolizumab-at-esmo-2026-"
        "presidential-symposium/"
    ),
    "biontech": (
        "https://www.biontech.com/int/en/home/mediaroom/news/statements/2026/08/"
        "BioNTech-Provides-Update-on-Phase-2-Clinical-Trial-of-Autogene-Cevumeran-"
        "in-Resected-Colorectal-Cancer.html"
    ),
    "nct_interpath": "https://clinicaltrials.gov/study/NCT05933577",
    "nct_imcode": "https://clinicaltrials.gov/study/NCT05968326",
    "nct_bnt": "https://clinicaltrials.gov/study/NCT04486378",
}

# label, date or other source detail, note appended on the list only
SOURCES = [
    ("nci_centers", "NCI-Designated Cancer Centers finder", "Updated 10 June 2026", ""),
    (
        "inca_platforms",
        "INCa and DGOS molecular-genetics platforms",
        "Page dated 11 Feb 2022. Directory 2020",
        "The page lists 28 hospital platforms. It is not shown here as a current list.",
    ),
    (
        "nhs_cvlp",
        "NHS Cancer Vaccine Launch Pad",
        "",
        "A national study funded and sponsored by NHS England. It refers people to trials. It is not a licensed treatment.",
    ),
    (
        "nhs_directory",
        "NHS National Genomic Test Directory",
        "",
        "",
    ),
    (
        "pfmg_cancer",
        "PFMG 2025 cancer page",
        "",
        "Short paraphrase only. PFMG content is not openly licensed.",
    ),
    (
        "pfmg_home",
        "PFMG 2025, preindications and LBM-FMG labs",
        "",
        "",
    ),
    ("ctg", "ClinicalTrials.gov", "Registry home", "Link only. No trial record is copied."),
    (
        "who_search",
        "WHO ICTRP search",
        "Registry search",
        "WHO ICTRP terms bar marketing, promotional or commercial reuse. No trial record is copied.",
    ),
    (
        "who_tool",
        "WHO ICTRP",
        "Registry page",
        "WHO ICTRP terms bar marketing, promotional or commercial reuse. No trial record is copied.",
    ),
    ("ctis", "EU CTIS search", "Registry search", "Link only. No trial record is copied."),
    ("rojas", "Rojas et al., Nature", "10 May 2023", "Phase 1 trial benchmark. Not a country average."),
    (
        "long",
        "Long et al., NEJM",
        "Published 11 Nov 2026",
        "Funded by MSD and Moderna.",
    ),
    (
        "merck",
        "Merck and Moderna release",
        "22 Oct 2026",
        "Still calls intismeran autogene investigational. Overall survival is not mature.",
    ),
    (
        "biontech",
        "BioNTech statement",
        "28 Aug 2026",
        "Colorectal Phase 2 BNT122-01.",
    ),
    (
        "nct_interpath",
        "NCT05933577",
        "Registry page only",
        "No trial record is copied.",
    ),
    (
        "nct_imcode",
        "NCT05968326",
        "Registry page only",
        "No trial record is copied.",
    ),
    (
        "nct_bnt",
        "NCT04486378",
        "Registry page only",
        "No trial record is copied. A registry status may lag a sponsor statement.",
    ),
]


def link(key: str, label: str) -> str:
    return f'<a href="{esc(URL[key])}">{esc(label)}</a>'


def cite(key: str, label: str, detail: str) -> str:
    extra = f" {esc(detail)}." if detail else ""
    return (
        f'<p class="fine">Source: {link(key, label)}.{extra} {esc(CHECKED)}.</p>'
    )


def cite_set() -> str:
    """A negative finding across the linked sources, not one new document."""
    return (
        '<p class="fine">Source: <a href="#source-list">the sources linked on this page</a>. '
        f"{esc(CHECKED)}.</p>"
    )


def quote(text: str, footer: str) -> str:
    return (
        '<blockquote class="case-quote"><p>'
        + esc(text)
        + "</p><footer>"
        + footer
        + "</footer></blockquote>"
    )


def care_line() -> str:
    return (
        '<p class="care-line"><span lang="fr">à voir avec l\'équipe soignante.</span> '
        "To discuss with the care team.</p>"
    )


def source_list() -> str:
    items = []
    for key, label, detail, note in SOURCES:
        detail_h = f" {esc(detail)}." if detail else ""
        note_h = f" {esc(note)}" if note else ""
        items.append(
            f"<li>{link(key, label)}.{detail_h}{note_h} {esc(CHECKED)}.</li>"
        )
    return '<ul class="source-dates">' + "".join(items) + "</ul>"


def page_body() -> str:
    find = (
        '<section id="find-a-centre">'
        "<h3>Find a specialist or a centre</h3>"
        "<p>This step starts with the treating team.</p>"
        "<p>Official directories are examples. "
        "The order is not a ranking of countries or centres.</p>"
        "<p>United States. The NCI has a public finder for NCI-Designated Cancer Centers. "
        "The finder was updated on 10 June 2026.</p>"
        + cite("nci_centers", "NCI-Designated Cancer Centers finder", "Updated 10 June 2026")
        + "<p>France. INCa and DGOS describe hospital platforms for molecular genetics. "
        "The page lists 28 hospital platforms. "
        "The page is dated 11 Feb 2022. The directory is from 2020. "
        "It is not a current list.</p>"
        + cite(
            "inca_platforms",
            "INCa and DGOS molecular-genetics platforms",
            "Page dated 11 Feb 2022. Directory 2020",
        )
        + "<p>England. The NHS Cancer Vaccine Launch Pad is a national study. "
        "NHS England funds it and sponsors it. "
        "It refers people to trials. It is not a licensed treatment.</p>"
        + cite("nhs_cvlp", "NHS Cancer Vaccine Launch Pad", "")
        + "<p>England also publishes the NHS National Genomic Test Directory.</p>"
        + cite("nhs_directory", "NHS National Genomic Test Directory", "")
        + "</section>"
    )
    tissue = (
        '<section id="tissue-or-biopsy">'
        "<h3>Tissue or biopsy</h3>"
        "<p>This step starts with the treating team.</p>"
        "<p>The PFMG 2025 cancer page says a new biopsy may be necessary. "
        "It says the doctor discusses it and asks for agreement. "
        "PFMG content is not openly licensed. "
        "The lines above are a short paraphrase, not a copy.</p>"
        + cite("pfmg_cancer", "PFMG 2025 cancer page", "")
        + "<p>The NHS Cancer Vaccine Launch Pad page says unused tissue from a "
        "previous surgery or biopsy is used. "
        "The quote is about the Launch Pad itself.</p>"
        + quote(
            "You will not need to undergo an extra procedure",
            "NHS Cancer Vaccine Launch Pad, for the Launch Pad itself. "
            + link("nhs_cvlp", "NHS Cancer Vaccine Launch Pad")
            + f". {esc(CHECKED)}.",
        )
        + "<p>The same page says people should ask their local hospital team "
        "if they wish to take part.</p>"
        + cite("nhs_cvlp", "NHS Cancer Vaccine Launch Pad", "")
        + care_line()
        + "</section>"
    )
    sequencing = (
        '<section id="sequencing">'
        "<h3>Sequencing</h3>"
        "<p>This step starts with the treating team.</p>"
        "<p>Sequencing uses tumour NGS panels. "
        "Sometimes the test is a whole exome or a whole genome.</p>"
        "<p>In France, this step points to PFMG 2025 preindications and LBM-FMG labs.</p>"
        + cite("pfmg_home", "PFMG 2025", "")
        + "<p>In England, the NHS National Genomic Test Directory uses these words:</p>"
        + quote(
            "outlines the full range of genomic tests that are commissioned for the NHS in England",
            link("nhs_directory", "NHS National Genomic Test Directory")
            + f". {esc(CHECKED)}.",
        )
        + quote(
            "the patients who are eligible.",
            link("nhs_directory", "NHS National Genomic Test Directory")
            + f". {esc(CHECKED)}.",
        )
        + "<p>No wait time is shown. "
        "No comparable official figure was found in the sources linked on this page.</p>"
        + cite_set()
        + "</section>"
    )
    matching = (
        '<section id="interpretation">'
        "<h3>Interpretation and matching</h3>"
        "<p>This step starts with the treating team.</p>"
        "<p>The care team and the molecular review meeting match a result to a trial.</p>"
        "<p>This page links to trial registries only. "
        "It copies no trial record, no count, no status and no location number. "
        "A trial may be named by its registry id, with a link to its registry page.</p>"
        "<ul>"
        f"<li>{link('ctg', 'ClinicalTrials.gov')}</li>"
        f"<li>{link('who_search', 'WHO ICTRP search')} "
        f"and {link('who_tool', 'the WHO ICTRP page')}</li>"
        f"<li>{link('ctis', 'EU CTIS search')}</li>"
        "</ul>"
        "<p>WHO ICTRP terms bar marketing, promotional or commercial reuse.</p>"
        + cite("ctg", "ClinicalTrials.gov", "Registry home")
        + cite("who_search", "WHO ICTRP search", "Registry search")
        + cite("who_tool", "WHO ICTRP", "Registry page")
        + cite("ctis", "EU CTIS search", "Registry search")
        + "</section>"
    )
    reach = (
        '<section id="reach">'
        "<h3>Access, reimbursement and travel</h3>"
        "<p>This step starts with the treating team.</p>"
        "<p>Trial slots and geography shape access. "
        "Manufacturing is made to order.</p>"
        "<p>No personalised mRNA cancer vaccine marketing authorisation was found "
        "in the sources linked on this page. There is no reimbursement table.</p>"
        + cite_set()
        + "<p>One Phase 1 figure is a trial benchmark. It is not a country average. "
        "Rojas et al., Nature, 10 May 2023, report a vaccine produced in ≤6 weeks. "
        "The first dose was ≤9 weeks after surgery.</p>"
        + cite("rojas", "Rojas et al., Nature", "10 May 2023")
        + care_line()
        + "</section>"
    )
    caution = (
        '<div class="case-banner" role="note">'
        "<strong>One setting. One combination. Not an approval.</strong> "
        "Overall survival is not mature. The colorectal trial was stopped. "
        "These products are not ranked."
        "</div>"
    )
    intismeran = (
        '<section id="intismeran">'
        "<h3>Intismeran autogene (V940 / mRNA-4157)</h3>"
        "<p>Merck Sharp &amp; Dohme and Moderna. Investigational.</p>"
        "<p>Phase 3 INTerpath-001 is "
        + link("nct_interpath", "NCT05933577")
        + ". The link is the registry page only.</p>"
        "<p>It is adjuvant intismeran plus pembrolizumab, versus pembrolizumab alone, "
        "after complete resection of stage IIB–IV cutaneous melanoma.</p>"
        + cite("long", "Long et al., NEJM", "Published 11 Nov 2026")
        + "<p>Long et al. published the results in the NEJM on 11 Nov 2026. "
        "MSD and Moderna funded the paper.</p>"
        "<p>1,137 were randomised (757 vs 380). "
        "The written order is intismeran plus pembrolizumab, then pembrolizumab alone.</p>"
        "<p>Median follow-up was 24.6 months.</p>"
        "<p>24-month recurrence-free survival was 82.2% vs 70.0% (two-sided P&lt;0.001), "
        "in that same order.</p>"
        "<p>24-month distant-metastasis-free survival was 88.5% vs 80.2% (P=0.002), "
        "in that same order.</p>"
        "<p>Grade ≥3 adverse events were 23.6% vs 20.3%, in that same order.</p>"
        + cite("long", "Long et al., NEJM", "Published 11 Nov 2026. Funded by MSD and Moderna")
        + "<p>A Merck and Moderna release of 22 Oct 2026 still calls it investigational. "
        "It says overall survival is not mature.</p>"
        + quote(
            "designed and produced using a patient's tumor sample",
            "Merck and Moderna release, 22 Oct 2026. " + link("merck", "Release") + f". {esc(CHECKED)}.",
        )
        + quote(
            "a synthetic mRNA coding for up to 34 neoantigens.",
            "Merck and Moderna release, 22 Oct 2026. " + link("merck", "Release") + f". {esc(CHECKED)}.",
        )
        + cite("merck", "Merck and Moderna release", "22 Oct 2026")
        + "<p>These melanoma figures are one setting and one combination. "
        "They are not an approval. Overall survival is not mature.</p>"
        + "</section>"
    )
    cevumeran = (
        '<section id="cevumeran">'
        "<h3>Autogene cevumeran (BNT122)</h3>"
        "<p>BioNTech and Genentech. Investigational.</p>"
        "<p>A Phase 1 study in pancreatic cancer is in Rojas et al., Nature, 10 May 2023. "
        "Neoantigen selection in that study is bioinformatic neoantigen prediction.</p>"
        + quote(
            "bioinformatically predicted and ranked by immunogenicity",
            "Methods. Rojas et al., Nature, 10 May 2023. "
            + link("rojas", "Nature")
            + f". {esc(CHECKED)}.",
        )
        + "<p>The same paper reports neoantigen-specific T cells in 8 of 16 patients.</p>"
        + cite("rojas", "Rojas et al., Nature", "10 May 2023")
        + "<p>Phase 2 IMcode003, "
        + link("nct_imcode", "NCT05968326")
        + ", is in resected pancreatic cancer. It continues. "
        "The link is the registry page only. No registry fields are copied. "
        "A registry status may lag a sponsor statement.</p>"
        + '<p class="fine">Checked 15 Nov 2026. '
        "No separate source link is added for the word “continues”. "
        "The registry link is the page only.</p>"
        + "<p>On 28 Aug 2026 BioNTech said it had decided to terminate the colorectal "
        "Phase 2 study BNT122-01, "
        + link("nct_bnt", "NCT04486378")
        + ". The data safety monitoring board noted a numerical imbalance in "
        "overall survival between treatment arms.</p>"
        + quote(
            "decided to terminate",
            "BioNTech statement, 28 Aug 2026. " + link("biontech", "Statement") + f". {esc(CHECKED)}.",
        )
        + quote(
            "a numerical imbalance in overall survival between treatment arms",
            "BioNTech statement, 28 Aug 2026, on what the data safety monitoring board noted. "
            + link("biontech", "Statement")
            + f". {esc(CHECKED)}.",
        )
        + cite("biontech", "BioNTech statement", "28 Aug 2026")
        + "<p>A registry status may lag a sponsor statement.</p>"
        + "</section>"
    )
    return (
        "<h1>Practical access</h1>"
        '<p class="lede">One shared path. It is the same for everyone. '
        "It is not a care plan. Each step starts with the treating team. "
        "Country names are examples. This page is not a ranking of treatments, "
        "countries or centres.</p>"
        '<p class="confidence-line">Not medical advice. Talk to your oncologist. '
        f"{esc(CHECKED)}.</p>"
        '<article class="practical-access">'
        "<h2>A common path</h2>"
        + find
        + tissue
        + sequencing
        + matching
        + reach
        + "<h2>Personalised mRNA cancer vaccines today</h2>"
        + '<p><strong>All are investigational.</strong></p>'
        + caution
        + intismeran
        + cevumeran
        + '<section id="false-hope">'
        + "<h3>Read the figures with care</h3>"
        + "<p>One setting. One combination. Not an approval. "
        "Overall survival is not mature. The colorectal trial was stopped.</p>"
        + cite("long", "Long et al., NEJM", "Published 11 Nov 2026")
        + cite("merck", "Merck and Moderna release", "22 Oct 2026")
        + cite("biontech", "BioNTech statement", "28 Aug 2026")
        + "</section>"
        + '<section id="source-list">'
        + "<h2>Sources</h2>"
        + f"<p><strong>{esc(CHECKED)}.</strong></p>"
        + source_list()
        + "</section>"
        + "</article>"
    )


def merged_notice(snap: dict) -> str:
    return (
        '<div class="notice notice-short" role="note">'
        f"<strong>{esc(DISCLAIMER_SHORT)}</strong> "
        "This page is one shared path and a public note. "
        "It is not a care plan, a diagnosis or a treatment recommendation. "
        "It is not a ranking of treatments, countries or centres. "
        "There is no live AI on this page, and no collection of patient data. "
        "Data is a snapshot as of "
        f'<time datetime="{esc(snap["snapshotDate"])}">{esc(fmt_date(snap["snapshotDate"]))}</time>. '
        '<a href="notice.html">Full notice</a>.'
        "</div>"
    )


def write_practical_access(snap: dict) -> None:
    write(
        SITE / "practical-access.html",
        page_shell(
            "Practical access — Targeted Therapy Explorer",
            0,
            snap,
            page_body(),
            crumbs(
                [("index.html", "Home"), ("practical-access.html", "Practical access")],
                0,
            ),
            full_notice=False,
            custom_notice=merged_notice(snap),
        ),
    )
