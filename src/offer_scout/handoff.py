"""Handoff contract Scout -> Modeler (Agent 2).

Only abstractions cross this boundary: audience, problem, categories, price band, structure,
gaps, risks and evidence URLs. No competitor titles, hooks or copy are passed on, so Agent 2
cannot accidentally clone them. `assert_no_verbatim` enforces that in tests and at runtime.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from typing import Any

from .models import Record
from .normalize import norm_text

FORMAT_TERMS = {
    "excel": "Excel", "google sheets": "Google Sheets", "canva": "Canva", "pdf": "PDF",
    "fillable": "fillable PDF", "notion": "Notion", "goodnotes": "Goodnotes", "printable": "printable",
}


class VerbatimLeak(Exception):
    pass


def detect_formats(recs: list[Record]) -> list[str]:
    hits: Counter[str] = Counter()
    for r in recs:
        low = (r.text or "").lower()
        for term, label in FORMAT_TERMS.items():
            if term in low:
                hits[label] += 1
    return [k for k, _ in hits.most_common(6)]


def detect_deliverables(recs: list[Record], vocab: list[str]) -> list[str]:
    counts = {v: sum(1 for r in recs if v in (r.text or "").lower()) for v in vocab}
    return [v for v, c in sorted(counts.items(), key=lambda kv: -kv[1]) if c > 0]


def price_band(recs: list[Record]) -> dict[str, Any]:
    prices = sorted(r.price_usd for r in recs if r.price_usd)
    if not prices:
        return {"minimum": None, "maximum": None, "median": None, "sample_size": 0}
    return {"minimum": prices[0], "maximum": prices[-1], "median": round(statistics.median(prices), 2), "sample_size": len(prices)}


def build_handoff(opp: dict[str, Any], sub_cfg: dict[str, Any], recs: list[Record]) -> dict[str, Any]:
    payload = {
        "opportunity_id": opp["opportunity_id"],
        "category": opp["category"],
        "subcategory": opp["subcategory"],
        "target_customer": sub_cfg.get("target_customer"),
        "core_problem": sub_cfg.get("core_problem"),
        "promise_category": sub_cfg.get("promise_category"),
        "mechanism_category": sub_cfg.get("mechanism_category"),
        "observed_formats": opp["observed_offer_structure"]["formats"],
        "observed_deliverable_types": opp["observed_offer_structure"]["deliverable_types"],
        "observed_price_band_usd": price_band(recs),
        "market_gaps": opp["market_gaps"],
        "evidence_confidence": opp["evidence_confidence"],
        "score": opp["score"]["total"],
        "compliance": opp["compliance"],
        "market_ideas": [
            {k: i[k] for k in ("target_market", "target_region", "currency", "source_market", "status", "confidence", "adaptation", "regional_notes")}
            for i in opp.get("market_ideas", []) if i["status"] != "COMPETITIVE"
        ],
        "evidence_urls": [s["evidence_url"] for s in opp["signals"] if s.get("evidence_url")][:10],
        "constraints_for_modeler": [
            "Do not reuse competitor names, copy, layouts or files",
            "Educational/organizational language only; no clinical, dietary or outcome claims",
            "Pass the six-difference originality test before approval",
        ],
        "human_approval_required": True,
    }
    assert_no_verbatim(payload, recs)
    return payload


def assert_no_verbatim(payload: dict[str, Any], recs: list[Record]) -> None:
    blob = norm_text(json.dumps(payload, default=str))
    for r in recs:
        title = norm_text(r.product_name)
        if len(title) >= 12 and title in blob:
            raise VerbatimLeak(f"competitor title leaked into handoff: {r.product_name!r}")
