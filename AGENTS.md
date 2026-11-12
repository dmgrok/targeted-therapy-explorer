# Agent notes — Targeted Therapy Explorer

Follow these rules when implementing a David-written specification. Only David merges.

## What this is

A static, English, public GitHub Pages site. It maps a closed biomarker list to approved targeted therapies and recruiting trials. It is informational and non-individual. It is not medical advice and is not a medical device.

## Hard rules

- Keep the notice **“Not medical advice. Talk to your oncologist.”** on every page, in the header and the footer, unmissable.
- Keep the snapshot date on every page, and the stale banner when the snapshot is more than eight days old.
- No patient input beyond picking a biomarker from the closed list (EGFR, ALK, BRAF V600E, KRAS G12C, HER2, NTRK, MSI-H/dMMR). No uploads, no free-text clinical fields, no cookies, no analytics, no accounts, no third-party scripts.
- Every therapy and trial row must cite a public source with a URL.
- **Do not use OncoKB**, in any form.
- Do not add API keys or secrets. Do not add a Fly app.
- Do not collect personal or health data.
- Data snapshots come only from the allowed public sources in `scripts/fetch_snapshot.py`.
- Design: David’s Risograph identity only. Paper `#f4efe4`, teal `#1b4f4c`, pinks `#b02058` / `#d13a72`, **no orange**. Barlow Condensed (headings) and Source Sans 3 (body), already self-hosted. Inks and paper texture, serious editorial look. Never a Claude/Anthropic (cream, serif, rust orange), Copilot, Codex or Grok look.
- One idea, one small pull request. Do not merge.

## Before requesting the pull request

```sh
python3 scripts/build_site.py
python3 tests/test_site.py
```

## Pull request

Request **one** draft pull request via safe-outputs (`create-pull-request`). The title must start with `[circuit] `. Write the body in English. Include `Closes #<issue>`. Assign and request review from `dmgrok`. **Do not merge.**
