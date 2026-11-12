# Circuit — Targeted Therapy Explorer

Loop: **idea → issue → agent PR → David’s review and merge → GitHub Pages deploy → usage check**.

The site is a **public** static GitHub Pages site (`https://dmgrok.github.io/targeted-therapy-explorer/`). There is no Fly app. No new API keys or secrets are added by this Circuit. The engine is the **Copilot already present** on the account `dmgrok`. Inference uses the repository secret `COPILOT_GITHUB_TOKEN` (personal-account wiring; see below). Weekly data refreshes open a pull request; only David merges.

## How it works

1. **Idea → issue.** David opens an issue and writes a **specification** in his own words.
2. **Issue → agent PR.** The workflow `circuit-implement` (Copilot engine) runs on `/implement` or `workflow_dispatch`, **admin only** (`roles: [admin]`). It opens a **draft** pull request titled `[circuit] `, reviewer `dmgrok`, via `safe-outputs`, no direct write and no merge, with threat detection. Caps: 20 minutes, 40 turns, 100 AI credits per run, 200 per day, on the existing Copilot subscription. **David merges; the agent does not.**
3. **Review → merge.** **PR gates** (ordinary Actions, no agent) rebuild the site from the committed snapshot and run `tests/test_site.py` (disclaimer, snapshot date, stale banner, schema, citations, matching correctness, no OncoKB, no patient input, no cookies). David reviews and merges. No auto-merge.
4. **Merge → Pages.** A push to `main` runs **Deploy to GitHub Pages**. The published site is the `site/` folder. Source for Pages is **GitHub Actions** (free on a public repository).
5. **Weekly data.** Every Sunday 06:00 UTC, **Weekly snapshot** fetches the public APIs, rebuilds `data/snapshot.json` and `site/`, and **opens a pull request**. It does not merge. “What’s new this week” is the diff against the previous snapshot.
6. **Usage check.** Every Monday 09:00 Europe/Paris (08:00 UTC in winter), **Circuit weekly report** updates a `circuit-rapport` issue with aggregate counts of `[circuit]` pull requests and open issues. No issue text, no personal data, no cookies, no visitor identifiers.

## Files

| File | Type | Trigger | Rights |
|---|---|---|---|
| `.github/workflows/circuit-implement.md` (and the compiled `.lock.yml`) | gh-aw, Copilot engine | `/implement` on an issue, or `workflow_dispatch`. `roles: [admin]` only | Agent is read-only. Writes go through `safe-outputs` `create-pull-request` (draft) and `add-comment`. Network: `defaults`. Caps: 20 min, 40 turns, 100 credits/run, 200/day. Inference: repository secret `COPILOT_GITHUB_TOKEN` (personal repository; see below). No `copilot-requests: write` (that path is for organisations, and it would cause the secret to be ignored). |
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
- Copilot engine already on the `dmgrok` account, wired through the repository secret `COPILOT_GITHUB_TOKEN`. No new subscription and no new API key. The secret is already in place; Idea Lab does not create, read or copy it.
- A legal review comes before any promotion; it did not block this build.
- HAS, INCa and Swissmedic come later.

## Engine authentication: `COPILOT_GITHUB_TOKEN`

`dmgrok/targeted-therapy-explorer` is a **personal** repository, not an organisation. Per the [gh-aw authentication docs](https://github.github.com/gh-aw/reference/auth/), the permission `copilot-requests: write` (Actions token, no secret) is only valid for an organisation with Copilot and centralized billing. For a personal repository, inference uses a repository secret:

- Fine-grained Personal Access Token on David’s personal account (not an organisation), Account permission **Copilot Requests: Read**. Resource owner = user account `dmgrok`. No repository permissions are required on this token: it is used only for Copilot inference.
- Stored as the Actions repository secret named exactly `COPILOT_GITHUB_TOKEN`. This secret is already set. Idea Lab does not create it, does not read it, and does not substitute another token.

Docs: [Authentication](https://github.github.com/gh-aw/reference/auth/) (sections `copilot-requests: write` and `COPILOT_GITHUB_TOKEN`), [quickstart](https://github.github.com/gh-aw/setup/quick-start/).

An admin `/implement` on a specification written by David can run, within the caps, billed against the existing Copilot subscription. The agent opens a draft PR only and does not merge.

## Sources

- gh-aw documentation: [overview](https://github.github.com/gh-aw/introduction/overview/), [frontmatter](https://github.github.com/gh-aw/reference/frontmatter/), [triggers and roles](https://github.github.com/gh-aw/reference/triggers/), [slash commands](https://github.github.com/gh-aw/reference/command-triggers/), [engine authentication](https://github.github.com/gh-aw/reference/auth/), [engines](https://github.github.com/gh-aw/reference/engines/), [network](https://github.github.com/gh-aw/reference/network/), [tools](https://github.github.com/gh-aw/reference/tools/), [safe-outputs PRs](https://github.github.com/gh-aw/reference/safe-outputs-pull-requests/), [threat detection](https://github.github.com/gh-aw/reference/threat-detection/), [github/gh-aw](https://github.com/github/gh-aw).
- [GitHub plans](https://docs.github.com/en/get-started/learning-about-github/githubs-plans), [pricing](https://github.com/pricing), [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [Copilot billing](https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/).
