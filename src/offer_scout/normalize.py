from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

_WS = re.compile(r"\s+")
_NON = re.compile(r"[^a-z0-9 ]+")


def now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    s = str(value).strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d"):
        try:
            dt = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def days_between(start: datetime | None, end: datetime | None) -> int | None:
    if not start or not end:
        return None
    return max(0, (end - start).days)


def norm_text(s: str | None) -> str:
    s = (s or "").lower()
    return _WS.sub(" ", _NON.sub(" ", s)).strip()


def tokens(s: str | None) -> set[str]:
    return {t for t in norm_text(s).split() if len(t) > 2}


def to_usd(amount: float | None, currency: str | None, fx: dict[str, float]) -> float | None:
    if amount is None:
        return None
    rate = fx.get((currency or "USD").upper())
    if rate is None:
        return None  # unknown currency: do not guess
    return round(float(amount) * rate, 2)


def make_record_id(platform: str, source_id: str) -> str:
    return hashlib.sha1(f"{platform}:{source_id}".encode()).hexdigest()[:16]


def classify(text: str, subcategories: dict[str, dict[str, Any]]) -> str | None:
    """Pick the subcategory whose match_terms hit most often. Ties go to config order."""
    low = (text or "").lower()
    best_id, best_hits = None, 0
    for sub_id, cfg in subcategories.items():
        terms = list(cfg.get("match_terms", []))
        for lang_terms in (cfg.get("match_terms_i18n") or {}).values():
            terms.extend(lang_terms)
        hits = sum(1 for term in terms if term.lower() in low)
        if hits > best_hits:
            best_id, best_hits = sub_id, hits
    return best_id
