# Offer Scout architecture

Nothing here is new. The design combines established patterns so the system can grow into four agents
and a management dashboard without rewrites.

## Patterns used

| Pattern | Where | Why |
|---|---|---|
| Intelligence cycle (direction, collection, processing, analysis, dissemination) | `pipeline.py` stages | Standard structure for market/competitive intelligence; each stage is testable alone |
| Medallion layers (bronze / silver / gold) | `raw_records` / `records` / `opportunities` | Raw data is kept untouched, so scoring can be re-run when the rubric changes |
| Ports and adapters (hexagonal) | `collectors/` implement `Collector` | New sources (vendor API, trends export) never touch scoring or reporting |
| Source reliability x information credibility (Admiralty / NATO 4x4 style grading) | `evidence.py` | Makes "how much do we trust this signal" explicit and visible on the dashboard |
| Transactional outbox / event table | `events` table | Agents 2-4 and the dashboard consume the same facts independently, no direct coupling |
| Config as code with human-reviewed priors | `config/*.yaml` | Taxonomy, thresholds and compliance rules change without code changes; priors are reported separately from data |
| Fail-closed governance | `config.py`, `pipeline.py` | auto_publish/auto_ads must be false; SIMULATED runs cannot hand off |

## Data flow

```
 collectors (Etsy API, Meta Ad Library API, CSV imports, synthetic)
        |  RawRecord                          -> bronze: raw_records
        v
 parse -> compliance screen -> classify -> lookback -> dedupe
        |  Record                             -> silver: records
        v
 cluster by subcategory -> score (itemized) -> confidence -> decision
        |  Opportunity (scout-2.0 JSON)       -> gold: opportunities
        v
 safety gates -> handoff (abstractions only) -> events -> Agent 2 / dashboard
```

## Scoring transparency
`score.data_driven_points` comes from observed evidence; `score.analyst_prior_points` comes from the
human-reviewed `attrs` in `keywords.yaml`. A dashboard can show how much of a score is evidence.
Missing data scores zero and appears in `evidence_limitations`.

## Safety gates
1. Hard compliance rules drop records; whole prohibited niches are reported as REJECT with the reason.
2. Condition-specific, dietary, supplement, clinical, veterinary-dosage and academic-fraud signals are never modeled.
3. Handoff contains no competitor titles or copy (`assert_no_verbatim`).
4. HIGH confidence requires authoritative operator data. Ad age or engagement never raises it.
5. SIMULATED data: confidence LOW, no handoff, no recommendation.

## Extending
- New source: subclass `Collector`, register it in `pipeline.build_collectors`, add a config block.
- New niche: add a subcategory in `keywords.yaml` with queries, match_terms, attrs.
- New compliance rule: add to `compliance.yaml`; add a test in `tests/test_compliance.py`.

## Roadmap to the 4-agent system and dashboard
- Agent 2 (Modeler): consumes `scout.opportunity.ready_for_modeling`; produces offer spec + originality check.
- Agent 3 (Publisher): consumes approved offers; drafts listings/checkout; publishing only after human approval.
- Agent 4 (Scaler): reads sales and ad metrics; proposes capped test budgets; spend only after approval.
- Dashboard: reads `runs`, `v_latest_opportunities`, `events` (and later sales tables) from the same database.
