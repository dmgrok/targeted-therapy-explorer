#!/usr/bin/env python3
"""Build data/snapshot.json from allowed public sources. No API keys. No OncoKB.

Sources: ClinicalTrials.gov API v2, openFDA / Drugs@FDA labels, FDA pharmacogenomic
and companion-diagnostic tables, EMA medicines workbook, CIViC (CC0), and PubMed
E-utilities metadata (citation cards only).
"""
from __future__ import annotations

import argparse
import subprocess
import json
import re
import sys
import time
import zipfile
import io
import html
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matching import classify_relation, relevant_excerpt, TARGETS, analyse_text, dedupe_therapies  # noqa: E402
UA = (
    "targeted-therapy-explorer/0.1 "
    "(https://dmgrok.github.io/targeted-therapy-explorer/; "
    "educational snapshot; no API key)"
)
MIN_INTERVAL = 0.45  # polite default between requests
_last_by_host: dict[str, float] = {}

BIOMARKERS = [
    {
        "id": "EGFR",
        "name": "EGFR",
        "fullName": "Epidermal growth factor receptor",
        "aliases": [r"\bEGFR\b"],
        "civicSymbols": ["EGFR"],
        "trialQuery": 'EGFR AND (cancer OR carcinoma OR NSCLC OR neoplasm)',
        "pubmed": 'EGFR[Title] AND (osimertinib OR "tyrosine kinase inhibitor") AND (cancer[Title]) AND review[pt]',
    },
    {
        "id": "ALK",
        "name": "ALK",
        "fullName": "Anaplastic lymphoma kinase",
        "aliases": [r"\bALK\b"],
        "civicSymbols": ["ALK"],
        "trialQuery": '("ALK positive" OR "ALK-positive" OR "ALK rearrangement" OR "ALK fusion" OR "ALK inhibitor") AND (cancer OR carcinoma OR NSCLC OR lymphoma)',
        "pubmed": 'ALK[Title] AND (alectinib OR lorlatinib OR "lung cancer") AND review[pt]',
    },
    {
        "id": "BRAF-V600E",
        "name": "BRAF V600E",
        "fullName": "BRAF V600E substitution",
        "aliases": [r"\bBRAF\b"],
        "civicSymbols": ["BRAF"],
        "civicVariants": ["V600E"],
        "trialQuery": '("BRAF V600E" OR "BRAF V600" OR "BRAF-mutant") AND (cancer OR melanoma OR carcinoma)',
        "pubmed": '"BRAF V600E"[Title] AND (vemurafenib OR dabrafenib OR encorafenib) AND review[pt]',
    },
    {
        "id": "KRAS-G12C",
        "name": "KRAS G12C",
        "fullName": "KRAS G12C substitution",
        "aliases": [r"\bKRAS\b"],
        "civicSymbols": ["KRAS"],
        "civicVariants": ["G12C"],
        "trialQuery": '("KRAS G12C" OR "KRAS-G12C") AND (cancer OR carcinoma OR NSCLC)',
        "pubmed": '"KRAS G12C"[Title] AND (sotorasib OR adagrasib) AND review[pt]',
    },
    {
        "id": "HER2",
        "name": "HER2",
        "fullName": "Human epidermal growth factor receptor 2 (ERBB2)",
        "aliases": [r"\bERBB2\b", r"\bHER2\b", r"\bHER-2\b"],
        "civicSymbols": ["ERBB2"],
        "trialQuery": '(HER2 OR ERBB2 OR "HER-2") AND (cancer OR carcinoma OR breast OR gastric) AND (positive OR overexpression OR amplified OR mutation OR mutant)',
        "pubmed": '(HER2[Title] OR ERBB2[Title]) AND (trastuzumab OR deruxtecan) AND review[pt]',
    },
    {
        "id": "NTRK",
        "name": "NTRK",
        "fullName": "Neurotrophic tyrosine receptor kinase fusion (NTRK1/2/3)",
        "aliases": [r"\bNTRK\d?\b", r"\bTRK\b"],
        "civicSymbols": ["NTRK1", "NTRK2", "NTRK3"],
        "trialQuery": '(NTRK OR "TRK fusion" OR larotrectinib OR entrectinib OR "NTRK1" OR "NTRK2" OR "NTRK3") AND (cancer OR carcinoma OR solid tumour OR "solid tumor")',
        "pubmed": '(NTRK[Title] OR "TRK fusion"[Title]) AND (larotrectinib OR entrectinib) AND review[pt]',
    },
    {
        "id": "MSI-H-dMMR",
        "name": "MSI-H / dMMR",
        "fullName": "Microsatellite instability-high or mismatch-repair deficient",
        "aliases": [
            r"Microsatellite",
            r"\bMSI\b",
            r"Mismatch Repair",
            r"\bdMMR\b",
            r"\bMMR\b",
        ],
        "civicSymbols": ["MSH2", "MLH1", "MSH6", "PMS2"],
        "civicProfiles": ["MSI", "MSI-H", "dMMR"],
        "trialQuery": '("MSI-H" OR "MSI-high" OR "microsatellite instability" OR dMMR OR "mismatch repair deficient" OR "mismatch-repair") AND (cancer OR carcinoma OR tumour OR tumor)',
        "pubmed": '("MSI-H"[Title] OR "microsatellite instability"[Title] OR dMMR[Title]) AND (pembrolizumab OR dostarlimab) AND review[pt]',
    },
]

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _host(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc


# Optional local cache of bulky source files (FDA HTML, EMA xlsx)
CACHE_DIR = Path("/tmp/tte-raw")

CACHE_MAP = {
    "https://www.fda.gov/drugs/science-and-research-drugs/table-pharmacogenomic-biomarkers-drug-labeling": "fda-pgx.html",
    "https://www.fda.gov/medical-devices/in-vitro-diagnostics/list-fda-authorized-companion-diagnostic-devices-in-vitro-and-imaging-tools": "fda-cdx.html",
    "https://www.ema.europa.eu/en/documents/report/medicines-output-medicines-report_en.xlsx": "ema.xlsx",
}


class HttpError(Exception):
    def __init__(self, code, url, body=b""):
        self.code = code
        self.url = url
        self.body = body
        super().__init__(f"HTTP Error {code}: {url}")


def http(url: str, *, data: bytes | None = None, headers: dict | None = None,
         method: str | None = None, timeout: int = 45, min_interval: float | None = None) -> tuple[int, bytes, str]:
    """Fetch via curl (reliable timeouts). Honour a local cache for bulky FDA/EMA files."""
    cache_name = CACHE_MAP.get(url)
    if cache_name and data is None:
        cp = CACHE_DIR / cache_name
        if cp.is_file() and cp.stat().st_size > 1000:
            return 200, cp.read_bytes(), "application/octet-stream"

    host = _host(url)
    wait = MIN_INTERVAL if min_interval is None else min_interval
    last = _last_by_host.get(host, 0)
    gap = wait - (time.time() - last)
    if gap > 0:
        time.sleep(gap)

    tries = 0
    while True:
        tries += 1
        cmd = [
            "curl", "-sS", "-L", "--compressed",
            "-A", UA,
            "--max-time", str(timeout),
            "--retry", "0",
            "-w", "\n__HTTPSTATUS__%{http_code}__CTYPE__%{content_type}",
            "-o", "-",
        ]
        if headers:
            for k, v in headers.items():
                if k.lower() != "user-agent":
                    cmd.extend(["-H", f"{k}: {v}"])
        if data is not None:
            cmd.extend(["--data-binary", "@-"])
            cmd.extend(["-X", method or "POST"])
        elif method:
            cmd.extend(["-X", method])
        cmd.append(url)
        try:
            proc = subprocess.run(
                cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 5
            )
        except subprocess.TimeoutExpired:
            _last_by_host[host] = time.time()
            if tries < 3:
                time.sleep(2 ** tries)
                continue
            raise TimeoutError(f"timeout: {url}")
        _last_by_host[host] = time.time()
        raw = proc.stdout
        # Split off the -w trailer (last line)
        if b"__HTTPSTATUS__" in raw:
            body, _, trailer = raw.rpartition(b"__HTTPSTATUS__")
            trailer_s = trailer.decode("utf-8", "replace")
            if "__CTYPE__" in trailer_s:
                code_s, ctype = trailer_s.split("__CTYPE__", 1)
            else:
                code_s, ctype = trailer_s, ""
            try:
                code = int(code_s.strip())
            except ValueError:
                code = 0
        else:
            body, code, ctype = raw, (0 if proc.returncode else 200), ""
        if code in (429, 500, 502, 503, 504) and tries < 5:
            time.sleep(min(30, 3 ** tries))
            continue
        if code >= 400 or (code == 0 and proc.returncode != 0):
            raise HttpError(code or 599, url, body)
        if cache_name and data is None and body:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            (CACHE_DIR / cache_name).write_bytes(body)
        return code, body, ctype


def http_json(url: str, **kw) -> object:
    status, body, _ = http(url, **kw)
    return json.loads(body.decode("utf-8", "replace"))


def text_excerpt(s: str, n: int = 420) -> str:
    s = re.sub(r"\s+", " ", (s or "")).strip()
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "…"


# ---------------------------------------------------------------------------
# ClinicalTrials.gov
# ---------------------------------------------------------------------------

def fetch_ctgov_version() -> dict:
    data = http_json("https://clinicaltrials.gov/api/v2/version")
    return {"apiVersion": data.get("apiVersion"), "dataTimestamp": data.get("dataTimestamp")}


def _extract_trial(study: dict) -> dict:
    ps = study.get("protocolSection") or {}
    ident = ps.get("identificationModule") or {}
    status = ps.get("statusModule") or {}
    design = ps.get("designModule") or {}
    cond = ps.get("conditionsModule") or {}
    arms = ps.get("armsInterventionsModule") or {}
    locs = (ps.get("contactsLocationsModule") or {}).get("locations") or []
    nct = ident.get("nctId") or ""
    countries = sorted({(l.get("country") or "").strip() for l in locs if l.get("country")})
    location_rows = []
    for l in locs:
        country = (l.get("country") or "").strip()
        if not country:
            continue
        location_rows.append({
            "facility": l.get("facility") or "",
            "city": l.get("city") or "",
            "country": country,
        })
    interventions = []
    for iv in arms.get("interventions") or []:
        name = iv.get("name") or ""
        kind = iv.get("type") or ""
        if name:
            interventions.append(f"{kind}: {name}" if kind else name)
    phases = design.get("phases") or []
    start = (status.get("startDateStruct") or {}).get("date") or ""
    return {
        "nctId": nct,
        "title": ident.get("briefTitle") or "",
        "status": status.get("overallStatus") or "",
        "phases": phases,
        "conditions": (cond.get("conditions") or [])[:8],
        "interventions": interventions[:8],
        "countries": countries,
        "locations": location_rows[:40],
        "startDate": start,
        "url": f"https://clinicaltrials.gov/study/{nct}" if nct else "",
        "source": {
            "name": "ClinicalTrials.gov",
            "url": f"https://clinicaltrials.gov/study/{nct}" if nct else "https://clinicaltrials.gov/",
        },
    }


def fetch_ctgov_trials(query: str, locn: str | None = None, page_size: int = 50, max_studies: int = 80) -> list[dict]:
    studies = []
    token = None
    while len(studies) < max_studies:
        params = {
            "query.term": query,
            "filter.overallStatus": "RECRUITING",
            "pageSize": min(page_size, max_studies - len(studies)),
            "countTotal": "true",
            "sort": "LastUpdatePostDate:desc",
        }
        if locn:
            params["query.locn"] = locn
        if token:
            params["pageToken"] = token
        url = "https://clinicaltrials.gov/api/v2/studies?" + urlencode(params)
        data = http_json(url, timeout=60)
        batch = data.get("studies") or []
        if not batch:
            break
        studies.extend(batch)
        token = data.get("nextPageToken")
        if not token:
            break
    return [_extract_trial(s) for s in studies[:max_studies]]


def trials_for_biomarker(bm: dict) -> list[dict]:
    seen = {}
    # Broad recruiting set, plus an explicit France and Switzerland pull so those
    # countries are represented when any such trial exists.
    chunks = [
        fetch_ctgov_trials(bm["trialQuery"], max_studies=70),
        fetch_ctgov_trials(bm["trialQuery"], locn="France", max_studies=30),
        fetch_ctgov_trials(bm["trialQuery"], locn="Switzerland", max_studies=30),
    ]
    for chunk in chunks:
        for t in chunk:
            if t["nctId"] and t["nctId"] not in seen:
                seen[t["nctId"]] = t
    # FR / CH first, then the rest, stable by NCT
    def sort_key(t):
        countries = set(t.get("countries") or [])
        flag = 0 if ("France" in countries or "Switzerland" in countries) else 1
        return (flag, t.get("nctId") or "")
    return sorted(seen.values(), key=sort_key)


# ---------------------------------------------------------------------------
# FDA HTML tables
# ---------------------------------------------------------------------------

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._table = None
        self._row = None
        self._cell = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
            return
        if self._skip:
            return
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.tables.append(self._table)
            self._table = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._cell is not None:
            self._cell.append(data)


def fetch_html_tables(url: str) -> list[list[list[str]]]:
    _, body, _ = http(url, timeout=90, min_interval=1.0)
    parser = TableParser()
    parser.feed(body.decode("utf-8", "replace"))
    return parser.tables


def alias_match(text: str, aliases: list[str]) -> bool:
    for a in aliases:
        if re.search(a, text, flags=re.I):
            return True
    return False


def fetch_fda_pgx() -> list[dict]:
    url = "https://www.fda.gov/drugs/science-and-research-drugs/table-pharmacogenomic-biomarkers-drug-labeling"
    tables = fetch_html_tables(url)
    # The first large table is the biomarker table
    rows_out = []
    for table in tables:
        if len(table) < 5:
            continue
        header = [c.lower() for c in table[0]]
        # Expect Drug | Therapeutic Area | Biomarker | Labeling Sections
        def col(*names):
            for n in names:
                for i, h in enumerate(header):
                    if n in h:
                        return i
            return None
        i_drug = col("drug")
        i_area = col("therapeutic")
        i_bm = col("biomarker")
        i_sec = col("labeling", "section")
        if i_drug is None or i_bm is None:
            continue
        for raw in table[1:]:
            if max(i_drug, i_bm) >= len(raw):
                continue
            drug = re.sub(r"\s*\(\d+\)\s*$", "", raw[i_drug]).strip()
            area = raw[i_area] if i_area is not None and i_area < len(raw) else ""
            biomarker = raw[i_bm]
            sections = raw[i_sec] if i_sec is not None and i_sec < len(raw) else ""
            if not drug:
                continue
            rows_out.append({
                "drug": drug,
                "therapeuticArea": area,
                "biomarker": biomarker,
                "labelingSections": sections,
                "sourceUrl": url,
            })
        if rows_out:
            break
    return rows_out


def fetch_fda_cdx() -> list[dict]:
    url = (
        "https://www.fda.gov/medical-devices/in-vitro-diagnostics/"
        "list-fda-authorized-companion-diagnostic-devices-in-vitro-and-imaging-tools"
    )
    tables = fetch_html_tables(url)
    rows_out = []
    for table in tables:
        if len(table) < 3:
            continue
        header = [c.lower() for c in table[0]]
        def col(*names):
            for n in names:
                for i, h in enumerate(header):
                    if n in h:
                        return i
            return None
        i_diag = col("diagnostic")
        i_ind = col("indication")
        i_drug = col("drug", "trade")
        i_bm = col("biomarker")
        if i_drug is None and i_bm is None:
            continue
        for raw in table[1:]:
            def cell(i):
                return raw[i] if i is not None and i < len(raw) else ""
            rows_out.append({
                "diagnostic": cell(i_diag),
                "indication": text_excerpt(cell(i_ind), 280),
                "drug": cell(i_drug),
                "biomarker": cell(i_bm) or (cell(col("biomarker(s) (details)", "details")) if False else ""),
                "sourceUrl": url,
            })
    return rows_out


# ---------------------------------------------------------------------------
# openFDA labels
# ---------------------------------------------------------------------------

def _clean_drug_token(name: str) -> str:
    name = re.sub(r"\(.*?\)", " ", name)
    name = re.sub(r"[®™]", "", name)
    name = re.sub(r"[^A-Za-z0-9 +\-]", " ", name)
    return re.sub(r"\s+", " ", name).strip()


def fetch_openfda_label(drug: str) -> dict | None:
    token = _clean_drug_token(drug)
    if not token:
        return None
    # Prefer generic name, then brand. Limit payload via search, take first.
    for field in ("openfda.generic_name", "openfda.brand_name", "openfda.substance_name"):
        q = f'{field}:"{token.split()[0]}"' if " " not in token else f'{field}:"{token}"'
        # For multi-word, also try exact token
        url = (
            "https://api.fda.gov/drug/label.json?"
            + urlencode({"search": f'{field}:"{token}"', "limit": "1"})
        )
        try:
            data = http_json(url, timeout=40)
        except (HTTPError, HttpError) as e:
            if getattr(e, "code", None) == 404:
                continue
            raise
        results = data.get("results") or []
        if not results:
            continue
        r = results[0]
        of = r.get("openfda") or {}
        set_ids = of.get("set_id") or ([r.get("set_id")] if r.get("set_id") else [])
        set_id = (set_ids[0] if set_ids else "") or r.get("set_id") or ""
        brands = of.get("brand_name") or []
        generics = of.get("generic_name") or []
        apps = of.get("application_number") or []
        indications = r.get("indications_and_usage") or []
        indic_text = indications[0] if indications else ""
        dailymed = (
            f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}"
            if set_id else "https://open.fda.gov/apis/drug/label/"
        )
        drugsfda = ""
        if apps:
            # Application numbers look like NDA021743 or BLA125514
            drugsfda = (
                "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
                "?event=overview.process&ApplNo="
                + re.sub(r"[^0-9]", "", apps[0])
            )
        return {
            "drugQuery": drug,
            "brandNames": brands[:4],
            "genericNames": generics[:4],
            "applicationNumbers": apps[:4],
            "effectiveTime": r.get("effective_time") or "",
            "indicationsText": indic_text,
            "indicationsExcerpt": text_excerpt(indic_text, 420),
            "dailymedUrl": dailymed,
            "drugsfdaUrl": drugsfda,
            "openfdaUrl": url,
            "setId": set_id,
        }
    return None


