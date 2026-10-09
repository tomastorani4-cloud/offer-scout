from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

SIGNAL_TYPES = (
    "AD_PERSISTENCE",
    "MARKETPLACE_SALES",
    "REVIEW_VELOCITY",
    "SEARCH_TREND",
    "COMMENT_INTENT",
    "OPERATOR_DATA",
)


@dataclass
class RawRecord:
    """Bronze layer: exactly what a source returned, plus provenance."""
    source_platform: str
    source_id: str
    source_url: str | None
    captured_at: str
    query: str
    country: str | None
    payload: dict[str, Any]
    simulated: bool = False


@dataclass
class Record:
    """Silver layer: normalized, comparable observation."""
    record_id: str
    source_platform: str
    source_id: str
    source_url: str | None
    signal_type: str
    captured_at: str
    seller: str | None
    product_name: str | None
    text: str
    country: str | None
    category: str | None = None
    subcategory: str | None = None
    price_usd: float | None = None
    review_count: int | None = None
    recent_review_count_90d: int | None = None
    sales_count_visible: int | None = None
    favorers: int | None = None
    views: int | None = None
    date_first_seen: str | None = None
    date_last_seen: str | None = None
    runtime_days: int | None = None
    active: bool | None = None
    trend_series: list[float] | None = None
    tags: list[str] = field(default_factory=list)
    variants: int = 1
    simulated: bool = False
    language: str | None = None
    country_verified: bool = False
    reliability: str = ""
    compliance: dict[str, Any] = field(default_factory=dict)
    rejected: bool = False
    reject_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Score:
    """Gold layer: auditable score. Every point is traceable to a component."""
    total: int
    demand: int
    persistence: int
    quality: int
    viability: int
    differentiation: int
    penalties: list[dict[str, Any]]
    data_driven_points: int
    analyst_prior_points: int
    notes: list[str]
    limitations: list[str]
