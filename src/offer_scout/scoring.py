"""Opportunity scoring. Implements the Scout v2 rubric (0-100) with a fully itemized breakdown.

Design rules:
  * Points from observed data are kept separate from analyst priors (config attrs).
  * Missing evidence scores 0 and is listed as a limitation. Nothing is assumed.
  * Persistence never proves profit; it is one indirect signal.
"""
from __future__ import annotations

import statistics
from typing import Any

from .dedupe import saturation_share
from .evidence import is_authoritative
from .models import Record, Score


def _tier(value: float, tiers: list[tuple[float, int]]) -> int:
    for threshold, points in tiers:
        if value >= threshold:
            return points
    return 0


def _distinct_sellers(recs: list[Record]) -> int:
    return len({(r.seller or r.source_id) for r in recs})


def _demand(recs: list[Record], limits: list[str]) -> tuple[int, list[str]]:
    notes: list[str] = []
    recent = [r.recent_review_count_90d for r in recs if r.recent_review_count_90d is not None]
    if recent:
        pts_reviews = _tier(sum(recent), [(150, 8), (60, 6), (20, 4), (5, 2), (1, 1)])
        notes.append(f"reviews: {sum(recent)} in last 90d -> {pts_reviews}")
    else:
        cumulative = sum(r.review_count or 0 for r in recs)
        pts_reviews = _tier(cumulative, [(1000, 5), (300, 4), (100, 3), (20, 2), (1, 1)])
        limits.append("Review dates unavailable: only cumulative review counts (capped at 5 of 8 points)")
        notes.append(f"reviews: {cumulative} cumulative (undated) -> {pts_reviews}")

    pts_sellers = _tier(_distinct_sellers(recs), [(10, 6), (5, 4), (3, 3), (2, 1)])
    notes.append(f"distinct sellers: {_distinct_sellers(recs)} -> {pts_sellers}")

    pts_trend = 0
    series = [r.trend_series for r in recs if r.trend_series and len(r.trend_series) >= 6]
    if series:
        s = max(series, key=len)
        third = max(1, len(s) // 3)
        first, last = statistics.fmean(s[:third]), statistics.fmean(s[-third:])
        if first > 0:
            ratio = last / first
            pts_trend = 6 if ratio >= 1.1 else 4 if ratio >= 0.95 else 0
            notes.append(f"trend ratio last/first third: {ratio:.2f} -> {pts_trend}")
    else:
        limits.append("No search trend series (SEARCH_TREND signal missing)")

    intent = sum(1 for r in recs if r.signal_type == "COMMENT_INTENT")
    pts_intent = _tier(intent, [(10, 5), (5, 3), (1, 1)])
    return min(25, pts_reviews + pts_sellers + pts_trend + pts_intent), notes


def _persistence(recs: list[Record], limits: list[str]) -> tuple[int, list[str]]:
    notes: list[str] = []
    ads = [r for r in recs if r.signal_type == "AD_PERSISTENCE"]
    path_ad = 0
    if ads:
        runtime = max((r.runtime_days or 0) for r in ads)
        p = _tier(runtime, [(45, 15), (30, 12), (14, 8), (7, 4)])
        v = _tier(max(r.variants for r in ads), [(8, 5), (4, 3), (2, 1)])
        path_ad = p + v
        notes.append(f"ad path: runtime {runtime}d -> {p}, variants -> {v}")
    else:
        limits.append("No ad data (AD_PERSISTENCE missing): ad persistence not evaluated")

    mk = [r for r in recs if r.signal_type != "AD_PERSISTENCE"]
    recent = sum(r.recent_review_count_90d or 0 for r in mk)
    sales = sum(r.sales_count_visible or 0 for r in mk)
    cumulative = sum(r.review_count or 0 for r in mk)
    p_recent = _tier(recent, [(150, 15), (60, 12), (20, 8), (5, 4)])
    p_sales = _tier(sales, [(1500, 15), (500, 12), (150, 8), (30, 4)])
    p_cum = _tier(cumulative, [(1000, 8), (300, 6), (100, 4), (20, 2)])
    base = max(p_recent, p_sales, p_cum)
    multi = _tier(_distinct_sellers(mk), [(10, 5), (5, 3), (3, 2)]) if mk else 0
    path_mk = base + multi
    notes.append(f"marketplace path: base {base} + multi-seller {multi}")
    # Use the larger path, never the sum (rubric rule).
    return min(20, max(path_ad, path_mk)), notes


def _ticket_points(recs: list[Record], price_min: float, price_max: float, limits: list[str]) -> tuple[int, float | None]:
    prices = [r.price_usd for r in recs if r.price_usd]
    if not prices:
        limits.append("No visible prices: ticket compatibility not scored")
        return 0, None
    med = statistics.median(prices)
    if price_min <= med <= price_max:
        return 5, med
    if 5 <= med < price_min or price_max < med <= 70:
        return 3, med
    return 1, med


def score_cluster(
    recs: list[Record],
    sub_cfg: dict[str, Any],
    settings: Any,
    n_rejected: int,
    n_total: int,
    flag_counts: dict[str, int],
) -> Score:
    limits: list[str] = []
    notes: list[str] = []
    attrs = sub_cfg.get("attrs", {}) or {}
    penalties: list[dict[str, Any]] = []
    price_cfg = settings.run["price_range_usd"]

    if sub_cfg.get("blocked"):
        penalties.append({"reason": f"prohibited niche: {sub_cfg.get('blocked_reason', 'out of scope')}", "points": -100})
        return Score(0, 0, 0, 0, 0, 0, penalties, 0, 0, [], limits)

    demand, n1 = _demand(recs, limits)
    persistence, n2 = _persistence(recs, limits)
    notes += n1 + n2

    cap = lambda k, m=5: min(m, int(attrs.get(k, 0)))  # noqa: E731
    quality = sum(cap(k) for k in ("specific_problem", "identifiable_audience", "demonstrable", "auto_delivery", "derivatives"))
    ticket, median_price = _ticket_points(recs, price_cfg["min"], price_cfg["max"], limits)
    viability = ticket + cap("support_load") + cap("marginal_cost") + cap("upsell_potential")
    differentiation = cap("underserved_segment", 3) + cap("specific_application", 3) + cap("ux_improvable", 2) + cap("bundle_original", 2)

    data_driven = demand + persistence + ticket
    analyst_prior = (quality + viability - ticket) + differentiation

    n = max(1, len(recs))
    sc = settings.scoring
    if n_total and n_rejected / n_total >= 0.5:
        penalties.append({"reason": "majority of records tripped hard compliance rules", "points": -100})
    if flag_counts.get("ip_brand", 0) / n >= 0.2:
        penalties.append({"reason": "high intellectual property risk", "points": -50})
    if flag_counts.get("unproven_claim", 0) / n >= 0.2:
        penalties.append({"reason": "dependence on unproven claims", "points": -40})
    if median_price is not None and median_price < sc.get("price_floor_penalty_below_usd", 5):
        penalties.append({"reason": f"median price ${median_price:.2f} too low to fund ads", "points": -25})
    if int(attrs.get("support_load", 5)) <= 1:
        penalties.append({"reason": "heavy individual support load", "points": -20})
    if len(recs) >= sc.get("saturation_min_records", 10):
        listings = [r for r in recs if r.signal_type in ("MARKETPLACE_SALES", "REVIEW_VELOCITY")]
        share = saturation_share(listings, sc.get("saturation_similarity", 0.7)) if len(listings) >= sc.get("saturation_min_records", 10) else 0.0
        if share >= sc.get("saturation_share", 0.5):
            penalties.append({"reason": f"low differentiation: {share:.0%} of listings are near-duplicates", "points": -15})
    if attrs.get("platform_dependent"):
        penalties.append({"reason": "depends on a third-party platform or brand", "points": -15})

    raw_total = demand + persistence + quality + viability + differentiation + sum(p["points"] for p in penalties)
    total = max(0, min(100, raw_total))
    return Score(total, demand, persistence, quality, viability, differentiation, penalties,
                 data_driven, analyst_prior, notes, limits)


def confidence(recs: list[Record]) -> str:
    """LOW / MEDIUM / HIGH. HIGH only with authoritative operator data (never from ad age or engagement)."""
    if any(r.signal_type == "OPERATOR_DATA" and is_authoritative(r.reliability) and not r.simulated for r in recs):
        return "HIGH"
    types = {r.signal_type for r in recs}
    platforms = {r.source_platform for r in recs}
    if len(types) >= 3 and len(platforms) >= 2 and not any(r.simulated for r in recs):
        return "MEDIUM"
    return "LOW"


def decide(score: int, conf: str, blocked: bool, majority_rejected: bool) -> tuple[str, str]:
    if blocked:
        return "REJECT", "Prohibited niche (see compliance flags)."
    if majority_rejected:
        return "REJECT", "Most observed listings trip hard compliance rules."
    if score < 40:
        return "REJECT", "Score below 40."
    if score < 65:
        return "WATCH", "Score 40-64: evidence insufficient or market weak."
    if score >= 80:
        if conf == "LOW":
            return "VALIDATE", "Score >= 80 but confidence is LOW, so capped at VALIDATE."
        return "PRIORITY", "Score >= 80 with multiple independent signals."
    return "VALIDATE", "Score 65-79: validate cheaply before building."
