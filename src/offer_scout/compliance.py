"""Rule-based compliance screen. Deterministic, auditable, easy to extend in compliance.yaml.

A rule-based screen is deliberately conservative: it may over-reject, never silently pass.
Anything borderline still goes to human review at the opportunity level.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

RISK_FIELDS = ("health_risk", "veterinary_risk", "academic_integrity_risk", "ip_risk")
_LEVEL = {"none": 0, "low": 1, "medium": 2, "high": 3}


@dataclass
class ComplianceResult:
    health_risk: str = "none"
    veterinary_risk: str = "none"
    academic_integrity_risk: str = "none"
    ip_risk: str = "low"
    flags: list[str] = field(default_factory=list)
    hard_reject: bool = False
    assign_subcategory: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "health_risk": self.health_risk,
            "veterinary_risk": self.veterinary_risk,
            "academic_integrity_risk": self.academic_integrity_risk,
            "ip_risk": self.ip_risk,
            "flags": list(self.flags),
            "hard_reject": self.hard_reject,
        }


def _bump(current: str, new: str) -> str:
    return new if _LEVEL[new] > _LEVEL[current] else current


class ComplianceScreen:
    def __init__(self, rules_cfg: dict[str, Any]):
        self.rules = []
        for rule in rules_cfg.get("rules", []):
            compiled = dict(rule)
            if rule["kind"] == "any":
                compiled["_re"] = [re.compile(p, re.I | re.S) for p in rule["patterns"]]
            elif rule["kind"] == "all_of":
                compiled["_groups"] = [[re.compile(p, re.I | re.S) for p in g] for g in rule["groups"]]
            else:
                raise ValueError(f"unknown rule kind: {rule['kind']}")
            self.rules.append(compiled)

    @staticmethod
    def _matches(rule: dict[str, Any], text: str) -> bool:
        if rule["kind"] == "any":
            return any(rx.search(text) for rx in rule["_re"])
        return all(any(rx.search(text) for rx in group) for group in rule["_groups"])

    def evaluate(self, text: str) -> ComplianceResult:
        res = ComplianceResult()
        for rule in self.rules:
            if not self._matches(rule, text):
                continue
            res.flags.append(rule["id"])
            risk, level = rule["risk"], rule["level"]
            if risk in RISK_FIELDS:
                setattr(res, risk, _bump(getattr(res, risk), level))
            if rule.get("effect") == "hard_reject":
                res.hard_reject = True
                if rule.get("assign_subcategory") and not res.assign_subcategory:
                    res.assign_subcategory = rule["assign_subcategory"]
        return res