# ---------------------------------------------------------------------------
# EMA medicines xlsx
# ---------------------------------------------------------------------------

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _xlsx_sheet_rows(blob: bytes, sheet_name_pref: str | None = None) -> tuple[list[str], list[list[str]]]:
    z = zipfile.ZipFile(io.BytesIO(blob))
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", NS):
            texts = [t.text or "" for t in si.findall(".//m:t", NS)]
            ss.append("".join(texts))
    # workbook sheet paths
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {}
    for rel in rels:
        rid_to_target[rel.attrib.get("Id")] = rel.attrib.get("Target")
    sheets = []
    for sh in wb.find("m:sheets", NS) or []:
        name = sh.attrib.get("name")
        rid = sh.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rid_to_target.get(rid, "")
        path = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
        # some targets are "/xl/worksheets/sheet1.xml" or "worksheets/sheet1.xml"
        if not path.startswith("xl/"):
            path = "xl/" + path
        path = path.replace("xl/xl/", "xl/")
        sheets.append((name, path))
    chosen = sheets[0]
    if sheet_name_pref:
        for s in sheets:
            if s[0] and sheet_name_pref.lower() in s[0].lower():
                chosen = s
                break
    root = ET.fromstring(z.read(chosen[1]))

    def cell_value(c):
        t = c.attrib.get("t")
        v = c.find("m:v", NS)
        is_el = c.find("m:is", NS)
        if t == "s" and v is not None and v.text is not None:
            idx = int(v.text)
            return ss[idx] if 0 <= idx < len(ss) else ""
        if t == "inlineStr" and is_el is not None:
            return "".join(x.text or "" for x in is_el.findall(".//m:t", NS))
        if v is not None and v.text is not None:
            return v.text
        return ""

    rows = []
    for row in root.findall("m:sheetData/m:row", NS):
        vals = [cell_value(c) for c in row.findall("m:c", NS)]
        rows.append(vals)
    if not rows:
        return [], []
    header = rows[0]
    return header, rows[1:]


