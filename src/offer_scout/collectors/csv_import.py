"""Operator-supplied CSV adapter. The escape hatch for sources without an authorized API.

Expected columns (header names, case-insensitive; unknown columns ignored):
  source_platform, source_id, source_url, signal_type, seller, product_name, text, country, price, currency,
  review_count, recent_review_count_90d, sales_count_visible, date_first_seen, date_last_seen, trend_series
`trend_series` is a semicolon-separated list of numbers (e.g. a Google Trends export row).
`data_class` may be 'operator' for first-party sales exports (reliability A); default is csv_import (C).
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..models import RawRecord, Record, SIGNAL_TYPES
from ..normalize import days_between, make_record_id, now_iso, parse_dt, to_usd
from .base import Collector, CollectorError, ParseContext


def _num(v: str | None) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except ValueError:
        return None


class CsvImportCollector(Collector):
    name = "csv_import"
    source_class = "csv_import"
    country_scoped = True   # only meaningful if the CSV has a country column

    def __init__(self, paths: list[str]):
        self.paths = [Path(p) for p in paths]

    def collect(self, query: str, country: str, limit: int) -> list[RawRecord]:
        # CSV rows are not query-driven: load once per run (the pipeline calls with query='*').
        raws: list[RawRecord] = []
        for path in self.paths:
            if not path.exists():
                raise CollectorError(f"CSV not found: {path}")
            with open(path, newline="", encoding="utf-8-sig") as fh:
                for i, row in enumerate(csv.DictReader(fh)):
                    row = {k.strip().lower(): v for k, v in row.items() if k}
                    sid = row.get("source_id") or f"{path.stem}-{i}"
                    raws.append(RawRecord(
                        source_platform=row.get("source_platform") or "csv", source_id=sid,
                        source_url=row.get("source_url") or None, captured_at=now_iso(),
                        query="*", country=row.get("country") or None, payload=row))
        return raws[:limit]

    def parse(self, raw: RawRecord, ctx: ParseContext) -> Record | None:
        r = raw.payload
        stype = (r.get("signal_type") or "MARKETPLACE_SALES").upper()
        if stype not in SIGNAL_TYPES:
            return None
        start, end = parse_dt(r.get("date_first_seen")), parse_dt(r.get("date_last_seen"))
        series = [float(x) for x in (r.get("trend_series") or "").split(";") if x.strip()] or None
        cls = "operator" if (r.get("data_class") or "").lower() == "operator" else "csv_import"
        rec = Record(
            record_id=make_record_id(raw.source_platform, raw.source_id), source_platform=raw.source_platform,
            source_id=raw.source_id, source_url=raw.source_url, signal_type=stype, captured_at=raw.captured_at,
            seller=r.get("seller") or None, product_name=r.get("product_name") or None,
            text=" ".join(filter(None, [r.get("product_name"), r.get("text")])), country=raw.country,
            price_usd=to_usd(_num(r.get("price")), r.get("currency"), ctx.fx),
            review_count=int(_num(r.get("review_count")) or 0) or None,
            recent_review_count_90d=int(v) if (v := _num(r.get("recent_review_count_90d"))) is not None else None,
            sales_count_visible=int(v) if (v := _num(r.get("sales_count_visible"))) is not None else None,
            date_first_seen=start.isoformat() if start else None, date_last_seen=end.isoformat() if end else None,
            runtime_days=days_between(start, end), trend_series=series,
        )
        rec.reliability = f"{'A' if cls == 'operator' else 'C'}{1 if cls == 'operator' else 3}"
        return rec
