"""Meta Ad Library adapter (official Graph API `ads_archive`).

IMPORTANT COVERAGE NOTE (verify in current Meta docs): to the best of our knowledge the API returns
commercial ads only for EU/UK delivery; for US/CA/AU it covers political and social-issue ads.
For US/CA/AU commercial ad persistence, export from the Ad Library UI (or a licensed vendor)
and load it through the CSV adapter. The adapter reports this limitation instead of hiding it.
NOT live-tested in the build environment.
"""
from __future__ import annotations

import json
import os

from ..models import RawRecord, Record
from ..normalize import days_between, make_record_id, now_iso, parse_dt
from .base import Collector, CollectorError, HttpClient, ParseContext

FIELDS = ",".join([
    "id", "page_id", "page_name", "ad_creation_time", "ad_delivery_start_time", "ad_delivery_stop_time",
    "ad_creative_bodies", "ad_creative_link_titles", "ad_creative_link_captions", "ad_snapshot_url",
    "languages", "publisher_platforms",
])
COMMERCIAL_API_COUNTRIES = {"GB"}  # plus EU members; extend if you target them


class MetaAdLibraryCollector(Collector):
    name = "meta_ad_library"
    source_class = "ad_library"
    country_scoped = True

    def __init__(self, token: str | None = None, api_version: str = "v21.0",
                 min_interval_s: float = 1.0, http: HttpClient | None = None):
        self.token = token or os.environ.get("META_AD_LIBRARY_TOKEN")
        if not self.token:
            raise CollectorError("META_AD_LIBRARY_TOKEN not set")
        self.url = f"https://graph.facebook.com/{api_version}/ads_archive"
        self.http = http or HttpClient(min_interval_s)

    def coverage_warnings(self, country: str) -> list[str]:
        if country not in COMMERCIAL_API_COUNTRIES:
            return [f"meta_ad_library: commercial ads for {country} are likely not returned by the API; use CSV import from the Ad Library UI or a licensed vendor"]
        return []

    def collect(self, query: str, country: str, limit: int) -> list[RawRecord]:
        params = {
            "access_token": self.token, "search_terms": query, "ad_type": "ALL",
            "ad_reached_countries": json.dumps([country]), "ad_active_status": "ALL",
            "fields": FIELDS, "limit": min(limit, 100),
        }
        raws: list[RawRecord] = []
        url = self.url
        while url and len(raws) < limit:
            data = self.http.get_json(url, params=params)
            for ad in data.get("data", []):
                raws.append(RawRecord(
                    source_platform="meta_ads", source_id=str(ad["id"]), source_url=ad.get("ad_snapshot_url"),
                    captured_at=now_iso(), query=query, country=country, payload=ad))
            url, params = (data.get("paging") or {}).get("next"), None
        return raws[:limit]

    def parse(self, raw: RawRecord, ctx: ParseContext) -> Record | None:
        ad = raw.payload
        start = parse_dt(ad.get("ad_delivery_start_time") or ad.get("ad_creation_time"))
        stop = parse_dt(ad.get("ad_delivery_stop_time"))
        end = stop or ctx.now
        bodies = " ".join(ad.get("ad_creative_bodies") or [])
        titles = " ".join(ad.get("ad_creative_link_titles") or [])
        return Record(
            record_id=make_record_id("meta_ads", raw.source_id), source_platform="meta_ads",
            source_id=raw.source_id, source_url=raw.source_url, signal_type="AD_PERSISTENCE",
            captured_at=raw.captured_at, seller=ad.get("page_name") or ad.get("page_id"),
            product_name=titles or bodies[:80], text=f"{titles} {bodies}", country=raw.country,
            date_first_seen=start.isoformat() if start else None, date_last_seen=end.isoformat(),
            runtime_days=days_between(start, end), active=stop is None,
        )