def _col_index(ref: str) -> int:
    letters = re.match(r"([A-Z]+)", ref or "A").group(1)
    n = 0
    for c in letters:
        n = n * 26 + (ord(c) - 64)
    return n - 1


def _xlsx_values(blob: bytes) -> list[dict[int, str]]:
    """Return a list of {col_index: value} for every row, honouring cell refs."""
    z = zipfile.ZipFile(io.BytesIO(blob))
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", NS):
            texts = [t.text or "" for t in si.findall(".//m:t", NS)]
            ss.append("".join(texts))
    root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    def cell_value(c):
        t = c.attrib.get("t")
        v = c.find("m:v", NS)
        is_el = c.find("m:is", NS)
        if t == "s" and v is not None and v.text is not None:
            idx = int(v.text)
            return ss[idx] if 0 <= idx < len(ss) else ""
        if t == "inlineStr" and is_el is not None:
            return "".join(x.text or "" for x in is_el.findall(".//m:t", NS))
        if is_el is not None:
            return "".join(x.text or "" for x in is_el.findall(".//m:t", NS))
        if v is not None and v.text is not None:
            return v.text
        return ""

    rows = []
    for row in root.findall("m:sheetData/m:row", NS):
        d = {}
        for c in row.findall("m:c", NS):
            d[_col_index(c.attrib.get("r", "A"))] = cell_value(c)
        rows.append(d)
    return rows


