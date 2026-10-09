# Offer Scout (Agent 1)

Scans public demand signals for low-ticket digital products in **pets**, **education** and
**non-clinical wellness**, scores them with an itemized rubric, screens compliance, and hands
vetted *abstractions* (never competitor copy) to the Modeler (Agent 2).

## Quick start

```bash
pip install pyyaml            # core; add `requests` for live sources
make test                     # 56 tests, standard library unittest
make demo                     # SIMULATED run, safe to try, never for decisions
```

Live use: enable sources in `config/settings.yaml`, export credentials
(`ETSY_API_KEY`, `META_AD_LIBRARY_TOKEN`), then `python -m offer_scout.cli run` (set `PYTHONPATH=src`).

Other commands: `events <consumer>` (pending events for an agent/dashboard), `top` (latest ranking).

## What is verified and what is not

- Verified here: normalization, compliance rules, scoring, dedupe, handoff gates, SQLite store/events,
  report validation (56 passing tests, offline).
- **Not live-tested** (no network in the build environment): the Etsy and Meta adapters. They are written
  against the official APIs; confirm field names and your access level against the current docs first.
- **Meta Ad Library coverage:** to our knowledge the API returns commercial ads only for EU/UK delivery.
  For US/CA/AU ad persistence, export from the Ad Library UI (or a licensed vendor) and load via
  `csv_import`. The tool prints this warning in `source_failures`.
- **Google Trends:** no adapter is bundled. Load exports through `csv_import` (`trend_series` column) or add
  an adapter for an authorized API.
- Etsy API commercial use and data caching are governed by Etsy's terms and key approval.

## Confidence and decisions
- LOW: indirect signals. MEDIUM: 3+ signal types from 2+ platforms. HIGH: authoritative operator data only.
- PRIORITY needs score >= 80 and confidence above LOW. SIMULATED runs never hand off.
- Scores split into `data_driven_points` and `analyst_prior_points` (human-reviewed `attrs` in `keywords.yaml`).

## Health niche policy
Dietary or supplement interventions for conditions (for example autism diets), clinical claims, condition-specific
trackers and weight-loss plans are scanned only so they can be **reported as REJECT with the reason**. They are
never modeled. A parent/caregiver *organization* niche (`special_needs_family_organizer`) is included, with
mandatory human review, and no therapeutic, dietary or outcome claims.

## Layout
`src/offer_scout/` collectors, compliance, scoring, pipeline, store, handoff, report, CLI.
`config/` settings, taxonomy, compliance rules. `contracts/` event and handoff contracts. `docs/ARCHITECTURE.md`.

## Automation and online dashboard
See `docs/DEPLOY.md`. `offer-scout run --auto --dashboard-dir site/data` runs every source whose credentials/CSVs exist and writes `latest/history/status.json`; `site/index.html` is the mobile dashboard that reads them.

## Markets and cross-market ideas
`config/settings.yaml: markets` defines language-markets (en = US and English markets, pt = Brazil, de/fr/es = Europe).
`config/localization.yaml` holds translated queries and classification terms (best effort: have a native speaker review).
`markets.py` proposes publication ideas only where evidence supports them (GAP_SUPPORTED), marks missing data as
UNVERIFIED, and never calls an unsearched language a gap. Compliance rules cover en/pt/es/de/fr; records in any other
language are rejected (fail closed). Step by step for non-technical use: `docs/ROTEIRO_LEIGO.md`.
