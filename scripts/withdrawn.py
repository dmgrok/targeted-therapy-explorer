#!/usr/bin/env python3
"""Withdrawn / discontinued labels.

A therapy is removed from Mainstream only when a *whole-product*
withdrawal is recorded in data/withdrawn.json (a catalog of sources
we opened, with URLs and dates). Indication-level withdrawals are
reported by the gate and must not drop a drug that still has another
approved use for this biomarker.

The catalog is committed reviewable data. Weekly snapshot PRs do not
silently add or remove withdrawals; the gate fails if a whole-product
entry's names no longer match any snapshot therapy (stale catalog) or
if a targeting therapy is shown as Mainstream despite a whole-product
match.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "withdrawn.json"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def load_catalog() -> dict:
    if not CATALOG.is_file():
        raise FileNotFoundError(f"missing withdrawn catalog {CATALOG}")
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def _therapy_keys(therapy: dict) -> set[str]:
    names = [therapy.get("name") or ""]
    names.extend(therapy.get("brandNames") or [])
    names.extend(therapy.get("genericNames") or [])
    for e in therapy.get("ema") or []:
        names.append(e.get("name") or "")
        names.append(e.get("inn") or "")
    return {_norm(n) for n in names if n and _norm(n)}


def _entry_keys(entry: dict) -> set[str]:
    return {_norm(n) for n in (entry.get("names") or []) if n and _norm(n)}


def whole_product_match(therapy: dict, catalog: dict | None = None) -> dict | None:
    """Return the whole-product catalog entry if this therapy matches one."""
    catalog = catalog or load_catalog()
    keys = _therapy_keys(therapy)
    for entry in catalog.get("entries") or []:
        if entry.get("scope") != "whole-product":
            continue
        if keys & _entry_keys(entry):
            return entry
    return None


def indication_notes(therapy: dict, catalog: dict | None = None) -> list[dict]:
    catalog = catalog or load_catalog()
    keys = _therapy_keys(therapy)
    out = []
    for entry in catalog.get("indication_level_noted") or []:
        if keys & _entry_keys(entry):
            out.append(entry)
    return out


def is_withdrawn(therapy: dict, catalog: dict | None = None) -> bool:
    return whole_product_match(therapy, catalog) is not None


def display_mainstream(biomarker: dict, catalog: dict | None = None) -> list[dict]:
    """Mainstream therapies that are not whole-product withdrawn.

    Uses matching.targeting_therapies (the FDA-selection rule), then
    drops whole-product withdrawals. Alphabetical by name.
    """
    from matching import targeting_therapies

    catalog = catalog or load_catalog()
    items = [
        t for t in targeting_therapies(biomarker) if not is_withdrawn(t, catalog)
    ]
    items.sort(key=lambda t: (t.get("name") or "").lower())
    return items


def withdrawn_therapies(biomarker: dict, catalog: dict | None = None) -> list[dict]:
    """Targeting therapies that are whole-product withdrawn, alphabetical."""
    from matching import targeting_therapies

    catalog = catalog or load_catalog()
    items = [
        (t, whole_product_match(t, catalog))
        for t in targeting_therapies(biomarker)
    ]
    out = [{"therapy": t, "entry": e} for t, e in items if e]
    out.sort(key=lambda r: (r["therapy"].get("name") or "").lower())
    return out


def report_catalog_against_snapshot(snap: dict) -> dict:
    """What the catalog catches, for the gate and the QC report."""
    from matching import targeting_therapies

    catalog = load_catalog()
    whole_hits = []
    indication_hits = []
    missing = []
    for entry in catalog.get("entries") or []:
        found = False
        for b in snap.get("biomarkers") or []:
            for t in b.get("therapies") or []:
                if _therapy_keys(t) & _entry_keys(entry):
                    found = True
                    if t in targeting_therapies(b) or t.get("relation") == "targets":
                        whole_hits.append(
                            {
                                "biomarker": b["id"],
                                "therapy": t.get("name"),
                                "entry": entry["id"],
                                "would_have_been_mainstream": t.get("relation") == "targets",
                            }
                        )
        if not found:
            missing.append(entry["id"])
    for entry in catalog.get("indication_level_noted") or []:
        for b in snap.get("biomarkers") or []:
            for t in targeting_therapies(b):
                if _therapy_keys(t) & _entry_keys(entry):
                    indication_hits.append(
                        {
                            "biomarker": b["id"],
                            "therapy": t.get("name"),
                            "entry": entry["id"],
                            "still_mainstream": True,
                            "sure": entry.get("sure"),
                        }
                    )
    return {
        "whole_product_hits": whole_hits,
        "indication_level_hits": indication_hits,
        "stale_entries": missing,
    }