def fetch_ema_medicines() -> list[dict]:
    url = "https://www.ema.europa.eu/en/documents/report/medicines-output-medicines-report_en.xlsx"
    _, blob, _ = http(url, timeout=90, min_interval=1.0)
    rows = _xlsx_values(blob)
    # Known column map for the EMA "Medicine" workbook (row 9 is the header;
    # shared-string values observed 12 Nov 2026). Data starts at the first
    # "Human" / "Veterinary" row.
    # A Category, B Name, C EMA number, D status, G INN, H active substance,
    # I therapeutic area, P indication, AD authorisation date, AM EPAR URL.
    out = []
    for raw in rows:
        category = (raw.get(0) or "").strip()
        if category.lower() != "human":
            continue
        name = (raw.get(1) or "").strip()
        inn = (raw.get(6) or "").strip()
        if not name and not inn:
            continue
        url_e = (raw.get(38) or "").strip()  # AM = 38
        out.append({
            "name": name,
            "inn": inn,
            "activeSubstance": (raw.get(7) or "").strip(),
            "therapeuticArea": (raw.get(8) or "").strip(),
            "condition": text_excerpt((raw.get(15) or "").strip(), 280),
            "status": (raw.get(3) or "").strip(),
            "authorisationDate": (raw.get(29) or raw.get(31) or "").strip(),
            "emaUrl": url_e or "https://www.ema.europa.eu/en/medicines",
            "emaNumber": (raw.get(2) or "").strip(),
        })
    return out


