"""Builds the scout-2.0 JSON report and validates its structure."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .compliance import _LEVEL
from .markets import STATUSES
from .handoff import detect_deliverables, detect_formats, price_band
from .models import Record, Score

REQUIRED_TOP = ("schema_version", "run", "market_summary", "opportunities", "recommended_next_action")
DECISIONS = {"REJECT", "WATCH", "VALIDATE", "PRIORITY"}
CONFIDENCE = {"LOW", "MEDIUM", "HIGH"}


def build_signals(recs: list[Record], captured_at: str) -> list[dict[str, Any]]:
    out = []
    by_type: dict[str, list[Record]] = {}
    for r in recs:
        by_type.setdefault(r.signal_type, []).append(r)
    for stype, items in by_type.items():
        top = max(items, key=lambda r: (r.review_count or 0, r.runtime_days or 0))
        if stype == "AD_PERSISTENCE":
            desc = f"{len(items)} ads from {len({r.seller for r in items})} advertisers; longest runtime {max((r.runtime_days or 0) for r in items)} days"
        elif stype == "SEARCH_TREND":
            desc = f"{len(items)} trend series (12+ points) available"
        else:
            desc = (f"{len(items)} listings from {len({r.seller for r in items})} sellers; "
                    f"max reviews {max((r.review_count or 0) for r in items)}; reliability {top.reliability}")
        out.append({"signal_type": stype, "description": desc, "evidence_url": top.source_url, "captured_at": captured_at})
    return out


def worst(level_fields: list[str]) -> str:
    return max(level_fields, key=lambda x: _LEVEL[x]) if level_fields else "none"


def build_opportunity(
    opp_id: str, sub_id: str, sub_cfg: dict[str, Any], kept: list[Record], all_recs: list[Record],
    score: Score, conf: str, decision: str, reason: str, flag_counts: Counter, captured_at: str,
) -> dict[str, Any]:
    limits = list(score.limitations)
    if any(r.simulated for r in all_recs):
        limits.insert(0, "SIMULATED data: not valid for decisions")
    blocked = bool(sub_cfg.get("blocked"))
    flags = sorted(flag_counts)
    return {
        "opportunity_id": opp_id,
        "category": sub_cfg["category"],
        "subcategory": sub_id,
        "target_customer": sub_cfg.get("target_customer"),
        "core_problem": sub_cfg.get("core_problem"),
        "score": {
            "total": score.total, "demand": score.demand, "persistence": score.persistence,
            "quality": score.quality, "viability": score.viability, "differentiation": score.differentiation,
            "penalties": score.penalties,
            "data_driven_points": score.data_driven_points, "analyst_prior_points": score.analyst_prior_points,
            "notes": score.notes,
        },
        "evidence_confidence": conf,
        "signals": build_signals(kept, captured_at) if kept else [],
        "evidence_limitations": limits,
        "observed_price_range_usd": price_band(kept),
        "observed_offer_structure": {
            "promise_category": sub_cfg.get("promise_category"),
            "mechanism_category": sub_cfg.get("mechanism_category"),
            "formats": detect_formats(kept),
            "deliverable_types": detect_deliverables(kept, sub_cfg.get("deliverable_vocab", [])),
            "cta_types": ["instant download"] if any("instant" in (r.text or "").lower() for r in kept) else [],
            "funnel_structure": None,
        },
        "recurring_objections": [],
        "market_gaps": list(sub_cfg.get("market_gaps", [])),
        "compliance": {
            "health_risk": worst([r.compliance.get("health_risk", "none") for r in all_recs]) if not blocked else "high",
            "veterinary_risk": worst([r.compliance.get("veterinary_risk", "none") for r in kept]),
            "academic_integrity_risk": worst([r.compliance.get("academic_integrity_risk", "none") for r in kept]),
            "ip_risk": "high" if flag_counts.get("ip_brand") else "low",
            "flags": flags,
            "records_rejected": sum(1 for r in all_recs if r.rejected),
            "records_total": len(all_recs),
            "required_human_review": True,
        },
        "decision": decision,
        "decision_reason": reason + (f" Blocked: {sub_cfg['blocked_reason']}" if blocked else ""),
        "handoff_to_modeler": False,   # set by the pipeline after safety gates
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    """Lightweight structural validation (no external dependency). Returns a list of problems."""
    errs: list[str] = []
    for k in REQUIRED_TOP:
        if k not in report:
            errs.append(f"missing top-level key: {k}")
    if errs:
        return errs
    if report["schema_version"] != "scout-2.0":
        errs.append("schema_version must be scout-2.0")
    if report["run"].get("data_mode") not in {"LIVE", "SIMULATED"}:
        errs.append("run.data_mode must be LIVE or SIMULATED")
    for i, o in enumerate(report["opportunities"]):
        p = f"opportunities[{i}]"
        if o.get("decision") not in DECISIONS:
            errs.append(f"{p}.decision invalid")
        if o.get("evidence_confidence") not in CONFIDENCE:
            errs.append(f"{p}.evidence_confidence invalid")
        sc = o.get("score", {})
        parts = sc.get("demand", 0) + sc.get("persistence", 0) + sc.get("quality", 0) + sc.get("viability", 0) + sc.get("differentiation", 0)
        raw = parts + sum(x["points"] for x in sc.get("penalties", []))
        if sc.get("total") != max(0, min(100, raw)):
            errs.append(f"{p}.score.total does not match components")
        if o.get("evidence_confidence") == "HIGH" and not any(s["signal_type"] == "OPERATOR_DATA" for s in o.get("signals", [])):
            errs.append(f"{p}: HIGH confidence without OPERATOR_DATA")
        if o.get("decision") == "PRIORITY" and o.get("evidence_confidence") == "LOW":
            errs.append(f"{p}: PRIORITY with LOW confidence")
        if o.get("handoff_to_modeler") and report["run"]["data_mode"] == "SIMULATED":
            errs.append(f"{p}: handoff from SIMULATED data")
        if o.get("handoff_to_modeler") and o.get("decision") not in {"VALIDATE", "PRIORITY"}:
            errs.append(f"{p}: handoff for non-VALIDATE/PRIORITY decision")
        for j, idea in enumerate(o.get("market_ideas", [])):
            q = f"{p}.market_ideas[{j}]"
            if idea.get("status") not in STATUSES:
                errs.append(f"{q}.status invalid")
            if idea.get("status") == "GAP_SUPPORTED" and not idea.get("target_evidence", {}).get("coverage_records"):
                errs.append(f"{q}: GAP_SUPPORTED without coverage evidence")
            if idea.get("confidence") == "MEDIUM" and idea.get("simulated"):
                errs.append(f"{q}: MEDIUM confidence from simulated data")
            if not idea.get("caveat"):
                errs.append(f"{q}: missing caveat")
    if report["recommended_next_action"].get("human_approval_required") is not True:
        errs.append("human_approval_required must be true")
    return errs
