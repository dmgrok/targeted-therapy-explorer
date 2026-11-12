# Circuit — Targeted Therapy Explorer

Loop: **idea → issue → agent PR → David’s review and merge → GitHub Pages deploy → usage check**.

The site is a **public** static GitHub Pages site (`https://dmgrok.github.io/targeted-therapy-explorer/`). There is no Fly app. No secrets are added. The Copilot engine is **parked** until David decides. Weekly data refreshes open a pull request; only David merges.

## How it works

1. **Idea → issue.** David opens an issue and writes a **specification** in his own words.
2. **Issue → agent PR (parked).** The workflow `circuit-implement` is compiled and ready (`/implement` or `workflow_dispatch`, **admin only**). It has not been launched. It needs David’s decision on the engine. When it runs: a **draft** pull request titled `[circuit] `, reviewer `dmgrok`, via `safe-outputs`, no direct write and no merge, with threat detection.
3. **Review → merge.** **PR gates** (ordinary Actions, no agent) rebuild the site from the committed snapshot and run `tests/test_site.py` (disclaimer, snapshot date, stale banner, schema, citations, no OncoKB, no patient input, no cookies). David reviews and merges. No auto-merge.
4. **Merge → Pages.** A push to `main` runs **Deploy to GitHub Pages**. The published site is the `site/` folder. Source for Pages is **GitHub Actions** (free on a public repository).
5. **Weekly data.** Every Sunday 06:00 UTC, **Weekly snapshot** fetches the public APIs, rebuilds `data/snapshot.json` and `site/`, and **opens a pull request**. It does not merge. “What’s new this week” is the diff against the previous snapshot.
6. **Usage check.** Every Monday 09:00 Europe/Paris (08:00 UTC in winter), **Circuit weekly report** updates a `circuit-rapport` issue with aggregate counts of `[circuit]` pull requests and open issues. No issue text, no personal data, no cookies, no visitor identifiers.

## Files

| File | Type | Trigger | Rights |
|---|---|---|---|
| `.github/workflows/circuit-implement.md` (and the compiled `.lock.yml`) | gh-aw, Copilot engine **parked** | `/implement` on an issue, or `workflow_dispatch`. `roles: [admin]` only | Agent is read-only. Writes go through `safe-outputs` `create-pull-request` (draft) and `add-comment`. Caps: 20 min, 40 turns, 100 credits/run, 200/day. **Do not run** until David has chosen the engine. |
| `.github/workflows/pr-gates.yml` | Ordinary Actions | every pull request, and push to `main` | `contents: read` |
| `.github/workflows/pages-deploy.yml` | Ordinary Actions | push to `main`, or manual | `contents: read`, `pages: write`, `id-token: write` |
| `.github/workflows/data-refresh.yml` | Ordinary Actions | Sunday 06:00 UTC, or manual | `contents: write`, `pull-requests: write`. Opens a PR; no auto-merge |
| `.github/workflows/circuit-usage.yml` | Ordinary Actions | Monday 08:00 UTC, or manual | `contents: read`, `issues: write`, `pull-requests: read`. Counts only |
| `.github/CODEOWNERS` | documentation | — | `.github/`, `scripts/`, `data/` for `@dmgrok` |
| `.github/workflows/aw.json` | gh-aw | — | `strict: true` |

## Safety rules the agent (and every PR) must keep

- Every page carries **“Not medical advice. Talk to your oncologist.”** and the snapshot date, plus a stale banner if the snapshot is more than eight days old.
- No patient input beyond picking a biomarker from the closed list. No uploads, no free-text clinical fields, no cookies, no analytics.
- No OncoKB. No new API keys. No secrets in the repository.
- Every therapy and trial row cites a public source with a URL.
- Do not merge. Only David merges.

## Decisions already taken

- Public repository `dmgrok/targeted-therapy-explorer`. English site.
- GitHub Pages only, no Fly, no GitHub Pro spend.
- Weekly snapshot pull requests; David merges.
- Closed biomarker list: EGFR, ALK, BRAF V600E, KRAS G12C, HER2, NTRK, MSI-H/dMMR.
- Copilot engine parked; no API keys.
- A legal review comes before any promotion; it did not block this build.
- HAS, INCa and Swissmedic come later.