def match_ema(ema_rows: list[dict], drug: str) -> list[dict]:
    token = _clean_drug_token(drug).lower()
    if not token:
        return []
    parts = [p for p in re.split(r"[+/,-]", token) if len(p.strip()) > 3]
    if not parts:
        parts = [token]
    hits = []
    for row in ema_rows:
        hay = f"{row.get('name','')} {row.get('inn','')}".lower()
        if any(p in hay for p in parts):
            hits.append(row)
    return hits[:4]


# ---------------------------------------------------------------------------
# CIViC
# ---------------------------------------------------------------------------

def civic_gql(query: str, variables: dict | None = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    _, body, _ = http(
        "https://civicdb.org/api/graphql",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
        timeout=50,
        min_interval=0.5,
    )
    data = json.loads(body.decode("utf-8", "replace"))
    if data.get("errors"):
        raise RuntimeError(data["errors"][0].get("message") or "CIViC GraphQL error")
    return data.get("data") or {}


GENE_Q = """
query ($syms: [String!]!) {
  genes(entrezSymbols: $syms, first: 20) {
    nodes {
      id
      name
      description
      link
    }
  }
}
"""

ASSERT_Q = """
query ($name: String!, $after: String) {
  assertions(molecularProfileName: $name, first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id
      status
      summary
      assertionType
      significance
      ampLevel
      therapies { name ncitId }
      disease { name }
      molecularProfile { name id }
    }
  }
}
"""


def fetch_civic(bm: dict) -> dict:
    genes = []
    try:
        data = civic_gql(GENE_Q, {"syms": bm["civicSymbols"]})
        genes = (data.get("genes") or {}).get("nodes") or []
    except Exception as e:
        return {"ok": False, "error": str(e), "genes": [], "assertions": []}

    assertions = []
    names = [bm["name"]] + bm.get("civicProfiles", []) + bm["civicSymbols"]
    if bm.get("civicVariants"):
        for sym in bm["civicSymbols"]:
            for v in bm["civicVariants"]:
                names.append(f"{sym} {v}")
    seen = set()
    for name in names:
        after = None
        pages = 0
        while pages < 3:
            pages += 1
            try:
                data = civic_gql(ASSERT_Q, {"name": name, "after": after})
            except Exception:
                # molecularProfileName may not match; skip quietly
                break
            conn = data.get("assertions") or {}
            for n in conn.get("nodes") or []:
                if n["id"] in seen:
                    continue
                # Keep accepted / accepted-looking assertions
                status = (n.get("status") or "").upper()
                if status and status not in ("ACCEPTED", "APPROVED", "ACTIVE"):
                    # still keep if ampLevel is present (often accepted)
                    if not n.get("ampLevel"):
                        continue
                seen.add(n["id"])
                assertions.append({
                    "id": n.get("id"),
                    "status": n.get("status"),
                    "summary": text_excerpt(n.get("summary") or "", 400),
                    "assertionType": n.get("assertionType"),
                    "significance": n.get("significance"),
                    "ampLevel": n.get("ampLevel"),
                    "therapies": [t.get("name") for t in (n.get("therapies") or []) if t.get("name")],
                    "disease": ((n.get("disease") or {}).get("name")),
                    "molecularProfile": ((n.get("molecularProfile") or {}).get("name")),
                    "url": f"https://civicdb.org/assertions/{n.get('id')}" if n.get("id") else "https://civicdb.org/",
                })
            pi = conn.get("pageInfo") or {}
            if not pi.get("hasNextPage"):
                break
            after = pi.get("endCursor")
            if not after:
                break
    # Prefer AMP / tier I-like first
    def akey(a):
        lvl = (a.get("ampLevel") or "")
        return (0 if "TIER_I" in lvl or "LEVEL_A" in lvl else 1, a.get("id") or 0)
    assertions.sort(key=akey)
    gene_out = []
    for g in genes:
        gid = g.get("id")
        gene_out.append({
            "id": gid,
            "name": g.get("name"),
            "description": text_excerpt(g.get("description") or "", 700),
            "url": g.get("link") or (f"https://civicdb.org/genes/{gid}/summary" if gid else "https://civicdb.org/"),
        })
    return {"ok": True, "genes": gene_out, "assertions": assertions[:40]}


# ---------------------------------------------------------------------------
# PubMed citation cards (metadata only)
# ---------------------------------------------------------------------------

def fetch_pubmed(term: str, retmax: int = 5) -> list[dict]:
    # 3 rps official cap without a key — MIN_INTERVAL 0.45 is safe; also pause 0.4s extra
    params = {
        "db": "pubmed",
        "term": term,
        "retmax": str(retmax),
        "retmode": "json",
        "sort": "relevance",
        "tool": "targeted-therapy-explorer",
        "email": "targeted-therapy-explorer@users.noreply.github.com",
    }
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urlencode(params)
    data = http_json(url, min_interval=0.4)
    ids = ((data.get("esearchresult") or {}).get("idlist")) or []
    if not ids:
        return []
    time.sleep(0.4)
    sum_url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
        + urlencode({
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "json",
            "tool": "targeted-therapy-explorer",
            "email": "targeted-therapy-explorer@users.noreply.github.com",
        })
    )
    summary = http_json(sum_url, min_interval=0.4)
    result = summary.get("result") or {}
    cards = []
    for pmid in ids:
        r = result.get(pmid) or {}
        authors = r.get("authors") or []
        author_s = ", ".join(a.get("name", "") for a in authors[:4] if a.get("name"))
        if len(authors) > 4:
            author_s += " et al."
        cards.append({
            "pmid": pmid,
            "title": r.get("title") or "",
            "authors": author_s,
            "journal": r.get("fulljournalname") or r.get("source") or "",
            "date": r.get("pubdate") or "",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "source": "PubMed",
        })
    return cards


