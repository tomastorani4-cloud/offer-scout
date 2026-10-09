# Event contract (shared by Agents 1-4 and the dashboard)

Events live in the SQLite `events` table (transactional outbox). Producers insert; consumers poll with
`Store.pending_events(consumer, event_type)` and acknowledge with `mark_consumed(id, consumer)`.
Each consumer acknowledges independently, so the dashboard and Agent 2 can read the same event.

| event_type                              | producer | consumer(s)        | payload                                                       |
|-----------------------------------------|----------|--------------------|---------------------------------------------------------------|
| scout.run.completed                     | scout    | dashboard          | run_id, data_mode, finalists, rejected_clusters               |
| scout.opportunity.ready_for_modeling    | scout    | modeler (Agent 2)  | handoff payload (see `handoff_to_modeler.schema.json`)        |
| modeler.offer.ready_for_review          | modeler  | human, dashboard   | planned: offer spec + originality check (6+ differences)      |
| publisher.listing.awaiting_approval     | publisher| human, dashboard   | planned: draft listing + checkout config, never auto-published|
| scaler.test.budget_proposal             | scaler   | human, dashboard   | planned: capped test budget; money moves only after approval  |

Rules
- Any event that leads to publishing, spending or messaging customers requires a human approval record.
- `data_mode = SIMULATED` runs never emit `ready_for_modeling` events.
- Dashboard tables to read: `runs`, `opportunities` (view `v_latest_opportunities`), `records`, `events`.
