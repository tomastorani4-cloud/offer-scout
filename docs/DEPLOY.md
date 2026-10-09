# Automatic scans + online dashboard (GitHub Actions + Pages)

Flow: schedule -> Scout runs in the cloud -> writes `site/data/*.json` -> Pages serves `site/` -> the dashboard
reads those files. The dashboard re-reads every 5 minutes and when you reopen the tab.

## One-time setup (needs a computer, about 20 minutes; afterwards everything works from the iPhone)
1. Create a **private** GitHub repository and upload the contents of this folder (including `.github/`).
2. Settings > Pages > Build and deployment > Source: **GitHub Actions**.
3. Settings > Secrets and variables > Actions > New secret (only the ones you have):
   - `ETSY_API_KEY`  (Etsy developer app, needs approval)
   - `META_AD_LIBRARY_TOKEN`  (Meta developer app, identity verification)
4. Actions tab > "Offer Scout" > Run workflow. The dashboard URL appears in the deploy step and in Settings > Pages.
   Add it to the iPhone home screen (Safari > Share > Add to Home Screen).

## What runs by itself
- Every Monday 06:00 (Sao Paulo), plus whenever a CSV is added to `data/inbox/`.
- Tests run first; if the code is broken the run stops and the dashboard shows the last good data.
- No credentials and no CSVs: the run is a no-op and the dashboard says "Sem fontes configuradas".
- Failures show on the dashboard (red box) instead of silently serving old numbers.

## What automation can NOT see (be realistic)
- Meta Ad Library API: to our knowledge only EU/UK commercial ads. US/CA/AU need an export dropped in `data/inbox/`
  (CSV columns are documented in `collectors/csv_import.py`) or a licensed ads-intelligence vendor.
- TikTok: no official API we know of for these data. Vendor or manual export only.
- Etsy: needs an approved key; review dates are the main persistence signal there.
Until a source is live, confidence stays LOW and nothing is handed to Agent 2.

## Privacy warning
GitHub Pages sites are publicly reachable by URL even when the repository is private (unless you have an
Enterprise plan). The data is analysis of public listings, but your scores and decisions would be visible to
anyone with the link. To keep it private, host `site/` on Cloudflare Pages behind Cloudflare Access (or similar)
instead; the dashboard is plain static files and works anywhere.

## Cost
Public-repo Actions minutes are free; private repos have a monthly free quota (check current limits).
A weekly run takes a couple of minutes.