# ---------------------------------------------------------------------------
# Assemble therapies for a biomarker
# ---------------------------------------------------------------------------

def therapies_for(bm: dict, pgx: list[dict], cdx: list[dict],
                  ema_rows: list[dict], label_cache: dict) -> list[dict]:
    # Collect candidate drug names from FDA tables
    candidates: dict[str, dict] = {}

    def add(name: str, origin: str, extra: dict):
        key = _clean_drug_token(name).lower()
        if not key or len(key) < 3:
            return
        rec = candidates.setdefault(key, {"name": _clean_drug_token(name), "origins": [], "pgx": [], "cdx": []})
        if origin not in rec["origins"]:
            rec["origins"].append(origin)
        if extra.get("pgx"):
            rec["pgx"].append(extra["pgx"])
        if extra.get("cdx"):
            rec["cdx"].append(extra["cdx"])

    for row in pgx:
        area = (row.get("therapeuticArea") or "").lower()
        # Keep oncology / hematology primarily; MSI and others sit in Oncology
        if area and not any(x in area for x in ("oncol", "hemat", "haemat")):
            # still allow if biomarker is a strong match (e.g. some tables use other areas)
            if not alias_match(row.get("biomarker") or "", bm["aliases"]):
                continue
        if alias_match(row.get("biomarker") or "", bm["aliases"]):
            add(row["drug"], "fda-pgx", {"pgx": row})

    for row in cdx:
        hay = f"{row.get('biomarker','')} {row.get('indication','')} {row.get('drug','')}"
        if alias_match(hay, bm["aliases"]):
            # Drug field may list several trade names
            raw = row.get("drug") or ""
            # Split on common separators but keep "drug (generic)" together
            pieces = re.split(r"\s*(?:;|\n| / )\s*", raw)
            for p in pieces:
                p = p.strip()
                if p:
                    add(p, "fda-cdx", {"cdx": row})

    therapies = []
    for key, rec in sorted(candidates.items(), key=lambda kv: kv[1]["name"].lower()):
        drug = rec["name"]
        if drug not in label_cache:
            try:
                label_cache[drug] = fetch_openfda_label(drug)
            except Exception as e:
                label_cache[drug] = {"error": str(e)}
        label = label_cache.get(drug) if isinstance(label_cache.get(drug), dict) and "error" not in (label_cache.get(drug) or {}) else None
        ema_hits = match_ema(ema_rows, drug)
        # Also try generic names from the label
        if label:
            for g in label.get("genericNames") or []:
                more = match_ema(ema_rows, g)
                for m in more:
                    if m not in ema_hits:
                        ema_hits.append(m)

        citations = []
        if rec["pgx"]:
            citations.append({
                "source": "FDA Table of Pharmacogenomic Biomarkers in Drug Labeling",
                "url": rec["pgx"][0]["sourceUrl"],
                "detail": f"Biomarker listed as “{rec['pgx'][0].get('biomarker','')}”; labeling sections: {rec['pgx'][0].get('labelingSections','')}.",
            })
        if rec["cdx"]:
            citations.append({
                "source": "FDA-authorized companion diagnostic devices",
                "url": rec["cdx"][0]["sourceUrl"],
                "detail": text_excerpt(
                    f"{rec['cdx'][0].get('diagnostic','')}: {rec['cdx'][0].get('indication','')}",
                    280,
                ),
            })
        if label:
            citations.append({
                "source": "FDA drug label (openFDA / DailyMed)",
                "url": label.get("dailymedUrl") or label.get("openfdaUrl"),
                "detail": "Excerpt of Indications and Usage; see the official label for the complete, current text.",
            })
            if label.get("drugsfdaUrl"):
                citations.append({
                    "source": "Drugs@FDA",
                    "url": label["drugsfdaUrl"],
                    "detail": "Application " + ", ".join(label.get("applicationNumbers") or []),
                })
        for em in ema_hits:
            citations.append({
                "source": "European Medicines Agency",
                "url": em.get("emaUrl") or "https://www.ema.europa.eu/en/medicines",
                "detail": text_excerpt(
                    f"{em.get('name') or ''} ({em.get('inn') or ''}). {em.get('status') or ''} {em.get('condition') or ''}",
                    280,
                ),
            })

        therapies.append({
            "name": drug,
            "brandNames": (label or {}).get("brandNames") or [],
            "genericNames": (label or {}).get("genericNames") or [],
            "indicationsExcerpt": (label or {}).get("indicationsExcerpt") or "",
            "fda": {
                "pgxBiomarker": (rec["pgx"][0].get("biomarker") if rec["pgx"] else ""),
                "pgxArea": (rec["pgx"][0].get("therapeuticArea") if rec["pgx"] else ""),
                "labelingSections": (rec["pgx"][0].get("labelingSections") if rec["pgx"] else ""),
                "dailymedUrl": (label or {}).get("dailymedUrl") or "",
                "drugsfdaUrl": (label or {}).get("drugsfdaUrl") or "",
            } if (rec["pgx"] or label) else None,
            "ema": [
                {
                    "name": e.get("name"),
                    "inn": e.get("inn"),
                    "status": e.get("status"),
                    "authorisationDate": e.get("authorisationDate"),
                    "url": e.get("emaUrl"),
                }
                for e in ema_hits
            ],
            "companionDiagnostics": [
                {
                    "diagnostic": c.get("diagnostic"),
                    "indication": c.get("indication"),
                    "url": c.get("sourceUrl"),
                }
                for c in rec["cdx"][:5]
            ],
            "citations": citations,
        })
        therapy = therapies[-1]
        full = (label or {}).get("indicationsText") or ""
        result = classify_relation(bm["id"], therapy, extra_text=full)
        therapy["relation"] = result["relation"]
        therapy["relationReason"] = result["reason"]
        therapy["relationEvidence"] = result["evidence"]
        # Prefer a displayed excerpt that includes the selection-criterion clause.
        if result["relation"] == TARGETS and full:
            if not analyse_text(therapy.get("indicationsExcerpt") or "", bm["id"])["positives"]:
                therapy["indicationsExcerpt"] = relevant_excerpt(full, bm["id"], 420)
        elif not therapy.get("indicationsExcerpt") and full:
            therapy["indicationsExcerpt"] = relevant_excerpt(full, bm["id"], 420)
    therapies, _reports = dedupe_therapies(therapies)
    for rec in therapies:
        rec.pop("_mergedFrom", None)
    # Re-classify after a merge so combined CDx / label evidence is considered,
    # and so the QC not-shown override still applies.
    for therapy in therapies:
        result = classify_relation(bm["id"], therapy)
        therapy["relation"] = result["relation"]
        therapy["relationReason"] = result["reason"]
        therapy["relationEvidence"] = result["evidence"]
    return therapies


