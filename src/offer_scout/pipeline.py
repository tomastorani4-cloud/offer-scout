"""Pipeline = the classic intelligence cycle, implemented as stages:

  1 Planning/direction  -> queries and thresholds from config
  2 Collection          -> adapters (bronze: raw_records)
  3 Processing          -> normalize, compliance screen, dedupe (silver: records)
  4 Analysis            -> cluster, score, decide (gold: opportunities)
  5 Dissemination       -> JSON report, SQLite, events for Agent 2 and the dashboard
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .collectors import (Collector, CollectorError, CsvImportCollector, EtsyApiCollector,
                         MetaAdLibraryCollector, ParseContext, SyntheticCollector)
from .compliance import ComplianceScreen
from .config import Settings
from .dedupe import dedupe
from .evidence import grade
from .handoff import build_handoff
from .markets import build_market_ideas, coverage_by_market
from .models import RawRecord, Record
from .normalize import classify, now_iso
from .report import build_opportunity, validate_report
from .scoring import confidence, decide, score_cluster
from .store import Store


def build_collectors(settings: Settings, simulate: bool, auto: bool = False) -> list[Collector]:
    """auto=True: enable every source whose credentials/files are present (for scheduled runs)."""
    import os
    src = settings.sources
    if auto and not simulate:
        out_auto: list[Collector] = []
        if os.environ.get("ETSY_API_KEY"):
            c = src.get("etsy_api", {})
            out_auto.append(EtsyApiCollector(min_interval_s=c.get("min_interval_s", 0.4), review_lookup_top_n=c.get("review_lookup_top_n", 30)))
        if os.environ.get("META_AD_LIBRARY_TOKEN"):
            c = src.get("meta_ad_library", {})
            out_auto.append(MetaAdLibraryCollector(api_version=c.get("api_version", "v21.0"), min_interval_s=c.get("min_interval_s", 1.0)))
        inbox = sorted(str(p) for p in Path(src.get("csv_import", {}).get("inbox_dir", "data/inbox")).glob("*.csv"))
        if inbox:
            out_auto.append(CsvImportCollector(inbox))
        return out_auto
    if simulate:
        return [SyntheticCollector(settings.subcategories(), seed=src.get("synthetic", {}).get("seed", 7))]
    out: list[Collector] = []
    if src.get("etsy_api", {}).get("enabled"):
        c = src["etsy_api"]
        out.append(EtsyApiCollector(min_interval_s=c.get("min_interval_s", 0.4), review_lookup_top_n=c.get("review_lookup_top_n", 30)))
    if src.get("meta_ad_library", {}).get("enabled"):
        c = src["meta_ad_library"]
        out.append(MetaAdLibraryCollector(api_version=c.get("api_version", "v21.0"), min_interval_s=c.get("min_interval_s", 1.0)))
    if src.get("csv_import", {}).get("enabled"):
        out.append(CsvImportCollector(src["csv_import"].get("paths", [])))
    if src.get("synthetic", {}).get("enabled"):
        out.append(SyntheticCollector(settings.subcategories(), seed=src["synthetic"].get("seed", 7)))
    return out


def _queries(settings: Settings, country: str | None = None) -> list[str]:
    """Queries for a country's market language (English default). Blocked niches are scanned only to report them."""
    wanted = set(settings.run["categories"])
    lang = settings.country_language(country) or "en"
    qs: list[str] = []
    for sub in settings.subcategories().values():
        if sub["category"] in wanted or sub["category"] == "blocked":
            qs.extend(sub.get("queries", []) if lang == "en" else (sub.get("queries_i18n") or {}).get(lang, []))
    return list(dict.fromkeys(qs))


