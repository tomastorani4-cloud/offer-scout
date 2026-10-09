"""Cross-market publication ideas, derived from evidence (not from vibes).

Logic: for each niche, find language-markets with proven supply (>= min_source_sellers distinct sellers) and compare
with markets that look thin (<= thin_target_sellers) AND where the sources demonstrably returned data
(>= min_coverage_records in the whole run). Thin supply plus verified coverage -> GAP_SUPPORTED.
No coverage -> UNVERIFIED (we cannot tell "no competitors" from "we could not look"). Thin supply may also mean
low demand, so every idea carries that caveat and a next step to check local demand before building.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

from .models import Record

STATUSES = {"GAP_SUPPORTED", "COMPETITIVE", "UNVERIFIED"}
CAVEAT = ("Few or no competing listings can mean low demand, not opportunity. Check local search interest and "
          "buyer questions before building.")


def coverage_by_market(all_records: list[Record], settings: Any) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in all_records:
        if r.language:
            out[r.language] += 1
    return {lang: out.get(lang, 0) for lang in settings.markets}


def _stats(recs: list[Record]) -> dict[str, Any]:
    prices = [r.price_usd for r in recs if r.price_usd]
    return {
        "sellers": len({r.seller or r.source_id for r in recs}),
        "listings": len(recs),
        "median_price_usd": round(statistics.median(prices), 2) if prices else None,
        "reviews_cumulative": sum(r.review_count or 0 for r in recs),
        "country_verified_share": round(sum(1 for r in recs if r.country_verified) / len(recs), 2) if recs else None,
        "signal_types": sorted({r.signal_type for r in recs}),
    }


def _local_price(usd: float | None, currency: str, fx: dict[str, float]) -> dict[str, Any] | None:
    rate = fx.get(currency)
    if usd is None or not rate:
        return None
    return {"observed_source_median_usd": usd, "currency": currency, "converted_median": round(usd / rate, 2),
            "note": "Currency conversion only (placeholder FX). Purchasing power and local price anchors differ; validate locally."}


def build_market_ideas(sub_id: str, sub_cfg: dict[str, Any], kept: list[Record], coverage: dict[str, int], settings: Any) -> list[dict[str, Any]]:
    if sub_cfg.get("blocked"):
        return []
    mi = settings.raw["market_ideas"]
    markets = settings.markets
    by_lang: dict[str, list[Record]] = defaultdict(list)
    for r in kept:
        if r.language:
            by_lang[r.language].append(r)
    stats = {lang: _stats(by_lang.get(lang, [])) for lang in markets}
    sources = [l for l, st in stats.items() if st["sellers"] >= mi["min_source_sellers"]]
    if not sources:
        return []                       # nothing proven anywhere: no basis for a cross-market idea
    best = max(sources, key=lambda l: (stats[l]["sellers"], stats[l]["reviews_cumulative"]))
    simulated = any(r.simulated for r in kept)
    searched = {"en", *(sub_cfg.get("queries_i18n") or {}).keys()}
    ideas: list[dict[str, Any]] = []
    for lang, m in markets.items():
        if lang in sources:
            continue                    # supply already proven there: not an expansion target
        st, cov = stats[lang], coverage.get(lang, 0)
        if lang not in searched:
            status, why = "UNVERIFIED", (f"This niche has no search queries in {m['label']}'s language yet, so the absence of "
                                         "listings means nothing. Add translated queries in config/localization.yaml and rerun.")
        elif cov < mi["min_coverage_records"]:
            status, why = "UNVERIFIED", (f"No usable data returned for {m['label']} in this run ({cov} records). "
                                         "We cannot tell an empty market from a source that does not cover it.")
        elif st["sellers"] <= mi["thin_target_sellers"]:
            status, why = "GAP_SUPPORTED", (f"{stats[best]['sellers']} sellers in {markets[best]['label']} versus "
                                            f"{st['sellers']} seller(s) in {m['label']} despite {cov} records collected there.")
        else:
            status, why = "COMPETITIVE", f"{st['sellers']} sellers already serve {m['label']}; enter only with a clearly narrower sub-niche."
        conf = "LOW"
        if status == "GAP_SUPPORTED" and not simulated and len(stats[best]["signal_types"]) >= 2:
            conf = "MEDIUM"
        ideas.append({
            "target_market": lang, "target_label": m["label"], "target_region": m["region"], "currency": m["currency"],
            "source_market": best, "source_label": markets[best]["label"],
            "status": status, "confidence": conf, "rationale": why, "caveat": CAVEAT,
            "source_evidence": stats[best], "target_evidence": {**st, "coverage_records": cov},
            "price_hypothesis": _local_price(stats[best]["median_price_usd"], m["currency"], settings.fx),
            "adaptation": [
                f"Localize for {m['label']} (examples, formats, tone), not a literal translation",
                *( ["Native-speaker review of every customer-facing text"] if lang != "en" else [] ),
            ],
            "regional_notes": mi["notes"].get(m["region"], []),
            "requires_human_review": bool(sub_cfg.get("requires_human_review")) or lang != "en",
            "simulated": simulated,
            "next_steps": ["Check local demand (search interest export for the target country) before building",
                           "Read local competitor reviews for objections", "Approve the localized offer brief (Agent 2)"],
        })
    order = {"GAP_SUPPORTED": 0, "UNVERIFIED": 1, "COMPETITIVE": 2}
    ideas.sort(key=lambda i: (order[i["status"]], i["target_market"]))
    return ideas
