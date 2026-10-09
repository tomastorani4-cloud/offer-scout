from datetime import datetime, timezone
from pathlib import Path

from offer_scout.config import load_settings
from offer_scout.models import Record

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)


def settings():
    return load_settings(ROOT / "config", ROOT)


def rec(i=0, **kw) -> Record:
    base = dict(record_id=f"r{i}", source_platform="etsy", source_id=f"s{i}", source_url=f"https://x.test/{i}",
                signal_type="REVIEW_VELOCITY", captured_at="2026-10-06T00:00:00Z", seller=f"seller{i}",
                product_name=f"Unique Title Number {i} alpha{i}", text=f"pet sitter template {i}", country="US",
                price_usd=19.0, review_count=100, recent_review_count_90d=20, reliability="B3")
    base.update(kw)
    return Record(**base)