def summary_for(bm: dict, civic: dict) -> tuple[str, list[dict]]:
    # Prefer CIViC gene description (CC0) when present
    sources = []
    texts = []
    for g in civic.get("genes") or []:
        if g.get("description"):
            texts.append(g["description"])
            sources.append({"source": "CIViC (CC0)", "url": g.get("url"), "detail": f"{g.get('name')} gene summary."})
            break
    if not texts:
        # Short educational fallback, clearly sourced to the FDA table
        texts.append(
            f"{bm['fullName']} ({bm['name']}) is one of the biomarkers in this explorer’s closed list. "
            "Approved therapies below are those the FDA pharmacogenomic and companion-diagnostic tables "
            "associate with this biomarker; European authorisations are added from EMA medicine data when a match is found."
        )
        sources.append({
            "source": "FDA Table of Pharmacogenomic Biomarkers in Drug Labeling",
            "url": "https://www.fda.gov/drugs/science-and-research-drugs/table-pharmacogenomic-biomarkers-drug-labeling",
            "detail": "Closed-list membership and therapy association.",
        })
    return texts[0], sources


def compute_whats_new(prev: dict | None, current: dict) -> list[dict]:
    if not prev:
        return [{
            "type": "first-snapshot",
            "text": (
                f"This is the first snapshot ({current['snapshotDate']}). "
                "Weekly additions, withdrawals and label changes will appear here after the next refresh is merged."
            ),
            "source": None,
        }]
    items = []
    prev_bms = {b["id"]: b for b in prev.get("biomarkers") or []}
    for b in current.get("biomarkers") or []:
        old = prev_bms.get(b["id"]) or {"therapies": [], "trials": []}
        old_th = {t["name"].lower() for t in old.get("therapies") or []}
        new_th = {t["name"].lower(): t for t in b.get("therapies") or []}
        for name, t in new_th.items():
            if name not in old_th:
                items.append({
                    "type": "therapy-added",
                    "biomarker": b["name"],
                    "text": f"{b['name']}: {t['name']} now appears among the FDA/EMA-associated therapies.",
                    "url": (t.get("citations") or [{}])[0].get("url"),
                })
        for name in old_th - set(new_th):
            items.append({
                "type": "therapy-removed",
                "biomarker": b["name"],
                "text": f"{b['name']}: {name} is no longer in the associated-therapy list.",
                "url": None,
            })
        old_nct = {t["nctId"] for t in old.get("trials") or []}
        new_trials = {t["nctId"]: t for t in b.get("trials") or []}
        for nct, t in new_trials.items():
            if nct not in old_nct:
                items.append({
                    "type": "trial-added",
                    "biomarker": b["name"],
                    "text": f"{b['name']}: new recruiting trial {nct} — {t.get('title','')}.",
                    "url": t.get("url"),
                })
        for nct in old_nct - set(new_trials):
            items.append({
                "type": "trial-removed",
                "biomarker": b["name"],
                "text": f"{b['name']}: {nct} is no longer in the recruiting snapshot.",
                "url": f"https://clinicaltrials.gov/study/{nct}",
            })
    return items[:80]


