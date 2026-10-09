"""Etsy Open API v3 adapter (official API, preferred over scraping).

NOT live-tested in the build environment (no network). Verify endpoint fields against the
current Etsy developer docs and make sure your key is approved for this commercial use.
Signals produced: MARKETPLACE_SALES (listing data) and REVIEW_VELOCITY (dated reviews).
"""
from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

from ..models import RawRecord, Record
from ..normalize import make_record_id, now_iso, parse_dt, to_usd
from .base import Collector, CollectorError, HttpClient, ParseContext

BASE = "https://openapi.etsy.com/v3/application"


class EtsyApiCollector(Collector):
    name = "etsy_api"
    source_class = "official_api"
    country_scoped = False

    def coverage_warnings(self, country: str) -> list[str]:
        return ["etsy_api: listings are global; the country on each record is the market QUERIED (language-targeted), not verified seller or buyer location"]

    def __init__(self, api_key: str | None = None, min_interval_s: float = 0.4,
                 review_lookup_top_n: int = 30, http: HttpClient | None = None):
        self.api_key = api_key or os.environ.get("ETSY_API_KEY")
        if not self.api_key:
            raise CollectorError("ETSY_API_KEY not set")
        self.http = http or HttpClient(min_interval_s)
        self.top_n = review_lookup_top_n

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key}  # type: ignore[dict-item]

    def collect(self, query: str, country: str, limit: int) -> list[RawRecord]:
        data = self.http.get_json(
            f"{BASE}/listings/active",
            params={"keywords": query, "limit": min(limit, 100), "sort_on": "score"},
            headers=self._headers(),
        )
        raws: list[RawRecord] = []
        for i, item in enumerate(data.get("results", [])):
            payload = dict(item)
            if i < self.top_n and item.get("listing_id"):
                payload["_reviews"] = self._reviews(item["listing_id"])
            raws.append(RawRecord(
                source_platform="etsy", source_id=str(item.get("listing_id")), source_url=item.get("url"),
                captured_at=now_iso(), query=query, country=country, payload=payload))
        return raws

    def _reviews(self, listing_id: int) -> dict[str, Any]:
        try:
            data = self.http.get_json(
                f"{BASE}/listings/{listing_id}/reviews",
                params={"limit": 100}, headers=self._headers())
        except CollectorError:
            return {}
        stamps = [r.get("created_timestamp") or r.get("create_timestamp") for r in data.get("results", [])]
        return {"count": data.get("count"), "timestamps": [s for s in stamps if s]}

    def parse(self, raw: RawRecord, ctx: ParseContext) -> Record | None:
        p = raw.payload
        if p.get("type") not in (None, "download"):
            return None  # digital downloads only
        price = p.get("price") or {}
        amount = (price.get("amount") / price["divisor"]) if price.get("amount") is not None and price.get("divisor") else None
        reviews = p.get("_reviews") or {}
        recent = None
        if reviews.get("timestamps"):
            cutoff = ctx.now - timedelta(days=90)
            recent = sum(1 for t in reviews["timestamps"] if (parse_dt(t) or cutoff) >= cutoff)
        created = parse_dt(p.get("creation_timestamp") or p.get("original_creation_timestamp"))
        return Record(
            record_id=make_record_id("etsy", raw.source_id), source_platform="etsy", source_id=raw.source_id,
            source_url=raw.source_url, signal_type="REVIEW_VELOCITY" if recent is not None else "MARKETPLACE_SALES",
            captured_at=raw.captured_at, seller=str(p.get("shop_id")) if p.get("shop_id") else None,
            product_name=p.get("title"), text=" ".join(filter(None, [p.get("title"), p.get("description"), " ".join(p.get("tags") or [])])),
            country=raw.country, price_usd=to_usd(amount, price.get("currency_code"), ctx.fx),
            review_count=reviews.get("count"), recent_review_count_90d=recent,
            favorers=p.get("num_favorers"), views=p.get("views"),
            date_first_seen=created.isoformat() if created else None, tags=list(p.get("tags") or []),
        )
