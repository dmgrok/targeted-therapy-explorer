#!/usr/bin/env python3
"""Fetch full Indications and Usage (and form/mechanism fields) from the
openFDA drug-label API for every targeting therapy. Writes data/labels.json.

This is a maintainer tool, not called at site-build time. The committed
JSON is the source of truth for the tree and for plain-language lines.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from matching import targeting_therapies  # noqa: E402

OUT = ROOT / "data" / "labels.json"
API = "https://api.fda.gov/drug/label.json"
RETRIEVED = date.today().isoformat()  # box is Europe/Paris


def set_id_from_url(url: str) -> str:
    m = re.search(r"setid=([0-9a-fA-F\-]+)", url or "")
    return (m.group(1) if m else "").lower()


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "targeted-therapy-explorer/label-fetch"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def first(r: dict, *keys) -> str:
    for k in keys:
        v = r.get(k)
        if isinstance(v, list) and v:
            return v[0] or ""
        if isinstance(v, str) and v:
            return v
    return ""


def record_from(r: dict, query: str, how: str) -> dict:
    of = r.get("openfda") or {}
    set_ids = of.get("spl_set_id") or []
    set_id = r.get("set_id") or (set_ids[0] if set_ids else "")
    return {
        "name": query,
        "brandNames": of.get("brand_name") or [],
        "genericNames": of.get("generic_name") or [],
        "applicationNumbers": of.get("application_number") or [],
        "manufacturer": (of.get("manufacturer_name") or [""])[0] if of.get("manufacturer_name") else "",
        "route": of.get("route") or [],
        "set_id": set_id,
        "label_id": r.get("id") or "",
        "version": str(r.get("version") or ""),
        "effective_time": r.get("effective_time") or "",
        "indications_and_usage": first(r, "indications_and_usage"),
        "dosage_forms_and_strengths": first(r, "dosage_forms_and_strengths"),
        "dosage_and_administration": first(r, "dosage_and_administration"),
        "description": first(r, "description"),
        "mechanism_of_action": first(r, "mechanism_of_action") or first(r, "clinical_pharmacology"),
        "openfda_url": f'{API}?search=set_id:"{set_id}"&limit=1' if set_id else API,
        "dailymed_url": (
            f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}"
            if set_id else ""
        ),
        "retrieval_date": RETRIEVED,
        "retrieved_via": how,
    }


def search_set_id(set_id: str) -> dict | None:
    for field in ("set_id", "openfda.spl_set_id"):
        url = f'{API}?search={field}:"{set_id}"&limit=1'
        try:
            d = get_json(url)
        except Exception as e:
            print(f"  warn {field} {set_id}: {e}")
            continue
        if d.get("results"):
            return d["results"][0]
    return None


def search_name(name: str) -> dict | None:
    # Prefer a recent brand or generic hit that actually has indications.
    q = urllib.parse.quote(name)
    for expr in (
        f'openfda.generic_name:"{name}"',
        f'openfda.brand_name:"{name}"',
        f'generic_name:"{name}"',
        name,
    ):
        url = f"{API}?search={urllib.parse.quote(expr)}&limit=5"
        try:
            d = get_json(url)
        except Exception:
            continue
        results = d.get("results") or []
        owned = []
        for r in results:
            iu = first(r, "indications_and_usage")
            if iu:
                owned.append(r)
        if owned:
            owned.sort(key=lambda r: r.get("effective_time") or "", reverse=True)
            return owned[0]
    return None


# Prefer these set ids when we personally opened a more recent / brand label.
PREFERRED_SET = {
    # TARCEVA (erlotinib) label we opened: effective 18 Nov 2025, version 17.
    "Erlotinib": "57bccb29-1c47-4c64-ab6a-77960a91cc20",
    # TAGRISSO (osimertinib) DailyMed / openFDA we opened: effective 14 Sep 2026, version 37.
    "Osimertinib": "5e81b4a7-b971-45e1-9c31-29cea8c87ce7",
}


def main() -> int:
    snap = json.loads((ROOT / "data" / "snapshot.json").read_text())
    # Unique targeting therapies, plus withdrawn targeting (Mobocertinib).
    wanted = {}
    for b in snap.get("biomarkers") or []:
        for t in targeting_therapies(b):
            wanted[(t.get("name") or "").strip()] = t
        # also raw targeting-relation including withdrawn
        for t in b.get("therapies") or []:
            if (t.get("relation") or "") == "targets":
                wanted.setdefault((t.get("name") or "").strip(), t)

    entries = {}
    missing = []
    for name, t in sorted(wanted.items()):
        if not name:
            continue
        fda = t.get("fda") or {}
        sid = PREFERRED_SET.get(name) or set_id_from_url(fda.get("dailymedUrl") or "")
        print(f"fetch {name} set={sid or '(none)'}")
        rec = None
        how = ""
        if sid:
            raw = search_set_id(sid)
            if raw:
                rec = record_from(raw, name, f"openFDA set_id {sid}")
                how = "set_id"
        if not rec:
            raw = search_name(name)
            if raw:
                rec = record_from(raw, name, f"openFDA name search {name}")
                how = "name"
        if rec and rec.get("indications_and_usage"):
            entries[name] = rec
            print(f"  ok {how} eff={rec['effective_time']} ver={rec['version']} iu={len(rec['indications_and_usage'])}")
        else:
            missing.append(name)
            print("  MISSING")
        time.sleep(0.25)

    payload = {
        "retrieved_at": RETRIEVED,
        "retrieved_zone": "Europe/Paris",
        "api": API,
        "note": (
            "Full Indications and Usage (and form / mechanism fields) pulled from "
            "the openFDA drug-label API on the retrieval date. Used instead of the "
            "420-character snapshot excerpt for the decision tree and plain lines. "
            "Each entry has a source URL, set id, label version and effective date."
        ),
        "entries": entries,
        "missing": missing,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(entries)} labels, {len(missing)} missing)")
    if missing:
        print("MISSING:", missing)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