def load_previous(path: Path) -> dict | None:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DATA / "snapshot.json")
    ap.add_argument("--prev", type=Path, default=DATA / "snapshot.json")
    args = ap.parse_args()

    failures: list[dict] = []
    stats: dict = {}
    now = datetime.now(timezone.utc)
    snapshot_date = now.astimezone().date().isoformat()  # box is Europe/Paris

    prev = None
    if args.prev.is_file() and args.prev.resolve() != Path(args.out).resolve():
        prev = load_previous(args.prev)
    elif args.prev.is_file():
        # Read previous then we will overwrite
        prev = load_previous(args.prev)

    def record(name, ok, **extra):
        stats[name] = {"ok": ok, **extra}
        if not ok:
            failures.append({"source": name, "error": extra.get("error", "failed")})
            print(f"[fail] {name}: {extra.get('error')}", file=sys.stderr, flush=True)
        else:
            print(f"[ok]   {name}: { {k:v for k,v in extra.items() if k!='error'} }", flush=True)

    # CT.gov version
    ct_version = {}
    try:
        ct_version = fetch_ctgov_version()
        record("clinicaltrials-version", True, **ct_version)
    except Exception as e:
        record("clinicaltrials-version", False, error=str(e))

    pgx, cdx, ema_rows = [], [], []
    try:
        pgx = fetch_fda_pgx()
        record("fda-pgx", True, rows=len(pgx))
    except Exception as e:
        record("fda-pgx", False, error=str(e), rows=0)
    try:
        cdx = fetch_fda_cdx()
        record("fda-cdx", True, rows=len(cdx))
    except Exception as e:
        record("fda-cdx", False, error=str(e), rows=0)
    try:
        ema_rows = fetch_ema_medicines()
        record("ema", True, rows=len(ema_rows))
    except Exception as e:
        record("ema", False, error=str(e), rows=0)

    label_cache: dict = {}
    biomarkers_out = []
    total_trials = 0
    total_therapies = 0
    total_therapies_all = 0
    total_civic = 0
    total_lit = 0

    for bm in BIOMARKERS:
        print(f"--- {bm['id']} ---", flush=True)
        civic = {"ok": False, "genes": [], "assertions": []}
        try:
            civic = fetch_civic(bm)
            record(f"civic-{bm['id']}", civic.get("ok", True),
                   genes=len(civic.get("genes") or []),
                   assertions=len(civic.get("assertions") or []),
                   error=civic.get("error"))
        except Exception as e:
            record(f"civic-{bm['id']}", False, error=str(e))

        trials = []
        try:
            trials = trials_for_biomarker(bm)
            record(f"trials-{bm['id']}", True, trials=len(trials),
                   france=sum(1 for t in trials if "France" in (t.get("countries") or [])),
                   switzerland=sum(1 for t in trials if "Switzerland" in (t.get("countries") or [])))
        except Exception as e:
            record(f"trials-{bm['id']}", False, error=str(e), trials=0)

        try:
            therapies = therapies_for(bm, pgx, cdx, ema_rows, label_cache)
            record(f"therapies-{bm['id']}", True, therapies=len(therapies))
        except Exception as e:
            record(f"therapies-{bm['id']}", False, error=str(e))
            therapies = []

        literature = []
        try:
            literature = fetch_pubmed(bm["pubmed"], retmax=5)
            record(f"pubmed-{bm['id']}", True, citations=len(literature))
        except Exception as e:
            record(f"pubmed-{bm['id']}", False, error=str(e), citations=0)

        summary, summary_sources = summary_for(bm, civic)
        biomarkers_out.append({
            "id": bm["id"],
            "name": bm["name"],
            "fullName": bm["fullName"],
            "summary": summary,
            "summarySources": summary_sources,
            "therapies": therapies,
            "civic": {
                "genes": civic.get("genes") or [],
                "assertions": civic.get("assertions") or [],
            },
            "trials": trials,
            "literature": literature,
        })
        total_trials += len(trials)
        total_therapies += sum(1 for th in therapies if th.get("relation") == TARGETS)
        total_therapies_all += len(therapies)
        total_civic += len(civic.get("assertions") or [])
        total_lit += len(literature)

    # openFDA stats
    labels_ok = sum(1 for v in label_cache.values() if isinstance(v, dict) and v and "error" not in v)
    record("openfda", True, queried=len(label_cache), labels=labels_ok)

    current = {
        "snapshotDate": snapshot_date,
        "generatedAt": now.isoformat(),
        "timezoneNote": "Dates are calendar dates in Europe/Paris for snapshotDate; ClinicalTrials.gov dataTimestamp is shown as published by NLM.",
        "clinicalTrials": ct_version,
        "biomarkers": biomarkers_out,
        "whatsNew": [],
        "sourceStats": stats,
        "failures": failures,
        "counts": {
            "biomarkers": len(biomarkers_out),
            "therapies": total_therapies,
            "therapiesAll": total_therapies_all,
            "trials": total_trials,
            "civicAssertions": total_civic,
            "literature": total_lit,
            "fdaPgxRows": len(pgx),
            "fdaCdxRows": len(cdx),
            "emaRows": len(ema_rows),
            "openfdaLabels": labels_ok,
        },
    }
    current["whatsNew"] = compute_whats_new(prev, current)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # If we loaded prev from the same path, write atomically
    tmp = args.out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(args.out)
    print(f"Wrote {args.out}  counts={current['counts']}  failures={len(failures)}")
    return 0 if not failures else 0  # still succeed; failures are recorded


if __name__ == "__main__":
    sys.exit(main())
