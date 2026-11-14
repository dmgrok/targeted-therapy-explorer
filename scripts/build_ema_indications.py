#!/usr/bin/env python3
"""Build data/ema_indications.json from fetched EPAR HTML and procedural PDFs.

This is a one-off builder. The committed JSON is what the site uses; CI
does not re-fetch EMA pages. Re-run only when refreshing the indication
catalog from a local fetch directory (default /tmp/ema-epars).
"""
from __future__ import annotations

import argparse
import html as htmlmod
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROC_RE = re.compile(
    r"^\s*((?:WS|II|IA|IB|IG|X|T|R|PSUSA|ANX|EMA)"
    r"(?:/VR)?(?:/G)?[/\-\w.]*)\s{2,}(.*)$"
)
VARTYPE = re.compile(r"^\s*Variation type\s+(\w+)\s*/\s*(.*)$", re.I)
DATE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")
EXT_PHRASE = re.compile(r"Extension of [Ii]ndication")
CI6 = re.compile(r"C\.I\.6(?:\.a)?\b")
SHELF = re.compile(r"Extension of the shelf|re-test period|Q\.II\.f", re.I)


def clean(text: str) -> str:
    if not text:
        return ""
    t = htmlmod.unescape(text)
    for a, b in {
        "\xa0": " ",
        "\u00a0": " ",
        "\u2011": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u00ad": "",
        "\u200b": "",
        "\ufeff": "",
        "\u2010": "-",
        "‑": "-",
        "–": "-",
        "—": "-",
        "\u00a0": " ",
    }.items():
        t = t.replace(a, b)
    # Replacement character sometimes stands in for a non-breaking hyphen
    # (e.g. "HER2?positive" in a Tukysa extract).
    t = re.sub(r"([A-Z0-9])\?([a-z])", r"\1-\2", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def is_proc_line(line: str) -> bool:
    return bool(PROC_RE.match(line) or VARTYPE.match(line))


def get_code(line: str) -> str:
    m = PROC_RE.match(line)
    if m:
        return m.group(1)
    m = VARTYPE.match(line)
    if m:
        return f"Variation-type-{m.group(1)}"
    return ""


def is_indication_extension(body: str) -> bool:
    """True for an extension/addition of a therapeutic indication.

    Shelf-life and quality variations that only share the word
    "extension" are excluded. A C.I.6.a code, or the phrase
    "Extension of indication", is required.
    """
    if SHELF.search(body) and not EXT_PHRASE.search(body) and not CI6.search(body):
        return False
    if EXT_PHRASE.search(body):
        return True
    if CI6.search(body) and re.search(r"therapeutic indication", body, re.I):
        return True
    return False


def to_iso(d: str) -> str:
    if not d or not re.match(r"\d{2}/\d{2}/\d{4}$", d):
        return ""
    dd, mm, yy = d.split("/")
    return f"{yy}-{mm}-{dd}"



FOOTER = re.compile(
    r"^\s*(?:Page \d+/\d+|Official address|Address for visits|"
    r"Send us a question|Notifications are issued|are issued for all other|"
    r"A Commission decision \(CD\)|CD is issued within|"
    r"SmPC \(Summary of Product Characteristics\)|"
    r"\d+\s+Notifications are issued|"
    r"\*?Due to the Agency)",
    re.I,
)


def scope_column(header: str, body_lines: list[str]) -> str:
    """Take the Scope column (left of the first date) so 'Please refer
    to Scientific Discussion' in the Summary column cannot swallow
    the indication wording."""
    m = DATE.search(header)
    col = m.start() if m else 72
    # Leave a little room; dates sometimes shift a few columns.
    col = max(col - 2, 40)
    parts = []
    for line in body_lines:
        if FOOTER.search(line):
            continue
        if re.search(r"Page \d+/\d+", line):
            continue
        left = line[:col] if len(line) > 10 else line
        left = left.strip()
        if not left:
            continue
        # Drop a right-column fragment that leaked (e.g. "II-0039'").
        if re.match(r"^(?:II|WS|X)-?\d+", left) and "xtension" not in left:
            continue
        parts.append(left)
    text = " ".join(parts)
    text = re.sub(r"first-\s+line", "first-line", text)
    text = re.sub(r"(\w+)-\s+(\w+)", r"\1-\2", text)
    return text


def parse_procedural(text: str, source_url: str) -> list[dict]:
    if not text:
        return []
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        if not is_proc_line(lines[i]):
            i += 1
            continue
        code = get_code(lines[i])
        header = lines[i]
        body = [lines[i]]
        i += 1
        # Newer EMA "current" PDFs put "Variation type II /" on one line
        # and the EMA/VR number on the next.
        if code.startswith("Variation") and i < len(lines) and "EMA/" in lines[i]:
            code = lines[i].split()[0]
            header = header + " " + lines[i]
            body.append(lines[i])
            i += 1
        while i < len(lines):
            if is_proc_line(lines[i]):
                break
            body.append(lines[i])
            i += 1
        body_text = "\n".join(body)
        if not is_indication_extension(body_text):
            continue
        dates = DATE.findall(header)
        opinion = dates[0] if dates else ""
        cd = dates[1] if len(dates) >= 2 else ""
        # Never guess a single date's column. Year comes only from a
        # Commission Decision date (the second date column).
        year = cd.split("/")[-1] if cd else ""
        scope = clean(scope_column(header, body))
        full = clean(body_text)
        # Some older procedures put the indication wording in the
        # Summary column and only a "please refer to the Assessment
        # Report" note in Scope (Xalkori II/0024). Keep both when the
        # scope text does not itself name the extension.
        if (
            ("xtension of" in full.lower() or "first-line" in full.lower())
            and "xtension of" not in scope.lower()
        ):
            desc = clean(scope + " " + full)
        else:
            desc = scope
        out.append(
            {
                "procedure": code,
                "description": desc[:3000],
                "opinion_date": opinion,
                "opinion_date_iso": to_iso(opinion),
                "commission_decision_date": cd,
                "commission_decision_date_iso": to_iso(cd),
                "year": year,
                "source_url": source_url,
            }
        )
    return out


def ma_from_raw(ma_raw: str) -> tuple[str, str]:
    m = re.search(r"(\d{2}/\d{2}/\d{4})", ma_raw or "")
    if not m:
        return "", ""
    return m.group(1), to_iso(m.group(1))


def build(fetch_dir: Path) -> dict:
    index = json.loads((fetch_dir / "index.json").read_text(encoding="utf-8"))
    products = []
    for r in index:
        slug = r["slug"]
        exts: list[dict] = []
        for kind in ("current", "archive"):
            p = fetch_dir / f"{slug}-{kind}.txt"
            meta = r.get(f"{kind}_pdf") or {}
            url = meta.get("url") or ""
            if p.is_file():
                exts.extend(parse_procedural(p.read_text(errors="replace"), url))
        by: dict[str, dict] = {}
        for e in exts:
            k = e["procedure"]
            prev = by.get(k)
            if not prev:
                by[k] = e
                continue
            score = (1 if e["commission_decision_date"] else 0, len(e["description"]))
            pscore = (1 if prev["commission_decision_date"] else 0, len(prev["description"]))
            if score > pscore:
                by[k] = e
        exts = list(by.values())
        ma, ma_iso = ma_from_raw(r.get("ma_raw") or "")
        products.append(
            {
                "name": r["name"],
                "slug": slug,
                "url": r["url"],
                "html_therapeutic_indication": clean(r.get("therapeutic_indication") or ""),
                "therapeutic_indication": clean(r.get("therapeutic_indication") or ""),
                "smpc_4_1": "",
                "product_information_url": "",
                "marketing_authorisation_issued": ma,
                "marketing_authorisation_issued_iso": ma_iso,
                "ma_year": ma_iso[:4] if ma_iso else "",
                "n_extension_index": r.get("n_extension_of_indication") or 0,
                "n_CI6_index": r.get("n_CI6") or 0,
                "n_extension_parsed": len(exts),
                "extensions": exts,
                "current_pdf_url": (r.get("current_pdf") or {}).get("url") or "",
                "archive_pdf_url": (r.get("archive_pdf") or {}).get("url") or "",
            }
        )

    # Prefer the committed SmPC 4.1 sidecar; fall back to a fresh /tmp
    # fetch, then to a previously built catalog, so a rebuild never
    # silently reverts to the incomplete EPAR-webpage field.
    smpc_candidates = [
        ROOT / "data" / "ema_smpc_4_1.json",
        Path("/tmp/ema-smpc/index.json"),
    ]
    smpc = {}
    for smpc_path in smpc_candidates:
        if smpc_path.is_file():
            raw = json.loads(smpc_path.read_text(encoding="utf-8"))
            entries = raw.get("products", raw) if isinstance(raw, dict) else raw
            smpc = {e["slug"]: e for e in entries}
            break
    prev_path = ROOT / "data" / "ema_indications.json"
    prev = {}
    if prev_path.is_file():
        prev = {
            e["slug"]: e
            for e in json.loads(prev_path.read_text(encoding="utf-8")).get("products", [])
        }
    for p in products:
        s = smpc.get(p["slug"]) or {}
        prev_p = prev.get(p["slug"]) or {}
        body = (s.get("smpc_4_1") or prev_p.get("smpc_4_1") or "").strip()
        p["smpc_4_1"] = body
        p["product_information_url"] = (
            s.get("pi_url") or prev_p.get("product_information_url") or ""
        )
        # SmPC section 4.1 is the authorised indication wording.
        # The EPAR webpage "Therapeutic indication" field is sometimes
        # incomplete (Tarceva omitted first-line NSCLC; Cyramza omitted
        # the erlotinib combination). Prefer 4.1 when it is present.
        if body:
            p["therapeutic_indication"] = body
            p["indication_source"] = "smpc_4.1"
        else:
            p["indication_source"] = "epar_html"

    return {
        "note": (
            "EU therapeutic indications taken from each product's EMA EPAR "
            "English product-information PDF, section 4.1 (Therapeutic "
            "indications), which is the authorised SmPC wording. The EPAR "
            "webpage 'Therapeutic indication' field is kept as a cross-check; "
            "it is sometimes incomplete relative to section 4.1 (Tarceva "
            "omitted first-line NSCLC; Cyramza omitted the erlotinib "
            "combination). Indication-extension dates are taken from the EPAR "
            "'Marketing authorisation issued' field and from the EPAR 'Procedural steps taken and scientific information "
            "after authorisation' PDFs (current and archive). The year an "
            "indication was added is the Commission Decision date of the "
            "Type II / worksharing 'Extension of indication' (C.I.6.a) "
            "procedure, not the CHMP opinion date, and not the first "
            "marketing-authorisation year of the product unless that "
            "indication is shown to be original (sole current indication "
            "and no later extensions, or remainder after a complete parse "
            "of those extensions). A date is never inferred. Pages and PDFs "
            "were opened on 13 November 2026 (Europe/Paris)."
        ),
        "retrieved": "2026-11-13",
        "retrieved_zone": "Europe/Paris",
        "products": products,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-dir", type=Path, default=Path("/tmp/ema-epars"))
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "ema_indications.json",
    )
    args = ap.parse_args()
    data = build(args.fetch_dir)
    args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out} n={len(data['products'])}")
    under = over = exact = 0
    for p in data["products"]:
        a, b = p["n_extension_parsed"], p["n_extension_index"]
        if a < b:
            under += 1
            flag = "UNDER"
        elif a > b:
            over += 1
            flag = "OVER"
        else:
            exact += 1
            flag = "="
        if flag != "=":
            print(f"  {flag:5} {p['name']:20} parsed={a:2} index={b:2}")
    print(f"exact {exact} under {under} over {over}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
