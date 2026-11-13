# Targeted Therapy Explorer

**Not medical advice. Talk to your oncologist.**

This site is general information only. It is not medical advice, a diagnosis or a treatment recommendation, and it is not a medical device. It does not take account of any person’s medical situation. Talk to your oncologist before making any decision about your care.

A watch-and-explain explorer that maps a closed list of tumour biomarkers to **approved targeted therapies** and **recruiting clinical trials**, using public sources only. Every claim cites its source. Biomarker pages open with a plain-language introduction and a two-step map of options, each tagged Mainstream, Trials or On the edge. Raw label text, CIViC records and PubMed cards sit behind a Sources toggle. Plain-language lines are committed in `data/plain/` and are not generated in the browser.

- Live site: <https://dmgrok.github.io/targeted-therapy-explorer/>
- Repository: <https://github.com/dmgrok/targeted-therapy-explorer>

## Biomarkers

EGFR, ALK, BRAF V600E, KRAS G12C, HER2, NTRK, MSI-H / dMMR.

There is no search box for clinical information, no file upload, and no account. A country filter (including France and Switzerland) runs in the browser on the already-downloaded trial list.

## Sources

ClinicalTrials.gov API v2, openFDA / Drugs@FDA labels, the FDA pharmacogenomic-biomarker and companion-diagnostic tables, EMA medicine data, and CIViC (CC0). Literature appears only as PubMed citation cards (title, authors, journal, date, link — no abstracts). **OncoKB is not used.**

Licences, attribution and the snapshot date are on the [About & sources](https://dmgrok.github.io/targeted-therapy-explorer/about.html) page.

## Refresh and Circuit

A weekly GitHub Action rebuilds the static snapshot and opens a pull request. Nothing goes live until that pull request is merged. “What’s new this week” is the difference between snapshots. If a snapshot is more than eight days old, every page shows a stale-data banner.

The idea → issue → agent PR → review → deploy loop is described in [CIRCUIT.md](CIRCUIT.md). The agent engine is parked.

## Build locally

```sh
python3 scripts/fetch_snapshot.py      # talks to public APIs, no keys
python3 scripts/generate_plain.py      # only when the snapshot changed; review the JSON
python3 scripts/build_site.py          # fails if plain text is stale or unsourced
python3 tests/test_site.py             # must print PASS
python3 tests/test_plain.py            # must print PASS
```

Then open `site/index.html`. The committed snapshot in `data/snapshot.json` is enough to rebuild the site without the network.

## Licence

The **code** is [MIT](LICENSE). The **data** remains under each source’s own terms (see About & sources).