def run_pipeline(
    settings: Settings, collectors: list[Collector], store: Store,
    out_dir: str | Path | None = None, now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    run_id = f"scout-{now:%Y%m%dT%H%M%S}"
    subs = settings.subcategories()
    screen = ComplianceScreen(settings.compliance)
    ctx = ParseContext(fx=settings.fx, now=now, lookback_days=settings.run["lookback_days"])
    simulated_run = any(c.simulated for c in collectors)
    data_mode = "SIMULATED" if simulated_run else "LIVE"
    store.start_run(run_id, now_iso(now), data_mode, settings.raw)

    failures: list[str] = []
    seen_ids: set[str] = set()
    records: list[Record] = []
    raw_count = 0
    limit = settings.run["max_results_per_category"]

    # 2 + 3a: collect and normalize
    for col in collectors:
        for country in settings.run["countries"]:
            queries = ["*"] if col.name == "csv_import" else _queries(settings, country)
            failures.extend(w for w in col.coverage_warnings(country) if w not in failures)
            if col.name == "csv_import" and country != settings.run["countries"][0]:
                continue                          # CSV rows are loaded once, not per country
            for q in queries:
                try:
                    raws: list[RawRecord] = col.collect(q, country, limit)
                except CollectorError as exc:
                    msg = f"{col.name}: {exc}"
                    if msg not in failures:
                        failures.append(msg)
                    break  # do not hammer a failing source for the rest of this country
                raw_count += len(raws)
                store.add_raw(run_id, raws)
                for raw in raws:
                    rec = col.parse(raw, ctx)
                    if rec is None or rec.record_id in seen_ids:
                        continue
                    seen_ids.add(rec.record_id)
                    if not rec.reliability:
                        rec.reliability = grade(col.source_class, rec.signal_type)
                    rec.simulated = rec.simulated or raw.simulated
                    rec.language = settings.country_language(rec.country)
                    rec.country_verified = bool(col.country_scoped and rec.country)
                    records.append(rec)

    # 3b: screen, classify, lookback
    reject_reasons: Counter[str] = Counter()
    cutoff = now - timedelta(days=ctx.lookback_days)
    for rec in records:
        res = screen.evaluate(rec.text)
        rec.compliance = res.to_dict()
        if rec.language and rec.language not in settings.supported_languages():
            rec.rejected, rec.reject_reasons = True, ["compliance_language_unsupported"]
            reject_reasons["compliance_language_unsupported"] += 1
            continue
        rec.subcategory = res.assign_subcategory or classify(rec.text, subs)
        rec.category = subs[rec.subcategory]["category"] if rec.subcategory else None
        if rec.subcategory is None:
            rec.rejected, rec.reject_reasons = True, ["unclassified"]
        elif res.hard_reject:
            rec.rejected, rec.reject_reasons = True, list(res.flags)
        elif rec.signal_type == "AD_PERSISTENCE" and rec.date_last_seen:
            from .normalize import parse_dt
            last = parse_dt(rec.date_last_seen)
            if last and last < cutoff:
                rec.rejected, rec.reject_reasons = True, ["outside_lookback"]
        for reason in rec.reject_reasons:
            reject_reasons[reason] += 1

    # dedupe only the evidence we keep
    kept_all = dedupe([r for r in records if not r.rejected])
    kept_ids = {r.record_id for r in kept_all}
    for r in records:
        if not r.rejected and r.record_id not in kept_ids:
            r.rejected, r.reject_reasons = True, ["merged_duplicate"]
            reject_reasons["merged_duplicate"] += 1
    store.add_records(run_id, records)

    # 4: cluster by subcategory, score, decide
    clusters: dict[str, list[Record]] = defaultdict(list)
    for r in records:
        if r.subcategory:
            clusters[r.subcategory].append(r)

    coverage = coverage_by_market(records, settings)
    opps: list[dict[str, Any]] = []
    handoff_payloads: list[dict[str, Any]] = []
    for sub_id, all_recs in clusters.items():
        cfg = subs[sub_id]
        kept = [r for r in all_recs if not r.rejected]
        hard = [r for r in all_recs if r.rejected and "merged_duplicate" not in r.reject_reasons and "outside_lookback" not in r.reject_reasons]
        n_total = len(kept) + len(hard)
        flags: Counter[str] = Counter(f for r in all_recs for f in r.compliance.get("flags", []))
        score = score_cluster(kept, cfg, settings, n_rejected=len(hard), n_total=n_total, flag_counts=flags)
        conf = confidence(kept)
        majority = bool(n_total) and len(hard) / n_total >= 0.5
        decision, reason = decide(score.total, conf, bool(cfg.get("blocked")), majority)
        opp_id = "OPP-" + hashlib.sha1(sub_id.encode()).hexdigest()[:8].upper()
        opp = build_opportunity(opp_id, sub_id, cfg, kept, all_recs, score, conf, decision, reason, flags, now_iso(now))
        opp["market_ideas"] = [] if decision == "REJECT" else build_market_ideas(sub_id, cfg, kept, coverage, settings)
        opps.append(opp)

    opps.sort(key=lambda o: -o["score"]["total"])
    rejected_opps = [o for o in opps if o["decision"] == "REJECT"]
    live_opps = [o for o in opps if o["decision"] != "REJECT"][: settings.run["max_finalists_per_run"]]

    # safety gates for handoff: not simulated, VALIDATE/PRIORITY, meets min score, capped count
    slots = settings.run["max_offers_to_model"]
    for o in live_opps:
        if (not simulated_run and o["decision"] in {"VALIDATE", "PRIORITY"}
                and o["score"]["total"] >= settings.run["min_opportunity_score"] and slots > 0):
            sub_recs = [r for r in clusters[o["subcategory"]] if not r.rejected]
            o["handoff_to_modeler"] = True
            handoff_payloads.append(build_handoff(o, subs[o["subcategory"]], sub_recs))
            slots -= 1

    all_out = live_opps + rejected_opps
    top = next((o for o in live_opps if o["decision"] in {"VALIDATE", "PRIORITY"}), None)
    report = {
        "schema_version": "scout-2.0",
        "run": {
            "run_id": run_id, "generated_at_utc": now_iso(now), "data_mode": data_mode,
            "countries": settings.run["countries"], "categories": settings.run["categories"],
            "sources_used": [c.name for c in collectors], "source_failures": failures,
            "records_analyzed": len(records), "records_rejected": sum(1 for r in records if r.rejected),
            "rejection_reasons": dict(reject_reasons), "raw_records_collected": raw_count,
            "finalists": len(live_opps),
        },
        "market_summary": _market_summary(opps),
        "markets": {
            "coverage_records_by_market": coverage,
            "labels": {k: v["label"] for k, v in settings.markets.items()},
            "regions": {k: v["region"] for k, v in settings.markets.items()},
            "notes": "Market evidence is grouped by query language. Etsy listings are global; country is not verified for them.",
        },
        "opportunities": all_out,
        "recommended_next_action": {
            "selected_opportunity_id": top["opportunity_id"] if top and not simulated_run else None,
            "reason": ("SIMULATED run: no action recommended; validate the pipeline only." if simulated_run
                       else (top["decision_reason"] if top else "No opportunity reached VALIDATE.")),
            "actions_before_creation": ["Collect dated reviews and ad persistence for the top listings",
                                        "Review compliance flags and obtain human approval"],
            "actions_before_publication": ["Human approval of offer, claims and disclaimers", "Originality test in Agent 2"],
            "human_approval_required": True,
        },
    }
    problems = validate_report(report)
    if problems:
        store.finish_run(run_id, now_iso(now), "failed", data_mode)
        raise RuntimeError("report failed validation: " + "; ".join(problems))

    store.add_opportunities(run_id, all_out)
    store.emit_event(now_iso(now), "scout", "scout.run.completed", run_id,
                     {"run_id": run_id, "data_mode": data_mode, "finalists": len(live_opps), "rejected_clusters": len(rejected_opps)})
    for payload in handoff_payloads:
        store.emit_event(now_iso(now), "scout", "scout.opportunity.ready_for_modeling", run_id, payload)
    store.finish_run(run_id, now_iso(now), "completed", data_mode)

    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{run_id}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _market_summary(opps: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for cat in ("pets", "education", "non_clinical_wellness", "small_business", "creator_tools", "planning_lifestyle"):
        mine = [o for o in opps if o["category"] == cat]
        summary[cat] = {
            "patterns": [f"{o['subcategory']}: score {o['score']['total']}, {o['decision']}" for o in mine],
            "promising_subcategories": [o["subcategory"] for o in mine if o["decision"] in {"VALIDATE", "PRIORITY"}],
            "saturation_signals": [p["reason"] for o in mine for p in o["score"]["penalties"] if "differentiation" in p["reason"]],
            "risks": sorted({f for o in mine for f in o["compliance"]["flags"]}),
        }
    return summary
